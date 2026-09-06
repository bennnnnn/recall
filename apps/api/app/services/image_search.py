"""Reference-photo lookup — search + SSRF-safe mirror + chat persistence.

Separate product path from ``image_generation.py`` (AI creation). Finds a
real photo via Tavily image search, mirrors the bytes into Recall's own
storage (SSRF-safe fetch, size/type validated exactly like any other
attachment upload), and attaches it to the chat as an ``[Image: …]`` marker
— the client never renders a third-party URL directly.
"""

from __future__ import annotations

import logging
from uuid import UUID

import httpx

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.gateways import image_search_gateway, safe_fetch
from app.gateways.storage_gateway import (
    StorageGateway,
    UnconfiguredStorageGateway,
    get_storage_gateway,
)
from app.models.orm import Message, User
from app.repositories import attachments as attachments_repo
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.services import quota as quota_service
from app.services.attachment_content import (
    MAX_ATTACHMENT_SIZE,
    bytes_match_claimed,
    is_image_content_type,
    normalize_content_type,
)

logger = logging.getLogger(__name__)

_IMAGE_SEARCH_MODEL_ALIAS = "image-search-model"
_USER_MESSAGE_PREFIX = "Show me: "
_FETCH_MAX_REDIRECTS = 5


class ImageSearchError(Exception):
    """Domain failure for reference-photo lookup; router maps status_code → HTTP."""

    def __init__(self, detail: str, *, status_code: int) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


async def _rollback_written_bytes(gateway: StorageGateway, storage_keys: list[str]) -> None:
    """Delete object storage if persist failed after write_bytes.

    The orphan reaper only sees attachment rows. A write with no row (or a
    failed persist) would leak the object forever without this rollback.
    """
    for key in storage_keys:
        try:
            await gateway.delete_bytes(key)
        except Exception:
            logger.exception("Failed to delete orphaned reference-photo bytes %s", key)


async def _fetch_one_image(
    client: httpx.AsyncClient,
    hit: image_search_gateway.ImageSearchHit,
) -> tuple[bytes, str] | None:
    """Best-effort SSRF-safe fetch + validation of one candidate image URL.

    Any failure (network, oversized, wrong content-type, spoofed bytes)
    returns None so the caller tries the next candidate instead of erroring
    the whole turn over one bad search result.
    """
    try:
        response = await safe_fetch.fetch_safely(
            client,
            hit.image_url,
            max_redirects=_FETCH_MAX_REDIRECTS,
            max_body_bytes=MAX_ATTACHMENT_SIZE,
        )
        if response.status_code >= 400 or not response.content:
            return None
        content_type = normalize_content_type(response.headers.get("content-type", "image/jpeg"))
        data = response.content
    except Exception:
        logger.warning("Reference-photo candidate fetch failed", exc_info=True)
        return None
    if len(data) > MAX_ATTACHMENT_SIZE or not is_image_content_type(content_type):
        return None
    if not bytes_match_claimed(content_type, data):
        return None
    return data, content_type


async def _fetch_candidates(
    settings: Settings,
    hits: list[image_search_gateway.ImageSearchHit],
    *,
    max_images: int,
) -> list[tuple[bytes, str]]:
    fetched: list[tuple[bytes, str]] = []
    async with httpx.AsyncClient(
        timeout=settings.image_search_fetch_timeout_seconds, follow_redirects=False
    ) as client:
        for hit in hits:
            if len(fetched) >= max_images:
                break
            result = await _fetch_one_image(client, hit)
            if result is not None:
                fetched.append(result)
    return fetched


async def search_and_attach_for_chat(
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    query: str,
    user_message_content: str | None = None,
    create_user_message: bool = True,
) -> tuple[Message, Message]:
    """Plan/quota/storage/persist path for a reference-photo lookup turn.

    Returns (user_message, assistant_message). Raises ``ImageSearchError`` on
    expected failures (not found, quota, storage); unexpected exceptions are
    re-raised after quota refund. Mirrors ``image_generation.generate_for_chat``'s
    shape — the "provider call" here is a Tavily image search followed by an
    SSRF-safe fetch of the winning photo(s), never an AI generation, and runs
    with no DB session held.
    """
    if not settings.image_search_enabled:
        raise ImageSearchError("Not available", status_code=404)
    if not settings.attachments_enabled:
        raise ImageSearchError("Attachments are disabled", status_code=503)

    cleaned = query.strip()
    if not cleaned:
        raise ImageSearchError("Query is required", status_code=400)

    async with SessionLocal() as session:
        chat = await chats_repo.get_by_id(session, chat_id, user.id)
        if chat is None:
            raise ImageSearchError("Chat not found", status_code=404)

    gateway = get_storage_gateway(settings)
    if isinstance(gateway, UnconfiguredStorageGateway):
        raise ImageSearchError("Attachment storage is not configured", status_code=503)

    redis = get_redis_client()
    if await quota_service.global_spend_exceeded(redis, settings):
        raise ImageSearchError(
            quota_service.IMAGE_SEARCH_SPEND_CAP_MESSAGE,
            status_code=429,
        )
    daily_limit = quota_service.image_search_limit_for_user(user, settings)
    if not await quota_service.reserve_image_search(redis, user.id, limit=daily_limit):
        raise ImageSearchError(
            quota_service.image_search_limit_exceeded_message(user),
            status_code=429,
        )

    written_keys: list[str] = []
    try:
        # Provider HTTP (search + candidate fetches) — no DB session held.
        hits = await image_search_gateway.search_images(
            settings, cleaned, max_results=settings.image_search_max_results
        )
        if not hits:
            raise ImageSearchError("Could not find a reference photo", status_code=502)

        fetched = await _fetch_candidates(
            settings, hits, max_images=settings.image_search_max_results
        )
        if not fetched:
            raise ImageSearchError("Could not find a usable reference photo", status_code=502)

        attachment_ids: list[UUID] = []
        async with SessionLocal() as session:
            for data, content_type in fetched:
                presigned = await gateway.presign_upload(
                    user_id=str(user.id),
                    content_type=content_type,
                    size_bytes=len(data),
                )
                attachment_id = UUID(presigned.attachment_id)
                await gateway.write_bytes(presigned.storage_key, data)
                written_keys.append(presigned.storage_key)
                await attachments_repo.create_pending(
                    session,
                    attachment_id=attachment_id,
                    user_id=user.id,
                    storage_key=presigned.storage_key,
                    content_type=content_type,
                    size_bytes=len(data),
                    source="search",
                    original_filename=(cleaned.replace("\n", " ").strip()[:255] or None),
                    commit=False,
                )
                attachment_ids.append(attachment_id)

            if create_user_message:
                bubble = (user_message_content or f"{_USER_MESSAGE_PREFIX}{cleaned}").strip()
                if not bubble:
                    bubble = f"{_USER_MESSAGE_PREFIX}{cleaned}"
                user_message = await messages_repo.create(
                    session,
                    chat_id=chat_id,
                    user_id=user.id,
                    role="user",
                    content=bubble,
                    commit=False,
                )
            else:
                existing = await messages_repo.get_last_user(session, chat_id)
                if existing is None:
                    raise ImageSearchError("No user message to attach image to", status_code=404)
                user_message = existing

            markers = "\n".join(
                f"[Image: /attachments/{attachment_id}/file]" for attachment_id in attachment_ids
            )
            assistant_message = await messages_repo.create(
                session,
                chat_id=chat_id,
                user_id=user.id,
                role="assistant",
                content=markers,
                model=_IMAGE_SEARCH_MODEL_ALIAS,
                commit=False,
            )
            linked = await attachments_repo.link_to_message(
                session,
                user_id=user.id,
                attachment_ids=attachment_ids,
                message_id=assistant_message.id,
                commit=False,
            )
            if linked != len(attachment_ids):
                raise ImageSearchError("Could not link reference photo", status_code=500)
            for attachment_id in attachment_ids:
                # Bytes were fetched and validated here — skip /file re-download.
                await attachments_repo.mark_verified(session, attachment_id, commit=False)
            # Persist the turn atomically. If any link fails, session close
            # rolls back rows before byte cleanup.
            await session.commit()
    except ImageSearchError:
        await _rollback_written_bytes(gateway, written_keys)
        await quota_service.refund_image_search(redis, user.id)
        raise
    except BaseException:
        await _rollback_written_bytes(gateway, written_keys)
        await quota_service.refund_image_search(redis, user.id)
        raise

    try:
        await quota_service.record_global_spend(redis, quota_service.IMAGE_SEARCH_SPEND_USD)
    except Exception:
        logger.exception("record_global_spend failed after photo lookup")

    return user_message, assistant_message


def image_search_marker_ids(content: str) -> list[UUID]:
    """Parse ``[Image: /attachments/{uuid}/file]`` markers (reused for revisions/tests)."""
    from app.services.attachment_content import image_attachment_ids_from_text

    return image_attachment_ids_from_text(content)

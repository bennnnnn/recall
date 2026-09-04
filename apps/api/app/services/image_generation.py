"""Text-to-image product service (validation, provider call, chat persistence)."""

from __future__ import annotations

import logging
import re
from typing import Literal, cast
from uuid import UUID, uuid4

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.gateways import image_gateway, mock_llm
from app.gateways.storage_gateway import (
    StorageGateway,
    UnconfiguredStorageGateway,
    get_storage_gateway,
)
from app.models.orm import Attachment, Message, User
from app.repositories import attachments as attachments_repo
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.services import plan as plan_service
from app.services import quota as quota_service
from app.services.attachment_content import (
    MAX_ATTACHMENT_SIZE,
    bytes_match_claimed,
    is_image_content_type,
    normalize_content_type,
)
from app.services.model_catalog import get as get_model
from app.services.model_catalog import openrouter_slug

logger = logging.getLogger(__name__)

_MAX_PROMPT_LEN = 2000
_USER_MESSAGE_PREFIX = "Generate image: "
_IMAGE_MODEL_ALIAS = "image-gen-model"

AspectRatio = Literal["1:1", "16:9", "9:16", "4:3", "3:4"]
_ALLOWED_ASPECT_RATIOS: frozenset[str] = frozenset({"1:1", "16:9", "9:16", "4:3", "3:4"})


class ImageGenerationError(Exception):
    """Domain failure for image generation; router maps status_code → HTTP."""

    def __init__(self, detail: str, *, status_code: int) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


async def _rollback_written_bytes(gateway: StorageGateway, storage_key: str | None) -> None:
    """Delete object storage if persist failed after write_bytes.

    The orphan reaper only sees attachment rows. A write with no row (or a
    failed persist) would leak the object forever without this rollback.
    """
    if not storage_key:
        return
    try:
        await gateway.delete_bytes(storage_key)
    except Exception:
        logger.exception("Failed to delete orphaned generated image %s", storage_key)


def normalize_aspect_ratio(value: str | None) -> AspectRatio | None:
    if not value:
        return None
    trimmed = value.strip()
    if trimmed in _ALLOWED_ASPECT_RATIOS:
        return cast(AspectRatio, trimmed)
    return None


async def generate_image(
    settings: Settings,
    *,
    prompt: str,
    aspect_ratio: str | None = None,
    reference_images: list[tuple[bytes, str]] | None = None,
) -> tuple[bytes, str] | None:
    """Return (image_bytes, content_type) or None on failure."""
    if not settings.image_generation_enabled:
        return None
    cleaned = prompt.strip()
    if not cleaned or len(cleaned) > _MAX_PROMPT_LEN:
        logger.warning("Image generation rejected: prompt length=%s", len(cleaned))
        return None
    if mock_llm.should_mock_llm(settings):
        return mock_llm.mock_image_bytes(), "image/png"
    if not settings.openrouter_api_key:
        return None

    model = (settings.image_generation_model or openrouter_slug(_IMAGE_MODEL_ALIAS)).strip()
    return await image_gateway.generate_via_openrouter(
        settings,
        prompt=cleaned,
        model=model,
        aspect_ratio=normalize_aspect_ratio(aspect_ratio),
        reference_images=reference_images,
    )


async def generate_for_chat(
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    prompt: str,
    aspect_ratio: str | None = None,
    user_message_content: str | None = None,
    create_user_message: bool = True,
    reference_attachment_ids: list[UUID] | None = None,
) -> tuple[Message, Message]:
    """Plan/quota/storage/persist path for POST /images/generate.

    Returns (user_message, assistant_message). Raises ImageGenerationError on
    expected failures; unexpected exceptions are re-raised after quota refund.

    ``user_message_content`` is the composer text shown in the user bubble
    (e.g. \"create a cat image\"). Falls back to ``Generate image: …`` only
    when the caller did not pass the original wording. Set
    ``create_user_message=False`` when regenerating — only a new assistant row
    is written.

    DB sessions open only around ownership checks and persistence — the image
    provider HTTP call runs with no pool checkout held.
    """
    if not settings.image_generation_enabled:
        raise ImageGenerationError("Not available", status_code=404)
    if not settings.attachments_enabled:
        raise ImageGenerationError("Attachments are disabled", status_code=503)
    if not plan_service.is_pro(user):
        raise ImageGenerationError("Image generation requires Pro", status_code=403)

    async with SessionLocal() as session:
        chat = await chats_repo.get_by_id(session, chat_id, user.id)
        if chat is None:
            raise ImageGenerationError("Chat not found", status_code=404)
        if reference_attachment_ids is None and not create_user_message:
            prior = await messages_repo.get_last_user(session, chat_id)
            reference_attachment_ids = image_reference_ids(prior.content if prior else "")

    gateway = get_storage_gateway(settings)
    if isinstance(gateway, UnconfiguredStorageGateway):
        raise ImageGenerationError("Attachment storage is not configured", status_code=503)

    references = await load_reference_images(
        gateway, user_id=user.id, attachment_ids=reference_attachment_ids or []
    )

    redis = get_redis_client()
    daily_limit = quota_service.image_generation_limit_for_user(user, settings)
    if not await quota_service.reserve_image_generation(redis, user.id, limit=daily_limit):
        raise ImageGenerationError(
            quota_service.image_generation_limit_exceeded_message(user),
            status_code=429,
        )

    cleaned = prompt.strip()
    if not cleaned:
        await quota_service.refund_image_generation(redis, user.id)
        raise ImageGenerationError("Prompt is required", status_code=400)

    written_key: str | None = None
    reference_keys: list[str] = []
    try:
        # Provider HTTP — no DB session held.
        generated = await generate_image(
            settings,
            prompt=cleaned,
            aspect_ratio=aspect_ratio,
            reference_images=[(raw, row.content_type) for row, raw in references] or None,
        )
        if not generated:
            raise ImageGenerationError("Could not generate image", status_code=502)
        image_bytes, content_type = generated
        content_type = normalize_content_type(content_type)
        # BUG FIX: last-line-of-defense size check, matching the presign +
        # actual-bytes double-check every normal attachment upload gets in
        # routers/attachments.py. The gateway already rejects an oversized
        # provider response, but this keeps the invariant enforced here too
        # rather than trusting it was applied upstream.
        if len(image_bytes) > MAX_ATTACHMENT_SIZE:
            raise ImageGenerationError(
                "Generated image exceeds the maximum allowed size",
                status_code=502,
            )
        if not is_image_content_type(content_type):
            raise ImageGenerationError("Generated file is not an image", status_code=502)
        if not bytes_match_claimed(content_type, image_bytes):
            raise ImageGenerationError("Generated image failed validation", status_code=502)

        presigned = await gateway.presign_upload(
            user_id=str(user.id),
            content_type=content_type,
            size_bytes=len(image_bytes),
        )
        attachment_id = UUID(presigned.attachment_id)
        await gateway.write_bytes(presigned.storage_key, image_bytes)
        written_key = presigned.storage_key

        reference_copies: list[tuple[Attachment, UUID, str]] = []
        if create_user_message:
            for source, raw in references:
                ref_id = uuid4()
                ref_key = f"{user.id}/{ref_id}"
                await gateway.write_bytes(ref_key, raw)
                reference_keys.append(ref_key)
                reference_copies.append((source, ref_id, ref_key))

        async with SessionLocal() as session:
            await attachments_repo.create_pending(
                session,
                attachment_id=attachment_id,
                user_id=user.id,
                storage_key=presigned.storage_key,
                content_type=content_type,
                size_bytes=len(image_bytes),
                source="generated",
                original_filename=(cleaned.replace("\n", " ").strip()[:255] or None),
                commit=False,
            )

            if create_user_message:
                bubble = (user_message_content or f"{_USER_MESSAGE_PREFIX}{cleaned}").strip()
                if not bubble:
                    bubble = f"{_USER_MESSAGE_PREFIX}{cleaned}"
                # Independent hidden copies keep an edit/regenerate usable if
                # its original Library item or earlier image is later deleted.
                reference_ids: list[UUID] = []
                for source, ref_id, ref_key in reference_copies:
                    await attachments_repo.insert_verified_clone(
                        session, src=source, new_id=ref_id, storage_key=ref_key
                    )
                    reference_ids.append(ref_id)
                    bubble += f"\n[Image: /attachments/{ref_id}/file]"
                user_message = await messages_repo.create(
                    session,
                    chat_id=chat_id,
                    user_id=user.id,
                    role="user",
                    content=bubble,
                    commit=False,
                )
                if reference_ids:
                    linked_refs = await attachments_repo.link_to_message(
                        session,
                        user_id=user.id,
                        attachment_ids=reference_ids,
                        message_id=user_message.id,
                        commit=False,
                    )
                    if linked_refs != len(reference_ids):
                        raise ImageGenerationError(
                            "Could not preserve image references", status_code=500
                        )
            else:
                existing = await messages_repo.get_last_user(session, chat_id)
                if existing is None:
                    raise ImageGenerationError(
                        "No user message to attach image to", status_code=404
                    )
                user_message = existing
            image_marker = f"[Image: /attachments/{attachment_id}/file]"
            assistant_message = await messages_repo.create(
                session,
                chat_id=chat_id,
                user_id=user.id,
                role="assistant",
                content=image_marker,
                model=get_model(_IMAGE_MODEL_ALIAS).id,
                commit=False,
            )
            linked = await attachments_repo.link_to_message(
                session,
                user_id=user.id,
                attachment_ids=[attachment_id],
                message_id=assistant_message.id,
                commit=False,
            )
            if linked != 1:
                raise ImageGenerationError("Could not link generated image", status_code=500)
            # Bytes were generated and validated here — skip /file re-download.
            await attachments_repo.mark_verified(session, attachment_id, commit=False)
            # Persist the turn and its reference copies atomically. If any
            # link fails, session close rolls back rows before byte cleanup.
            await session.commit()
    except ImageGenerationError as exc:
        await _rollback_written_bytes(gateway, written_key)
        for key in reference_keys:
            await _rollback_written_bytes(gateway, key)
        if exc.status_code not in (403, 429):
            await quota_service.refund_image_generation(redis, user.id)
        raise
    except Exception:
        await _rollback_written_bytes(gateway, written_key)
        for key in reference_keys:
            await _rollback_written_bytes(gateway, key)
        await quota_service.refund_image_generation(redis, user.id)
        raise

    return user_message, assistant_message


async def load_reference_images(
    gateway: StorageGateway, *, user_id: UUID, attachment_ids: list[UUID]
) -> list[tuple[Attachment, bytes]]:
    """Resolve only owned, bounded image bytes; never fetch client-supplied URLs."""
    ids = list(dict.fromkeys(attachment_ids))
    if len(ids) > 2:
        raise ImageGenerationError("Use at most two reference images", status_code=400)
    if not ids:
        return []
    async with SessionLocal() as session:
        rows = await attachments_repo.get_by_ids(session, ids, user_id)
    by_id = {row.id: row for row in rows}
    if len(by_id) != len(ids):
        raise ImageGenerationError("Reference image not found", status_code=404)
    result = []
    for ref_id in ids:
        row = by_id[ref_id]
        if not is_image_content_type(row.content_type):
            raise ImageGenerationError("Reference must be an image", status_code=400)
        raw = await gateway.read_bytes(row.storage_key)
        if (
            not raw
            or len(raw) > MAX_ATTACHMENT_SIZE
            or not bytes_match_claimed(row.content_type, raw)
        ):
            raise ImageGenerationError("Reference image is unavailable or invalid", status_code=400)
        result.append((row, raw))
    return result


def image_reference_ids(content: str) -> list[UUID]:
    return list(
        dict.fromkeys(
            UUID(value)
            for value in re.findall(
                r"\[Image: /attachments/([0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}"
                r"[0-9a-fA-F]{12})/file\]",
                content,
            )
        )
    )[:2]

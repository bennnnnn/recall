import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.exceptions import AttachmentValidationError, ChatBusyError, ChatNotFoundError
from app.gateways.storage_gateway import StorageUnavailableError
from app.models.math_schemas import MathImageExtract
from app.models.orm import Attachment, User
from app.repositories import users as users_repo
from app.services.attachment_quota import has_current_upload_reservation
from app.services.chat.stream_status import StreamStatusFn


async def count_image_attachments(
    session: AsyncSession, user_id: UUID, attachment_ids: list[UUID]
) -> int:
    from app.repositories import attachments as attachments_repo
    from app.services.attachment_content import IMAGE_CONTENT_TYPES, normalize_content_type

    rows = await attachments_repo.get_by_ids(session, attachment_ids, user_id)
    return sum(1 for row in rows if normalize_content_type(row.content_type) in IMAGE_CONTENT_TYPES)


def vision_reserve_tokens(settings: Settings, image_count: int) -> int:
    if image_count <= 0:
        return 0
    return image_count * settings.image_attachment_reserve_tokens


@dataclass
class _AttachmentProcessResult:
    user: User | None
    user_content: str
    content: str
    has_image_attachment: bool
    # At least one non-image (document) attachment — these need RAG, which is
    # gated by rich_context. Images use vision injection (runs regardless of
    # rich_context), so an image-only turn must NOT force rich context (it
    # would trigger status theater + heavy prompt building for a vision QA turn).
    has_document_attachment: bool
    image_attachments: list[tuple[str, str]]
    image_math_extract: MathImageExtract | None
    gateway: Any | None
    # storage_key → bytes loaded once during verify (or first read this turn)
    bytes_by_key: dict[str, bytes]
    # Ids to persist/link. None = caller keeps the request list (no attachments).
    resolved_attachment_ids: list[UUID] | None = None


async def _process_attachments(
    *,
    user_id: UUID,
    user: User | None,
    content: str,
    attachment_ids: list[UUID] | None,
    settings: Settings,
    redis: Redis,
    on_status: StreamStatusFn | None,
) -> _AttachmentProcessResult:
    """Storage outages here are safe to retry: no user message has been saved yet."""
    try:
        return await _process_attachment_inputs(
            user_id=user_id,
            user=user,
            content=content,
            attachment_ids=attachment_ids,
            settings=settings,
            redis=redis,
            on_status=on_status,
        )
    except StorageUnavailableError as exc:
        raise ChatBusyError(
            "Attachment storage is temporarily unavailable. Please retry shortly."
        ) from exc


async def _process_attachment_inputs(
    *,
    user_id: UUID,
    user: User | None,
    content: str,
    attachment_ids: list[UUID] | None,
    settings: Settings,
    redis: Redis,
    on_status: StreamStatusFn | None,
) -> _AttachmentProcessResult:
    """Verify/format attachments and optionally vision-extract a camera math equation."""
    user_content = content
    gateway = None
    has_image_attachment = False
    image_attachments: list[tuple[str, str]] = []
    image_math_extract: MathImageExtract | None = None
    attachment_rows: list[Attachment] = []
    resolved_ids: list[UUID] = []

    if attachment_ids and not settings.attachments_enabled:
        raise AttachmentValidationError("Attachments are temporarily unavailable.")
    if not (attachment_ids and settings.attachments_enabled):
        return _AttachmentProcessResult(
            user=user,
            user_content=user_content,
            content=content,
            has_image_attachment=False,
            has_document_attachment=False,
            image_attachments=[],
            image_math_extract=None,
            gateway=None,
            bytes_by_key={},
        )

    attachment_ids = list(dict.fromkeys(attachment_ids))
    async with SessionLocal() as session:
        if user is None:
            user = await users_repo.get_by_id(session, user_id)
            if user is None:
                raise ChatNotFoundError("User not found.")
        from app.repositories import attachments as attachments_repo

        rows_by_id = {
            row.id: row
            for row in await attachments_repo.get_by_ids(session, attachment_ids, user.id)
        }
        if any(attachment_id not in rows_by_id for attachment_id in attachment_ids):
            raise AttachmentValidationError(
                "An attached file is no longer available. Attach it again."
            )
        attachment_rows = [
            rows_by_id[attachment_id]
            for attachment_id in attachment_ids
            if attachment_id in rows_by_id
        ]
        if attachment_rows:
            from app.services.attachment_reuse import ensure_unlinked_copies

            attachment_rows = await ensure_unlinked_copies(session, settings, attachment_rows)
        resolved_ids = [row.id for row in attachment_rows]

    if not attachment_rows:
        return _AttachmentProcessResult(
            user=user,
            user_content=user_content,
            content=content,
            has_image_attachment=False,
            has_document_attachment=False,
            image_attachments=[],
            image_math_extract=None,
            gateway=None,
            bytes_by_key={},
            resolved_attachment_ids=[],
        )

    from app.gateways.storage_gateway import get_storage_gateway
    from app.services import attachment_content as attachment_content_service

    if on_status is not None:
        await on_status("reading_files")

    gateway = get_storage_gateway(settings)
    # One download per storage_key this turn — reuse for format / OCR / vision.
    bytes_by_key: dict[str, bytes] = {}
    if attachment_rows:
        unverified = [row for row in attachment_rows if row.verified_at is None]
        if unverified:
            verified = await asyncio.gather(
                *[
                    attachment_content_service.verify_uploaded_bytes(
                        gateway,
                        content_type=row.content_type,
                        storage_key=row.storage_key,
                        declared_size=row.size_bytes,
                    )
                    for row in unverified
                ]
            )
            for row, (data, error) in zip(unverified, verified, strict=True):
                if error:
                    async with SessionLocal() as purge_session:
                        removed = await attachment_content_service.purge_invalid_upload(
                            gateway,
                            purge_session,
                            attachment_id=row.id,
                            storage_key=row.storage_key,
                        )
                    if (
                        removed
                        and attachment_content_service.is_image_content_type(row.content_type)
                        and has_current_upload_reservation(row)
                    ):
                        from app.services import quota as quota_service

                        await quota_service.refund_image_upload(redis, user_id)
                    raise AttachmentValidationError(error)
                if data:
                    bytes_by_key[row.storage_key] = data
                    async with SessionLocal() as verify_session:
                        await attachments_repo.mark_verified(verify_session, row.id)
    attachment_lines: list[str] = []
    formatted = await asyncio.gather(
        *(
            attachment_content_service.format_attachment_lines(
                gateway,
                attachment_id=str(row.id),
                content_type=row.content_type,
                storage_key=row.storage_key,
                size_bytes=row.size_bytes,
                settings=settings,
                data=bytes_by_key.get(row.storage_key),
            )
            for row in attachment_rows
        )
    )
    for row, (lines, is_image) in zip(attachment_rows, formatted, strict=True):
        if is_image:
            has_image_attachment = True
            image_attachments.append((row.content_type, row.storage_key))
        attachment_lines.extend(lines)
    # Persist plain attachment markers for the chat UI. Do NOT wrap
    # with wrap_untrusted here — that preamble is prompt-injection
    # framing for the model and must never appear as a user bubble.
    # File excerpts still land in history as data; wrap_untrusted is
    # applied when assembling LLM context elsewhere (RAG / search).
    if attachment_lines:
        plain = "\n".join(attachment_lines)
        if user_content.strip():
            user_content = f"{user_content}\n\n{plain}"
        else:
            user_content = plain

    # Camera math solver: vision-extract equation so SymPy can verify.
    from app.services import math_image_extract as math_image_extract_service
    from app.services import math_text_match

    # BUG FIX: this used to require the sent text to be BYTE-FOR-BYTE
    # identical to the preset camera caption — the composer pre-fills that
    # caption into an editable text box, so any user edit (add a word, fix
    # a typo, autocorrect touching punctuation) silently dropped the OCR
    # step with no error shown; the photo still sent, just unverified.
    # An edited caption from someone who chose "Solve math with camera"
    # overwhelmingly still reads as a math ask ("solve this", "find x", a
    # stray leftover word) — reuse the same has_math_keyword signal
    # needs_symbolic_math already trusts for the image-attachment case, so
    # OCR fires whenever the caption still looks like a math request, not
    # only on an exact match. A caption with no math keyword at all (or the
    # default blank caption every plain image attachment sends) is left
    # alone — this must not fire a vision call on every unrelated photo.
    caption = content.strip()
    looks_like_math_caption = bool(caption) and math_text_match.has_math_keyword(caption.lower())
    if (
        has_image_attachment
        and image_attachments
        and (math_image_extract_service.is_math_camera_prompt(content) or looks_like_math_caption)
    ):
        if on_status is not None:
            await on_status("calculating")
        mime, storage_key = image_attachments[0]
        image_bytes = bytes_by_key.get(storage_key)
        if image_bytes is None:
            image_bytes = await attachment_content_service.read_attachment_bytes(
                gateway, storage_key
            )
            if image_bytes:
                bytes_by_key[storage_key] = image_bytes
        if image_bytes:
            extracted = await math_image_extract_service.extract_equation_from_image(
                settings, content_type=mime, data=image_bytes
            )
            if extracted is not None:
                image_math_extract = extracted
                suffix = math_image_extract_service.camera_math_user_suffix(extracted)
                # Prompt/stream path sees Solve: for equations; stored bubble
                # keeps the image marker + original caption only.
                if suffix:
                    content = f"{content}\n\n{suffix}"

    return _AttachmentProcessResult(
        user=user,
        user_content=user_content,
        content=content,
        has_image_attachment=has_image_attachment,
        # A document attachment is any non-image row — images are not
        # indexable (is_indexable_attachment excludes them) and use vision
        # injection instead of RAG, so only documents force rich context.
        has_document_attachment=len(attachment_rows) != len(image_attachments),
        image_attachments=image_attachments,
        image_math_extract=image_math_extract,
        gateway=gateway,
        bytes_by_key=bytes_by_key,
        resolved_attachment_ids=resolved_ids,
    )

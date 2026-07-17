import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.exceptions import ChatNotFoundError
from app.models.math_schemas import MathImageExtract
from app.models.orm import Attachment, User
from app.repositories import users as users_repo
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
    image_attachments: list[tuple[str, str]]
    image_math_extract: MathImageExtract | None
    gateway: Any | None


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
    """Verify/format attachments and optionally vision-extract a camera math equation."""
    user_content = content
    gateway = None
    has_image_attachment = False
    image_attachments: list[tuple[str, str]] = []
    image_math_extract: MathImageExtract | None = None

    if not (attachment_ids and settings.attachments_enabled):
        return _AttachmentProcessResult(
            user=user,
            user_content=user_content,
            content=content,
            has_image_attachment=False,
            image_attachments=[],
            image_math_extract=None,
            gateway=None,
        )

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
        attachment_rows: list[Attachment] = [
            rows_by_id[attachment_id]
            for attachment_id in attachment_ids
            if attachment_id in rows_by_id
        ]

    if not attachment_rows:
        return _AttachmentProcessResult(
            user=user,
            user_content=user_content,
            content=content,
            has_image_attachment=False,
            image_attachments=[],
            image_math_extract=None,
            gateway=None,
        )

    from app.gateways.storage_gateway import LocalStorageGateway, get_storage_gateway
    from app.services import attachment_content as attachment_content_service

    if on_status is not None:
        await on_status("reading_files")

    gateway = get_storage_gateway(settings)
    if not isinstance(gateway, LocalStorageGateway):
        from app.exceptions import AttachmentValidationError

        for row in attachment_rows:
            _, error = await attachment_content_service.verify_uploaded_bytes(
                gateway,
                content_type=row.content_type,
                storage_key=row.storage_key,
            )
            if error:
                if attachment_content_service.is_image_content_type(row.content_type):
                    from app.services import quota as quota_service

                    await quota_service.refund_image_upload(redis, user_id)
                async with SessionLocal() as purge_session:
                    await attachment_content_service.purge_invalid_upload(
                        gateway,
                        purge_session,
                        attachment_id=row.id,
                        storage_key=row.storage_key,
                    )
                raise AttachmentValidationError(error)
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

    if (
        has_image_attachment
        and image_attachments
        and math_image_extract_service.is_math_camera_prompt(content)
    ):
        if on_status is not None:
            await on_status("calculating")
        mime, storage_key = image_attachments[0]
        image_bytes = await attachment_content_service.read_attachment_bytes(gateway, storage_key)
        if image_bytes:
            extracted = await math_image_extract_service.extract_equation_from_image(
                settings, content_type=mime, data=image_bytes
            )
            if extracted is not None:
                image_math_extract = extracted
                eq = f"{extracted.lhs} = {extracted.rhs}"
                # Prompt/stream path sees Solve:; stored bubble keeps
                # the image marker + original caption only.
                content = f"{content}\n\nSolve: {eq}"

    return _AttachmentProcessResult(
        user=user,
        user_content=user_content,
        content=content,
        has_image_attachment=has_image_attachment,
        image_attachments=image_attachments,
        image_math_extract=image_math_extract,
        gateway=gateway,
    )

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.aio import gather_or_cancel
from app.core.config import Settings
from app.core.db import SessionLocal
from app.exceptions import AttachmentValidationError, ChatBusyError, ChatNotFoundError
from app.gateways.storage_gateway import StorageGateway, StorageUnavailableError
from app.models.orm import Attachment, User
from app.modules.attachments.quota import has_current_upload_reservation, upload_counter
from app.modules.chat.stream_status import StreamStatusFn
from app.repositories import users as users_repo
from app.services.subjects.registry import (
    SUBJECTS,
    MathImageExtract,
    PhotoReading,
    SubjectPhoto,
    subject_adapter,
)


async def load_attachment_rows(
    session: AsyncSession, user_id: UUID, attachment_ids: list[UUID]
) -> list[Attachment]:
    """The user's rows among ``attachment_ids``, in one query: the quota counts their images,
    then the turn reads its files from the same rows (``prepare_chat_turn``)."""
    from app.modules.attachments import service as attachments_service

    return list(await attachments_service.get_by_ids(session, attachment_ids, user_id))


def count_images(rows: list[Attachment]) -> int:
    from app.modules.attachments.content_types import IMAGE_CONTENT_TYPES, normalize_content_type

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
    # An image's bytes by storage key, read once this turn (documents' are dropped).
    bytes_by_key: dict[str, bytes]
    # Ids to persist/link. None = caller keeps the request list (no attachments).
    resolved_attachment_ids: list[UUID] | None = None
    # The photo's reader was not sure what it read: nothing from it is certified.
    photo_uncertain: bool = False


async def _process_attachments(
    *,
    user_id: UUID,
    user: User | None,
    content: str,
    attachment_ids: list[UUID] | None,
    settings: Settings,
    redis: Redis,
    on_status: StreamStatusFn | None,
    rows: list[Attachment] | None = None,
) -> _AttachmentProcessResult:
    """Storage outages here are safe to retry: no user message has been saved yet.

    ``rows``: the requested rows, when the turn already read them (``load_attachment_rows``).
    """
    try:
        return await _process_attachment_inputs(
            user_id=user_id,
            user=user,
            content=content,
            attachment_ids=attachment_ids,
            settings=settings,
            redis=redis,
            on_status=on_status,
            rows=rows,
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
    rows: list[Attachment] | None = None,
) -> _AttachmentProcessResult:
    """Verify/format attachments and optionally vision-extract a camera math equation."""
    if attachment_ids and not settings.attachments_enabled:
        raise AttachmentValidationError("Attachments are temporarily unavailable.")
    if not (attachment_ids and settings.attachments_enabled):
        return _without_attachments(user, content)

    user, attachment_rows, resolved_ids = await _load_turn_attachments(
        user_id=user_id, user=user, attachment_ids=attachment_ids, settings=settings, rows=rows
    )
    if not attachment_rows:
        return _without_attachments(user, content, resolved_ids=[])

    from app.gateways.storage_gateway import get_storage_gateway

    if on_status is not None:
        await on_status("reading_files")

    gateway = get_storage_gateway(settings)
    attachment_lines, image_attachments, bytes_by_key = await _read_turn_attachments(
        gateway, attachment_rows, settings=settings, redis=redis, user_id=user_id
    )
    reading, kept = await _read_photo_problem(
        content,
        image_attachments=image_attachments,
        bytes_by_key=bytes_by_key,
        gateway=gateway,
        settings=settings,
        on_status=on_status,
    )
    user_content = _with_attachment_markers(kept, attachment_lines)
    content = reading.content

    return _AttachmentProcessResult(
        user=user,
        user_content=user_content,
        content=content,
        has_image_attachment=bool(image_attachments),
        # A document attachment is any non-image row — images are not
        # indexable (is_indexable_attachment excludes them) and use vision
        # injection instead of RAG, so only documents force rich context.
        has_document_attachment=len(attachment_rows) != len(image_attachments),
        image_attachments=image_attachments,
        image_math_extract=reading.extract,
        gateway=gateway,
        bytes_by_key=bytes_by_key,
        resolved_attachment_ids=resolved_ids,
        photo_uncertain=reading.uncertain,
    )


async def _read_photo_problem(
    content: str,
    *,
    image_attachments: list[tuple[str, str]],
    bytes_by_key: dict[str, bytes],
    gateway: StorageGateway,
    settings: Settings,
    on_status: StreamStatusFn | None,
) -> tuple[PhotoReading, str]:
    """The problem read off the first photo (``content`` with its line for the prompt), and
    the caption the user's row keeps.

    The scanner's tab names the reader in the caption, and that subject reads its own photo;
    any other photo is maths' to try. What the photo says then decides its subject, as a
    typed line's words do (``_read_by_its_subject``). The stored bytes downloaded here are
    kept in ``bytes_by_key`` for the vision injection; a reader gets the photo upright."""
    photo = _photo_reader(content)
    if photo is None:
        return PhotoReading(None, content), content
    from app.core.blocking import run_blocking
    from app.modules.attachments import content as attachment_content_service
    from app.modules.attachments.vision_input import upright_for_reading

    content_types = {storage_key: content_type for content_type, storage_key in image_attachments}

    async def load_image(storage_key: str) -> tuple[str, bytes] | None:
        image_bytes = bytes_by_key.get(storage_key)
        if image_bytes is None:
            image_bytes = await attachment_content_service.read_attachment_bytes(
                gateway, storage_key
            )
            if image_bytes:
                bytes_by_key[storage_key] = image_bytes
        if not image_bytes:
            return None
        return await run_blocking(
            "images",
            upright_for_reading,
            image_bytes,
            content_types.get(storage_key, "image/jpeg"),
            max_edge=settings.attachment_vision_max_edge,
            max_pixels=settings.attachment_image_max_decode_pixels,
        )

    reading = await photo.read(
        content,
        image_attachments=image_attachments,
        load_image=load_image,
        settings=settings,
        on_status=on_status,
    )
    moved = await _read_by_its_subject(content, reading, settings)
    if moved is not None:
        # The row keeps what the tab sent, as a maths photo's row does: the bubble shows
        # what it always showed, and the reading is the prompt's.
        return moved, content
    return reading, _stored_caption(content, reading.content)


async def _read_by_its_subject(
    content: str, reading: PhotoReading, settings: Settings
) -> PhotoReading | None:
    """A scanner photo whose words are another subject's problem: that subject's.

    The tab picked the reader, and a physics word problem on the maths tab never reached
    physics (audit SCAN-04, 2026-11-13). A reader that transcribed the page without stating
    it (maths') hands its transcription to the subject order, which decides a typed line's
    subject; when the order names another subject that is on, the transcription becomes the
    photo's line, which that subject solves, and maths' structured read goes. None: the
    photo stays the tab's.
    """
    from app.core.readings import read_aside
    from app.services.subject_scan import scanner_camera_subject, with_confirmed_reading
    from app.services.subjects.dispatch import detect_subject

    tab = scanner_camera_subject(content)
    if tab is None or not reading.transcription:
        return None
    subject = await read_aside(
        detect_subject,
        reading.transcription,
        chemistry_enabled=settings.chemistry_enabled,
        timeout=settings.subject_read_timeout_seconds,
    )
    if subject is None or subject == tab or not subject_adapter(subject).enabled(settings):
        return None
    return PhotoReading(
        None, with_confirmed_reading(content, reading.transcription), uncertain=reading.uncertain
    )


def _stored_caption(sent: str, read: str) -> str:
    """The caption the user's row keeps: with the reading a scanner photo's subject stated as
    its confirmed line (as the scanner's old review sent it), so a follow-up and a
    regenerate find the problem; otherwise the caption as sent (maths' ``Solve:`` line is
    the prompt's only)."""
    from app.services.subject_scan import confirmed_scan_reading

    if confirmed_scan_reading(read) is not None and confirmed_scan_reading(sent) is None:
        return read
    return sent


def _photo_reader(content: str) -> SubjectPhoto | None:
    from app.services.subject_scan import scanner_camera_subject

    named = scanner_camera_subject(content)
    for adapter in SUBJECTS:
        if adapter.name == named and adapter.photo is not None:
            return adapter.photo
    return subject_adapter("math").photo


def _without_attachments(
    user: User | None, content: str, *, resolved_ids: list[UUID] | None = None
) -> _AttachmentProcessResult:
    """A turn with nothing attached to read: the text passes through as it was sent."""
    return _AttachmentProcessResult(
        user=user,
        user_content=content,
        content=content,
        has_image_attachment=False,
        has_document_attachment=False,
        image_attachments=[],
        image_math_extract=None,
        gateway=None,
        bytes_by_key={},
        resolved_attachment_ids=resolved_ids,
    )


async def _load_turn_attachments(
    *,
    user_id: UUID,
    user: User | None,
    attachment_ids: list[UUID],
    settings: Settings,
    rows: list[Attachment] | None = None,
) -> tuple[User, list[Attachment], list[UUID]]:
    """The user and their requested rows in request order, a linked Library row copied.

    A missing user, or a requested id that is missing or someone else's, refuses the turn.
    ``rows`` read already are not read again: the session then runs nothing unless a row
    needs its copy.
    """
    attachment_ids = list(dict.fromkeys(attachment_ids))
    async with SessionLocal() as session:
        if user is None:
            user = await users_repo.get_by_id(session, user_id)
            if user is None:
                raise ChatNotFoundError("User not found.")
        if rows is None:
            rows = await load_attachment_rows(session, user.id, attachment_ids)
        rows_by_id = {row.id: row for row in rows}
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
            from app.modules.attachments.reuse import ensure_unlinked_copies

            attachment_rows = await ensure_unlinked_copies(session, settings, attachment_rows)
        resolved_ids = [row.id for row in attachment_rows]
    return user, attachment_rows, resolved_ids


# Files read at once. Ten 10 MiB documents were downloaded together and their bytes
# kept to the end of the turn, past 100 MiB plus their parse trees on a machine with
# well under a gigabyte to spare.
_FILES_AT_ONCE = 2


async def _read_turn_attachments(
    gateway: StorageGateway,
    attachment_rows: list[Attachment],
    *,
    settings: Settings,
    redis: Redis,
    user_id: UUID,
) -> tuple[list[str], list[tuple[str, str]], dict[str, bytes]]:
    """Each row's lines (a marker, and a document's excerpt) and the images, in row order.

    A file is read once: an unverified upload's bytes are checked, then formatted, two
    files at a time. A document's bytes are dropped once its excerpt is taken; an image's
    are returned by storage key for vision. A bad upload is purged and refuses the turn,
    cancelling the other reads. Verified rows are marked in one statement at the end.
    """
    from app.modules.attachments import content as attachment_content_service
    from app.modules.attachments import service as attachments_service

    slots = asyncio.Semaphore(_FILES_AT_ONCE)
    image_bytes: dict[str, bytes] = {}
    verified: list[UUID] = []

    async def read(row: Attachment) -> tuple[list[str], bool]:
        async with slots:
            data: bytes | None = None
            if row.verified_at is None:
                data, error = await attachment_content_service.verify_uploaded_bytes(
                    gateway,
                    content_type=row.content_type,
                    storage_key=row.storage_key,
                    declared_size=row.size_bytes,
                )
                if error:
                    await _refuse_bad_upload(gateway, row, error, redis=redis, user_id=user_id)
                if data:
                    verified.append(row.id)
            lines, is_image = await attachment_content_service.format_attachment_lines(
                gateway,
                attachment_id=str(row.id),
                content_type=row.content_type,
                storage_key=row.storage_key,
                size_bytes=row.size_bytes,
                settings=settings,
                data=data,
            )
            if is_image and data:
                image_bytes[row.storage_key] = data
            return lines, is_image

    formatted = await gather_or_cancel(*(read(row) for row in attachment_rows))
    if verified:
        async with SessionLocal() as session:
            await attachments_service.mark_verified_many(session, verified)
    image_attachments: list[tuple[str, str]] = []
    attachment_lines: list[str] = []
    for row, (lines, is_image) in zip(attachment_rows, formatted, strict=True):
        if is_image:
            image_attachments.append((row.content_type, row.storage_key))
        attachment_lines.extend(lines)
    return attachment_lines, image_attachments, image_bytes


async def _refuse_bad_upload(
    gateway: StorageGateway, row: Attachment, error: str, *, redis: Redis, user_id: UUID
) -> None:
    """Purge an upload whose bytes failed their check, refund its slot, refuse the turn."""
    from app.modules.attachments import content as attachment_content_service

    async with SessionLocal() as purge_session:
        removed = await attachment_content_service.purge_invalid_upload(
            gateway,
            purge_session,
            attachment_id=row.id,
            storage_key=row.storage_key,
        )
    if removed and has_current_upload_reservation(row):
        from app.services.quota import counters

        await counters.refund(upload_counter(row.content_type), redis, user_id)
    raise AttachmentValidationError(error)


def _with_attachment_markers(user_content: str, attachment_lines: list[str]) -> str:
    """The stored user bubble: the caption, then the attachment lines (alone if it is blank)."""
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
    return user_content

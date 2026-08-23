"""Attachment gallery, upload verification, and download policy."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.gateways.storage_gateway import LocalStorageGateway, get_storage_gateway
from app.models.orm import User
from app.models.schemas import AttachmentListItemOut, AttachmentListOut, AttachmentOut
from app.repositories import attachments as attachments_repo
from app.services import quota as quota_service
from app.services.attachment_content import (
    MAX_ATTACHMENT_SIZE,
    bytes_match_claimed,
    ensure_verified_or_purge,
    is_image_content_type,
    purge_invalid_upload,
)


class AttachmentWorkflowError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class FileAccess:
    content_type: str
    local_path: Path | None = None
    redirect_url: str | None = None


async def _refund_image(
    user: User,
    content_type: str,
) -> None:
    if is_image_content_type(content_type):
        await quota_service.refund_image_upload(get_redis_client(), user.id)


async def _verified_row(
    session: AsyncSession,
    settings: Settings,
    user: User,
    attachment_id: UUID,
):
    row = await attachments_repo.get_by_id(session, attachment_id, user.id)
    if row is None:
        raise AttachmentWorkflowError(404, "Not found")
    gateway = get_storage_gateway(settings)
    if row.verified_at is None:
        error = await ensure_verified_or_purge(
            gateway,
            session,
            attachment_id=attachment_id,
            content_type=row.content_type,
            storage_key=row.storage_key,
            declared_size=row.size_bytes,
        )
        if error:
            await _refund_image(user, row.content_type)
            raise AttachmentWorkflowError(400, error)
    return row, gateway


async def list_attachments(
    session: AsyncSession,
    settings: Settings,
    user: User,
    *,
    category: str | None,
    source: str | None,
    q: str | None,
    limit: int,
    offset: int,
) -> AttachmentListOut:
    rows, has_more = await attachments_repo.list_for_gallery(
        session,
        user.id,
        category=category,
        source=source,
        q=q,
        limit=limit,
        offset=offset,
    )
    message_ids = [row.message_id for row in rows if row.message_id is not None]
    chat_by_message = await attachments_repo.chat_ids_for_message_ids(session, message_ids)
    gateway = get_storage_gateway(settings)
    items: list[AttachmentListItemOut] = []
    for row in rows:
        url = (
            f"/attachments/{row.id}/file"
            if isinstance(gateway, LocalStorageGateway)
            else await gateway.presign_download(row.storage_key)
        )
        items.append(
            AttachmentListItemOut(
                id=row.id,
                content_type=row.content_type,
                size_bytes=row.size_bytes,
                download_url=url,
                source=row.source,
                created_at=row.created_at,
                chat_id=chat_by_message.get(row.message_id) if row.message_id else None,
                message_id=row.message_id,
                original_filename=row.original_filename,
            )
        )
    return AttachmentListOut(items=items, has_more=has_more)


class _UploadTooLarge(Exception):
    pass


async def _read_upload_capped(stream: AsyncIterator[bytes], max_bytes: int) -> bytes:
    """Read the body without buffering past the declared/max size."""
    parts: list[bytes] = []
    size = 0
    async for chunk in stream:
        if not chunk:
            continue
        size += len(chunk)
        if size > max_bytes:
            raise _UploadTooLarge
        parts.append(chunk)
    return b"".join(parts)


async def store_local_upload(
    session: AsyncSession,
    settings: Settings,
    user: User,
    attachment_id: UUID,
    stream: AsyncIterator[bytes],
) -> None:
    row = await attachments_repo.get_by_id(session, attachment_id, user.id)
    if row is None:
        raise AttachmentWorkflowError(404, "Not found")
    gateway = get_storage_gateway(settings)
    if not isinstance(gateway, LocalStorageGateway):
        raise AttachmentWorkflowError(501, "Use presigned upload")
    if row.message_id is not None:
        raise AttachmentWorkflowError(409, "Attachment is already linked to a message")

    cap = min(MAX_ATTACHMENT_SIZE, max(row.size_bytes, 0))
    detail: str | None = None
    try:
        data = await _read_upload_capped(stream, cap)
    except _UploadTooLarge:
        data = b""
        detail = "Invalid upload size"
    if detail is None:
        if not data or len(data) > MAX_ATTACHMENT_SIZE:
            detail = "Invalid upload size"
        elif len(data) != row.size_bytes:
            detail = "Uploaded size does not match the declared size"
        elif not bytes_match_claimed(row.content_type, data):
            detail = "Uploaded bytes do not match the declared content type"
    if detail:
        await purge_invalid_upload(
            gateway,
            session,
            attachment_id=row.id,
            storage_key=row.storage_key,
        )
        await _refund_image(user, row.content_type)
        raise AttachmentWorkflowError(400, detail)

    await gateway.write_bytes(row.storage_key, data)
    await attachments_repo.mark_verified(session, row.id)


async def confirm_upload(
    session: AsyncSession,
    settings: Settings,
    user: User,
    attachment_id: UUID,
) -> None:
    row = await attachments_repo.get_by_id(session, attachment_id, user.id)
    if row is None:
        raise AttachmentWorkflowError(404, "Not found")
    gateway = get_storage_gateway(settings)
    if isinstance(gateway, LocalStorageGateway):
        return
    error = await ensure_verified_or_purge(
        gateway,
        session,
        attachment_id=attachment_id,
        content_type=row.content_type,
        storage_key=row.storage_key,
        declared_size=row.size_bytes,
    )
    if error:
        await _refund_image(user, row.content_type)
        raise AttachmentWorkflowError(400, error)


async def get_file_access(
    session: AsyncSession,
    settings: Settings,
    user: User,
    attachment_id: UUID,
) -> FileAccess:
    row, gateway = await _verified_row(session, settings, user, attachment_id)
    if isinstance(gateway, LocalStorageGateway):
        path = gateway.resolve_local_path(row.storage_key)
        if path is None:
            raise AttachmentWorkflowError(404, "File missing")
        return FileAccess(content_type=row.content_type, local_path=path)
    return FileAccess(
        content_type=row.content_type,
        redirect_url=await gateway.presign_download(row.storage_key),
    )


async def get_download(
    session: AsyncSession,
    settings: Settings,
    user: User,
    attachment_id: UUID,
) -> AttachmentOut:
    row, gateway = await _verified_row(session, settings, user, attachment_id)
    url = (
        f"/attachments/{attachment_id}/file"
        if isinstance(gateway, LocalStorageGateway)
        else await gateway.presign_download(row.storage_key)
    )
    return AttachmentOut(
        id=row.id,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        download_url=url,
        created_at=row.created_at,
    )

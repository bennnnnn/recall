"""Presign + pending-row orchestration for attachment uploads."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.gateways.storage_gateway import UnconfiguredStorageGateway, get_storage_gateway
from app.models.orm import User
from app.models.schemas import AttachmentPresignOut
from app.repositories import attachments as attachments_repo
from app.services import quota as quota_service
from app.services.attachment_content import (
    IMAGE_CONTENT_TYPES,
    MAX_ATTACHMENT_SIZE,
    is_allowed_content_type,
    normalize_content_type,
)


class AttachmentUploadError(Exception):
    """Typed failure for the attachments router to map to HTTPException."""

    def __init__(self, detail: str, *, status_code: int) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


async def create_presigned_upload(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
    content_type: str,
    size_bytes: int,
) -> AttachmentPresignOut:
    """Validate, reserve image quota, presign storage, and create a pending row."""
    if not is_allowed_content_type(content_type):
        raise AttachmentUploadError("Unsupported content type", status_code=400)
    if size_bytes <= 0 or size_bytes > MAX_ATTACHMENT_SIZE:
        raise AttachmentUploadError("Invalid file size", status_code=400)

    normalized = normalize_content_type(content_type)

    gateway = get_storage_gateway(settings)
    if isinstance(gateway, UnconfiguredStorageGateway):
        raise AttachmentUploadError(
            "Attachment storage is not configured",
            status_code=503,
        )

    redis = get_redis_client()
    image_reserved = False
    if normalized in IMAGE_CONTENT_TYPES:
        image_limit = quota_service.image_upload_limit_for_user(user, settings)
        if not await quota_service.reserve_image_upload(redis, user.id, limit=image_limit):
            raise AttachmentUploadError(
                quota_service.image_limit_exceeded_message(user),
                status_code=429,
            )
        image_reserved = True

    try:
        presigned = await gateway.presign_upload(
            user_id=str(user.id),
            content_type=normalized,
            size_bytes=size_bytes,
        )
        attachment_id = UUID(presigned.attachment_id)
        await attachments_repo.create_pending(
            session,
            attachment_id=attachment_id,
            user_id=user.id,
            storage_key=presigned.storage_key,
            content_type=normalized,
            size_bytes=size_bytes,
        )
    except Exception:
        if image_reserved:
            await quota_service.refund_image_upload(redis, user.id)
        raise

    return AttachmentPresignOut(
        attachment_id=attachment_id,
        upload_url=presigned.upload_url,
        storage_key=presigned.storage_key,
        headers=presigned.headers,
        api_upload=presigned.api_upload,
    )

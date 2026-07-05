from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_settings_dep
from app.core.redis import get_redis_client
from app.gateways.storage_gateway import (
    LocalStorageGateway,
    UnconfiguredStorageGateway,
    get_storage_gateway,
)
from app.models.orm import User
from app.models.schemas import AttachmentOut, AttachmentPresignIn, AttachmentPresignOut
from app.repositories import attachments as attachments_repo
from app.services import quota as quota_service
from app.services.attachment_content import (
    IMAGE_CONTENT_TYPES,
    MAX_ATTACHMENT_SIZE,
    bytes_match_claimed,
    ensure_verified_or_purge,
    is_allowed_content_type,
    is_image_content_type,
    normalize_content_type,
)

router = APIRouter(prefix="/attachments", tags=["attachments"])

MAX_SIZE = MAX_ATTACHMENT_SIZE


async def _reject_unverified_upload(
    *,
    gateway,
    session: AsyncSession,
    user: User,
    attachment_id: UUID,
    content_type: str,
    storage_key: str,
) -> None:
    error = await ensure_verified_or_purge(
        gateway,
        session,
        attachment_id=attachment_id,
        content_type=content_type,
        storage_key=storage_key,
    )
    if error:
        if is_image_content_type(content_type):
            await quota_service.refund_image_upload(get_redis_client(), user.id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)


@router.post("/presign", response_model=AttachmentPresignOut)
async def presign_upload(
    body: AttachmentPresignIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> AttachmentPresignOut:
    if not is_allowed_content_type(body.content_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported content type"
        )
    if body.size_bytes <= 0 or body.size_bytes > MAX_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file size")

    content_type = normalize_content_type(body.content_type)

    gateway = get_storage_gateway(settings)
    if isinstance(gateway, UnconfiguredStorageGateway):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Attachment storage is not configured",
        )

    redis = get_redis_client()
    image_reserved = False
    if content_type in IMAGE_CONTENT_TYPES:
        image_limit = quota_service.image_upload_limit_for_user(user, settings)
        if not await quota_service.reserve_image_upload(redis, user.id, limit=image_limit):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=quota_service.image_limit_exceeded_message(user),
            )
        image_reserved = True

    try:
        presigned = await gateway.presign_upload(
            user_id=str(user.id),
            content_type=content_type,
            size_bytes=body.size_bytes,
        )
        from uuid import UUID as UUIDType

        attachment_id = UUIDType(presigned.attachment_id)
        await attachments_repo.create_pending(
            session,
            attachment_id=attachment_id,
            user_id=user.id,
            storage_key=presigned.storage_key,
            content_type=content_type,
            size_bytes=body.size_bytes,
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


@router.put("/{attachment_id}/upload", status_code=status.HTTP_204_NO_CONTENT)
async def upload_attachment_bytes(
    attachment_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    row = await attachments_repo.get_by_id(session, attachment_id, user.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    data = await request.body()
    if not data or len(data) > MAX_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid upload size")
    # Verify the actual bytes match the declared content type so a presigned
    # "image/png" can't be used to store a non-image blob that later gets served
    # back with the wrong Content-Type.
    if not bytes_match_claimed(row.content_type, data):
        if is_image_content_type(row.content_type):
            await quota_service.refund_image_upload(get_redis_client(), user.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded bytes do not match the declared content type",
        )

    gateway = get_storage_gateway(settings)
    if not isinstance(gateway, LocalStorageGateway):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Use presigned upload"
        )
    await gateway.write_bytes(row.storage_key, data)


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_pending_upload(
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Cancel a pending upload and refund the daily image slot if one was reserved."""
    row = await attachments_repo.get_by_id(session, attachment_id, user.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if row.message_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attachment is already linked to a message",
        )

    gateway = get_storage_gateway(settings)
    await gateway.delete_bytes(row.storage_key)
    await attachments_repo.delete_rows(session, [attachment_id])
    if is_image_content_type(row.content_type):
        await quota_service.refund_image_upload(get_redis_client(), user.id)


@router.post("/{attachment_id}/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_upload(
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Verify bytes stored at presigned URL match the declared content type."""
    row = await attachments_repo.get_by_id(session, attachment_id, user.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    gateway = get_storage_gateway(settings)
    if isinstance(gateway, LocalStorageGateway):
        # Dev/local uploads are validated on PUT /upload.
        return

    await _reject_unverified_upload(
        gateway=gateway,
        session=session,
        user=user,
        attachment_id=attachment_id,
        content_type=row.content_type,
        storage_key=row.storage_key,
    )


@router.get("/{attachment_id}/file", response_model=None)
async def serve_attachment_file(
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> FileResponse | RedirectResponse:
    row = await attachments_repo.get_by_id(session, attachment_id, user.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    gateway = get_storage_gateway(settings)
    await _reject_unverified_upload(
        gateway=gateway,
        session=session,
        user=user,
        attachment_id=attachment_id,
        content_type=row.content_type,
        storage_key=row.storage_key,
    )
    if isinstance(gateway, LocalStorageGateway):
        path = gateway.resolve_local_path(row.storage_key)
        if path is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing")
        return FileResponse(path, media_type=row.content_type)
    # R2/S3: redirect to a short-lived presigned GET so the client fetches the
    # blob directly from object storage. Keeps the mobile's existing /file call
    # working for both backends.
    download_url = await gateway.presign_download(row.storage_key)
    return RedirectResponse(url=download_url, status_code=status.HTTP_302_FOUND)


@router.get("/{attachment_id}/url", response_model=AttachmentOut)
async def download_url(
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> AttachmentOut:
    row = await attachments_repo.get_by_id(session, attachment_id, user.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    gateway = get_storage_gateway(settings)
    await _reject_unverified_upload(
        gateway=gateway,
        session=session,
        user=user,
        attachment_id=attachment_id,
        content_type=row.content_type,
        storage_key=row.storage_key,
    )
    if isinstance(gateway, LocalStorageGateway):
        url = f"/attachments/{attachment_id}/file"
    else:
        url = await gateway.presign_download(row.storage_key)
    return AttachmentOut(
        id=row.id,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        download_url=url,
        created_at=row.created_at,
    )

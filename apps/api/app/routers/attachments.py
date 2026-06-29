from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_settings_dep
from app.gateways.storage_gateway import LocalStorageGateway, get_storage_gateway
from app.models.orm import User
from app.models.schemas import AttachmentOut, AttachmentPresignIn, AttachmentPresignOut
from app.repositories import attachments as attachments_repo
from app.services.attachment_content import (
    MAX_ATTACHMENT_SIZE,
    is_allowed_content_type,
    normalize_content_type,
)

router = APIRouter(prefix="/attachments", tags=["attachments"])

MAX_SIZE = MAX_ATTACHMENT_SIZE


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

    gateway = get_storage_gateway(settings)
    if not isinstance(gateway, LocalStorageGateway):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Use presigned upload"
        )
    await gateway.write_bytes(row.storage_key, data)


@router.get("/{attachment_id}/file")
async def serve_attachment_file(
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> FileResponse:
    row = await attachments_repo.get_by_id(session, attachment_id, user.id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    gateway = get_storage_gateway(settings)
    if not isinstance(gateway, LocalStorageGateway):
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not available")
    path = gateway.resolve_local_path(row.storage_key)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing")
    return FileResponse(path, media_type=row.content_type)


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

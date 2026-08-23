from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_settings_dep
from app.models.orm import User
from app.models.schemas import (
    AttachmentListOut,
    AttachmentOut,
    AttachmentPresignIn,
    AttachmentPresignOut,
)
from app.services import attachment_workflow
from app.services.attachment_upload import AttachmentUploadError, create_presigned_upload
from app.services.attachment_upload import (
    cancel_pending_upload as cancel_pending_upload_service,
)

router = APIRouter(prefix="/attachments", tags=["attachments"])


async def require_attachments_enabled(
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Reject write endpoints when the attachments feature flag is off.
    Reads (file/url) and cancel-delete stay open so existing attachments can
    still be retrieved and pending uploads cleaned up after a flag flip."""
    if not settings.attachments_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Attachments are disabled",
        )


def _workflow_http_error(exc: attachment_workflow.AttachmentWorkflowError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("", response_model=AttachmentListOut)
async def list_attachments(
    category: str | None = Query(default=None, pattern="^(images|files)$"),
    source: str | None = Query(default=None, pattern="^(upload|generated)$"),
    q: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> AttachmentListOut:
    """List the user's attachments with pagination.

    ``q`` is a case-insensitive substring over filename, content type, and
    the linked message (covers image-gen prompts).
    """
    query = q.strip() if q else None
    if not query:
        query = None
    return await attachment_workflow.list_attachments(
        session,
        settings,
        user,
        category=category,
        source=source,
        q=query,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/presign",
    response_model=AttachmentPresignOut,
    dependencies=[Depends(require_attachments_enabled)],
)
async def presign_upload(
    body: AttachmentPresignIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> AttachmentPresignOut:
    try:
        return await create_presigned_upload(
            session,
            settings,
            user=user,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
            filename=body.filename,
        )
    except AttachmentUploadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.put(
    "/{attachment_id}/upload",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_attachments_enabled)],
)
async def upload_attachment_bytes(
    attachment_id: UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    data = await request.body()
    try:
        await attachment_workflow.store_local_upload(
            session,
            settings,
            user,
            attachment_id,
            data,
        )
    except attachment_workflow.AttachmentWorkflowError as exc:
        raise _workflow_http_error(exc) from exc


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_pending_upload(
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Cancel a pending upload and refund the daily image slot if one was reserved."""
    try:
        await cancel_pending_upload_service(
            session,
            settings,
            user=user,
            attachment_id=attachment_id,
        )
    except AttachmentUploadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post(
    "/{attachment_id}/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_attachments_enabled)],
)
async def confirm_upload(
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Verify bytes stored at presigned URL match the declared content type."""
    try:
        await attachment_workflow.confirm_upload(
            session,
            settings,
            user,
            attachment_id,
        )
    except attachment_workflow.AttachmentWorkflowError as exc:
        raise _workflow_http_error(exc) from exc


@router.get("/{attachment_id}/file", response_model=None)
async def serve_attachment_file(
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> FileResponse | RedirectResponse:
    try:
        access = await attachment_workflow.get_file_access(
            session,
            settings,
            user,
            attachment_id,
        )
    except attachment_workflow.AttachmentWorkflowError as exc:
        raise _workflow_http_error(exc) from exc
    if access.local_path is not None:
        return FileResponse(
            access.local_path,
            media_type=access.content_type,
            headers={"X-Content-Type-Options": "nosniff"},
        )
    if access.redirect_url is None:
        raise RuntimeError("Attachment access result has no target")
    return RedirectResponse(
        url=access.redirect_url,
        status_code=status.HTTP_302_FOUND,
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/{attachment_id}/url", response_model=AttachmentOut)
async def download_url(
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> AttachmentOut:
    try:
        return await attachment_workflow.get_download(
            session,
            settings,
            user,
            attachment_id,
        )
    except attachment_workflow.AttachmentWorkflowError as exc:
        raise _workflow_http_error(exc) from exc

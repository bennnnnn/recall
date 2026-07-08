from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_settings_dep
from app.core.redis import get_redis_client
from app.gateways.storage_gateway import UnconfiguredStorageGateway, get_storage_gateway
from app.models.orm import User
from app.models.schemas import ImageGenerateIn, ImageGenerateOut, MessageOut
from app.repositories import attachments as attachments_repo
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.services import image_generation as image_generation_service
from app.services import plan as plan_service
from app.services import quota as quota_service
from app.services.attachment_content import bytes_match_claimed, is_image_content_type
from app.services.model_catalog import get as get_model

router = APIRouter(prefix="/images", tags=["images"])

_USER_MESSAGE_PREFIX = "Generate image: "
_IMAGE_MODEL_ALIAS = "image-gen-model"


@router.post("/generate", response_model=ImageGenerateOut)
async def generate_image(
    body: ImageGenerateIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> ImageGenerateOut:
    if not settings.image_generation_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not available")
    if not settings.attachments_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Attachments are disabled",
        )
    if not plan_service.is_pro(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Image generation requires Pro",
        )

    chat = await chats_repo.get_by_id(session, body.chat_id, user.id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    gateway = get_storage_gateway(settings)
    if isinstance(gateway, UnconfiguredStorageGateway):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Attachment storage is not configured",
        )

    redis = get_redis_client()
    daily_limit = quota_service.image_generation_limit_for_user(user, settings)
    if not await quota_service.reserve_image_generation(redis, user.id, limit=daily_limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=quota_service.image_generation_limit_exceeded_message(user),
        )

    prompt = body.prompt.strip()
    if not prompt:
        await quota_service.refund_image_generation(redis, user.id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prompt is required")

    try:
        generated = await image_generation_service.generate_image(
            settings,
            prompt=prompt,
            aspect_ratio=body.aspect_ratio,
        )
        if not generated:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not generate image",
            )
        image_bytes, content_type = generated
        if not is_image_content_type(content_type):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Generated file is not an image",
            )
        if not bytes_match_claimed(content_type, image_bytes):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Generated image failed validation",
            )

        presigned = await gateway.presign_upload(
            user_id=str(user.id),
            content_type=content_type,
            size_bytes=len(image_bytes),
        )
        attachment_id = UUID(presigned.attachment_id)
        await attachments_repo.create_pending(
            session,
            attachment_id=attachment_id,
            user_id=user.id,
            storage_key=presigned.storage_key,
            content_type=content_type,
            size_bytes=len(image_bytes),
        )
        await gateway.write_bytes(presigned.storage_key, image_bytes)

        user_message = await messages_repo.create(
            session,
            chat_id=body.chat_id,
            user_id=user.id,
            role="user",
            content=f"{_USER_MESSAGE_PREFIX}{prompt}",
        )
        image_marker = f"[Image: /attachments/{attachment_id}/file]"
        assistant_message = await messages_repo.create(
            session,
            chat_id=body.chat_id,
            user_id=user.id,
            role="assistant",
            content=image_marker,
            model=get_model(_IMAGE_MODEL_ALIAS).id,
        )
        linked = await attachments_repo.link_to_message(
            session,
            user_id=user.id,
            attachment_ids=[attachment_id],
            message_id=assistant_message.id,
        )
        if linked != 1:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not link generated image",
            )
    except HTTPException as exc:
        if exc.status_code not in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_429_TOO_MANY_REQUESTS,
        ):
            await quota_service.refund_image_generation(redis, user.id)
        raise
    except Exception:
        await quota_service.refund_image_generation(redis, user.id)
        raise

    return ImageGenerateOut(
        user_message=MessageOut.model_validate(user_message),
        assistant_message=MessageOut.model_validate(assistant_message),
    )

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.models.orm import User
from app.models.schemas import ImageGenerateIn, ImageGenerateOut, MessageOut
from app.services import image_generation as image_generation_service

router = APIRouter(prefix="/images", tags=["images"])


@router.post("/generate", response_model=ImageGenerateOut)
async def generate_image(
    body: ImageGenerateIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> ImageGenerateOut:
    try:
        user_message, assistant_message = await image_generation_service.generate_for_chat(
            settings,
            user=user,
            chat_id=body.chat_id,
            prompt=body.prompt,
            aspect_ratio=body.aspect_ratio,
        )
    except image_generation_service.ImageGenerationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return ImageGenerateOut(
        user_message=MessageOut.model_validate(user_message),
        assistant_message=MessageOut.model_validate(assistant_message),
    )

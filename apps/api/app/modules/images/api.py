from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.models.orm import User
from app.models.schemas.chats import MessageOut
from app.modules.account import profile as profile_service
from app.modules.images import generation as image_generation_service
from app.modules.images import intent as image_intent_service
from app.modules.images.schemas import (
    ImageGenerateIn,
    ImageGenerateOut,
    ImageIntentIn,
    ImageIntentOut,
)

ImageGenerateOut.model_rebuild(_types_namespace={"MessageOut": MessageOut})

router = APIRouter(prefix="/images", tags=["images"])


@router.post("/generate", response_model=ImageGenerateOut)
async def generate_image(
    body: ImageGenerateIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> ImageGenerateOut:
    original = (body.user_message or "").strip() or None
    user_message, assistant_message = await image_generation_service.generate_for_chat(
        settings,
        user=user,
        chat_id=body.chat_id,
        prompt=body.prompt,
        aspect_ratio=body.aspect_ratio,
        user_message_content=original,
        reference_attachment_ids=body.reference_attachment_ids,
    )

    return ImageGenerateOut(
        user_message=MessageOut.model_validate(user_message),
        assistant_message=MessageOut.model_validate(assistant_message),
    )


@router.post("/intent", response_model=ImageIntentOut)
async def image_intent(
    body: ImageIntentIn,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> ImageIntentOut:
    """How the phone's composer sends a turn: a photo lookup, a picture, or chat.

    The phone reads no image intent itself; it asks here before a send that might
    be a picture, and this answers with the chat turn's own reading of the text and
    the chat's recent turns. A chat that is not the user's is not found.
    """
    verdict = await image_intent_service.composer_intent_for_chat(
        profile_service.settings_for_user(settings, user),
        user_id=user.id,
        text=body.text,
        chat_id=body.chat_id,
        image_attached=body.image_attached,
    )
    if verdict is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    request = verdict.request
    return ImageIntentOut(
        subject=verdict.subject,
        lookup_query=verdict.lookup_query,
        generate_prompt=request.prompt if request else None,
        revision=bool(request and request.revision),
        reference_attachment_ids=list(request.reference_ids) if request else [],
    )

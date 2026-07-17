"""Text-to-image product service (validation, provider call, chat persistence)."""

from __future__ import annotations

import logging
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.gateways import image_gateway, mock_llm
from app.gateways.storage_gateway import UnconfiguredStorageGateway, get_storage_gateway
from app.models.orm import Message, User
from app.repositories import attachments as attachments_repo
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.services import plan as plan_service
from app.services import quota as quota_service
from app.services.attachment_content import (
    MAX_ATTACHMENT_SIZE,
    bytes_match_claimed,
    is_image_content_type,
    normalize_content_type,
)
from app.services.model_catalog import get as get_model

logger = logging.getLogger(__name__)

_MAX_PROMPT_LEN = 2000
_USER_MESSAGE_PREFIX = "Generate image: "
_IMAGE_MODEL_ALIAS = "image-gen-model"

AspectRatio = Literal["1:1", "16:9", "9:16", "4:3", "3:4"]
_ALLOWED_ASPECT_RATIOS: frozenset[str] = frozenset({"1:1", "16:9", "9:16", "4:3", "3:4"})


class ImageGenerationError(Exception):
    """Domain failure for image generation; router maps status_code → HTTP."""

    def __init__(self, detail: str, *, status_code: int) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def normalize_aspect_ratio(value: str | None) -> AspectRatio | None:
    if not value:
        return None
    trimmed = value.strip()
    if trimmed in _ALLOWED_ASPECT_RATIOS:
        return trimmed  # type: ignore[return-value]
    return None


async def generate_image(
    settings: Settings,
    *,
    prompt: str,
    aspect_ratio: str | None = None,
) -> tuple[bytes, str] | None:
    """Return (image_bytes, content_type) or None on failure."""
    if not settings.image_generation_enabled:
        return None
    cleaned = prompt.strip()
    if not cleaned or len(cleaned) > _MAX_PROMPT_LEN:
        logger.warning("Image generation rejected: prompt length=%s", len(cleaned))
        return None
    if mock_llm.should_mock_llm(settings):
        return mock_llm.mock_image_bytes(), "image/png"
    if not settings.openrouter_api_key:
        return None

    model = (settings.image_generation_model or "black-forest-labs/flux.2-klein-4b").strip()
    return await image_gateway.generate_via_openrouter(
        settings,
        prompt=cleaned,
        model=model,
        aspect_ratio=normalize_aspect_ratio(aspect_ratio),
    )


async def generate_for_chat(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    prompt: str,
    aspect_ratio: str | None = None,
) -> tuple[Message, Message]:
    """Plan/quota/storage/persist path for POST /images/generate.

    Returns (user_message, assistant_message). Raises ImageGenerationError on
    expected failures; unexpected exceptions are re-raised after quota refund.
    """
    if not settings.image_generation_enabled:
        raise ImageGenerationError("Not available", status_code=404)
    if not settings.attachments_enabled:
        raise ImageGenerationError("Attachments are disabled", status_code=503)
    if not plan_service.is_pro(user):
        raise ImageGenerationError("Image generation requires Pro", status_code=403)

    chat = await chats_repo.get_by_id(session, chat_id, user.id)
    if chat is None:
        raise ImageGenerationError("Chat not found", status_code=404)

    gateway = get_storage_gateway(settings)
    if isinstance(gateway, UnconfiguredStorageGateway):
        raise ImageGenerationError("Attachment storage is not configured", status_code=503)

    redis = get_redis_client()
    daily_limit = quota_service.image_generation_limit_for_user(user, settings)
    if not await quota_service.reserve_image_generation(redis, user.id, limit=daily_limit):
        raise ImageGenerationError(
            quota_service.image_generation_limit_exceeded_message(user),
            status_code=429,
        )

    cleaned = prompt.strip()
    if not cleaned:
        await quota_service.refund_image_generation(redis, user.id)
        raise ImageGenerationError("Prompt is required", status_code=400)

    try:
        generated = await generate_image(
            settings,
            prompt=cleaned,
            aspect_ratio=aspect_ratio,
        )
        if not generated:
            raise ImageGenerationError("Could not generate image", status_code=502)
        image_bytes, content_type = generated
        content_type = normalize_content_type(content_type)
        # BUG FIX: last-line-of-defense size check, matching the presign +
        # actual-bytes double-check every normal attachment upload gets in
        # routers/attachments.py. The gateway already rejects an oversized
        # provider response, but this keeps the invariant enforced here too
        # rather than trusting it was applied upstream.
        if len(image_bytes) > MAX_ATTACHMENT_SIZE:
            raise ImageGenerationError(
                "Generated image exceeds the maximum allowed size",
                status_code=502,
            )
        if not is_image_content_type(content_type):
            raise ImageGenerationError("Generated file is not an image", status_code=502)
        if not bytes_match_claimed(content_type, image_bytes):
            raise ImageGenerationError("Generated image failed validation", status_code=502)

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
            chat_id=chat_id,
            user_id=user.id,
            role="user",
            content=f"{_USER_MESSAGE_PREFIX}{cleaned}",
        )
        image_marker = f"[Image: /attachments/{attachment_id}/file]"
        assistant_message = await messages_repo.create(
            session,
            chat_id=chat_id,
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
            raise ImageGenerationError("Could not link generated image", status_code=500)
    except ImageGenerationError as exc:
        if exc.status_code not in (403, 429):
            await quota_service.refund_image_generation(redis, user.id)
        raise
    except Exception:
        await quota_service.refund_image_generation(redis, user.id)
        raise

    return user_message, assistant_message

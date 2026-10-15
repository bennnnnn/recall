"""Image generation request and response models."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.models.schemas.chats import MessageOut


class ImageGenerateIn(BaseModel):
    chat_id: UUID
    prompt: str = Field(min_length=1, max_length=2000)
    user_message: str | None = Field(default=None, max_length=2000)
    aspect_ratio: str | None = Field(default=None, max_length=16)
    reference_attachment_ids: list[UUID] = Field(default_factory=list, max_length=2)


class ImageGenerateOut(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut


class ImageIntentIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ImageIntentOut(BaseModel):
    """The subject that owns a composer turn; ``None`` leaves it to image generation."""

    subject: Literal["math", "physics", "chemistry"] | None

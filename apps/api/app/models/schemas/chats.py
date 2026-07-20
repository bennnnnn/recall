from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.validation import normalize_chat_title, validate_user_alias
from app.models.schemas.common import MessageFeedback, MessageRole, QuizMode


class ChatCreate(BaseModel):
    model: str = "auto"
    project_id: UUID | None = None
    quiz_mode: QuizMode | None = None

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        validate_user_alias(value, allow_auto=True)
        return value


class ChatRename(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class PinUpdate(BaseModel):
    pinned: bool


class ArchiveUpdate(BaseModel):
    archived: bool


class FeedbackUpdate(BaseModel):
    feedback: MessageFeedback | None = None


class ChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    model: str
    pinned: bool = False
    archived: bool = False
    project_id: UUID | None = None
    quiz_mode: QuizMode | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def sanitize_title(self) -> Self:
        self.title = normalize_chat_title(self.title)
        return self


class ChatListOut(BaseModel):
    pinned: list[ChatOut] = Field(default_factory=list)
    today: list[ChatOut] = Field(default_factory=list)
    yesterday: list[ChatOut] = Field(default_factory=list)
    last_7_days: list[ChatOut] = Field(default_factory=list)
    this_month: list[ChatOut] = Field(default_factory=list)
    older: list[ChatOut] = Field(default_factory=list)
    archived: list[ChatOut] = Field(default_factory=list)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: MessageRole
    content: str
    model: str | None
    feedback: MessageFeedback | None = None
    created_at: datetime


class MessagePageOut(BaseModel):
    messages: list[MessageOut]
    has_more: bool


class ChatMessageRequest(BaseModel):
    # Cap matches EditMessageRequest — without it a client can push a
    # multi-MB body that bloats the prompt, DB row, and memory-extraction
    # job. 32k chars is well beyond any realistic chat turn.
    content: str = Field(default="", max_length=32_000)
    model: str | None = None
    # Cap per turn — unbounded lists let a client force huge DB/RAG work.
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=10)
    client_timezone: str | None = Field(default=None, max_length=64)
    client_location: str | None = Field(default=None, max_length=200)
    client_latitude: float | None = Field(default=None, ge=-90, le=90)
    client_longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        validate_user_alias(value, allow_auto=True)
        return value


class EditMessageRequest(BaseModel):
    message_id: UUID
    content: str = Field(min_length=1, max_length=32_000)
    model: str | None = None
    client_timezone: str | None = Field(default=None, max_length=64)
    client_location: str | None = Field(default=None, max_length=200)
    client_latitude: float | None = Field(default=None, ge=-90, le=90)
    client_longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        validate_user_alias(value, allow_auto=True)
        return value


class TitleGenerationResult(BaseModel):
    title: str = Field(min_length=3, max_length=80)


class ImageGenerateIn(BaseModel):
    chat_id: UUID
    prompt: str = Field(min_length=1, max_length=2000)
    aspect_ratio: str | None = Field(default=None, max_length=16)


class ImageGenerateOut(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut


class SearchResultItem(BaseModel):
    match_type: Literal["message", "title"] = "message"
    message_id: UUID | None = None
    chat_id: UUID
    chat_title: str | None
    content: str
    role: str
    created_at: datetime


class SearchResults(BaseModel):
    results: list[SearchResultItem] = Field(default_factory=list)
    total: int = 0

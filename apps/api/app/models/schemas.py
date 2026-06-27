from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MessageRole = Literal["user", "assistant", "system"]
MemoryType = Literal["profile", "preference", "project", "fact", "focus"]
ModelAlias = Literal["auto", "free-chat", "smart-chat", "max-chat", "title-model", "memory-model"]
ResponseStyle = Literal["short", "balanced", "detailed"]
MessageFeedback = Literal["up", "down"]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str | None
    avatar_url: str | None
    default_model: str
    response_style: str
    memory_enabled: bool
    custom_instructions: str | None = None
    locale: str = "en"
    created_at: datetime


class UserUpdate(BaseModel):
    name: str | None = None
    default_model: ModelAlias | None = None
    response_style: ResponseStyle | None = None
    memory_enabled: bool | None = None
    custom_instructions: str | None = None
    locale: str | None = None


class GoogleAuthRequest(BaseModel):
    id_token: str


class DevAuthRequest(BaseModel):
    email: str = "dev@recall.local"
    name: str = "Dev User"


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ChatCreate(BaseModel):
    model: ModelAlias = "free-chat"


class ChatRename(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class PinUpdate(BaseModel):
    pinned: bool


class FeedbackUpdate(BaseModel):
    feedback: MessageFeedback | None = None


class ChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    model: str
    pinned: bool = False
    created_at: datetime
    updated_at: datetime


class ChatListOut(BaseModel):
    pinned: list[ChatOut] = Field(default_factory=list)
    today: list[ChatOut] = Field(default_factory=list)
    yesterday: list[ChatOut] = Field(default_factory=list)
    earlier: list[ChatOut] = Field(default_factory=list)


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


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: MemoryType
    text: str
    confidence: float | None
    created_at: datetime
    updated_at: datetime


class UsageOut(BaseModel):
    date: str
    input_tokens: int
    output_tokens: int
    daily_limit: int
    remaining: int


class ModelInfo(BaseModel):
    id: str
    label: str
    provider: str
    description: str
    tier: str
    available: bool
    input_price_per_m: float | None = None
    output_price_per_m: float | None = None


class ChatMessageRequest(BaseModel):
    content: str = ""
    model: ModelAlias | None = None


class TitleGenerationResult(BaseModel):
    title: str = Field(min_length=3, max_length=80)


class MemoryExtractionItem(BaseModel):
    type: MemoryType
    text: str = Field(min_length=3, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)


class MemoryExtractionResult(BaseModel):
    memories: list[MemoryExtractionItem] = Field(default_factory=list)


class TodoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    checked: bool
    chat_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class TodoCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    chat_id: UUID | None = None


class TodoUpdate(BaseModel):
    content: str | None = None
    checked: bool | None = None


class SearchResultItem(BaseModel):
    message_id: UUID
    chat_id: UUID
    chat_title: str | None
    content: str
    role: str
    created_at: datetime


class SearchResults(BaseModel):
    results: list[SearchResultItem] = Field(default_factory=list)
    total: int = 0


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    content: str
    category: str
    is_builtin: bool
    created_at: datetime
    updated_at: datetime


class TemplateCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    category: str = Field(default="general", max_length=50)


class TemplateUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None


class SuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    text: str
    category: str
    source: str
    created_at: datetime


class SuggestionItem(BaseModel):
    text: str = Field(min_length=3, max_length=200)
    category: str = "general"


class SuggestionGenerationResult(BaseModel):
    items: list[SuggestionItem] = Field(default_factory=list)

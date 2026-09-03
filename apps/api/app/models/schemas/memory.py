from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.schemas.common import MemoryType


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: MemoryType
    text: str
    confidence: float | None
    created_at: datetime
    updated_at: datetime
    source_chat_id: UUID | None = None
    source_chat_title: str | None = None

    @field_validator("source_chat_id", mode="before")
    @classmethod
    def _coerce_source_chat_id(cls, value: object) -> UUID | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            return None

    @field_validator("source_chat_title", mode="before")
    @classmethod
    def _coerce_source_chat_title(cls, value: object) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        return cleaned or None


class MemoryUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class MemorySectionItem(BaseModel):
    type: MemoryType
    summary: str = Field(min_length=3, max_length=4000)
    confidence: float = Field(ge=0.0, le=1.0)


class MemorySectionUpdateResult(BaseModel):
    sections: list[MemorySectionItem] = Field(default_factory=list)

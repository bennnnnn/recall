from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.schemas.common import MemoryType

MEMORY_TEXT_MAX_LENGTH = 4000
# A persisted section may include the server's "As of YYYY-MM-DD: " prefix.
MEMORY_FACT_TEXT_MAX_LENGTH = MEMORY_TEXT_MAX_LENGTH + 18


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: MemoryType
    text: str
    confidence: float | None
    created_at: datetime
    updated_at: datetime


class MemoryUpdate(BaseModel):
    text: str = Field(min_length=1, max_length=MEMORY_TEXT_MAX_LENGTH)


class MemorySectionItem(BaseModel):
    type: MemoryType
    summary: str = Field(min_length=3, max_length=MEMORY_TEXT_MAX_LENGTH)
    confidence: float = Field(ge=0.0, le=1.0)


class MemorySectionUpdateResult(BaseModel):
    sections: list[MemorySectionItem] = Field(default_factory=list)

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.schemas.common import (
    MemoryOpKind,
    MemorySensitivity,
    MemoryStatus,
    MemoryType,
)

MEMORY_TEXT_MAX_LENGTH = 4000
# A persisted section may include the server's "As of YYYY-MM-DD: " prefix.
MEMORY_FACT_TEXT_MAX_LENGTH = MEMORY_TEXT_MAX_LENGTH + 18


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: MemoryType
    topic: str = "notes"
    text: str
    confidence: float | None
    status: MemoryStatus = "active"
    sensitivity: MemorySensitivity = "normal"
    importance: float | None = None
    last_confirmed_at: datetime | None = None
    source_chat_id: UUID | None = None
    source_chat_title: str | None = None
    source_message_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class MemoryUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=MEMORY_TEXT_MAX_LENGTH)
    status: MemoryStatus | None = None


class MemorySectionItem(BaseModel):
    """Legacy whole-section rewrite (pair-merge still uses summary + confidence)."""

    type: MemoryType
    summary: str = Field(default="", max_length=MEMORY_TEXT_MAX_LENGTH)
    confidence: float = Field(ge=0.0, le=1.0)


class MemorySectionUpdateResult(BaseModel):
    sections: list[MemorySectionItem] = Field(default_factory=list)


class MemoryFactOp(BaseModel):
    op: MemoryOpKind
    type: MemoryType
    text: str = Field(default="", max_length=MEMORY_TEXT_MAX_LENGTH)
    confidence: float = Field(ge=0.0, le=1.0)
    sensitivity: MemorySensitivity = "normal"
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    match_text: str | None = Field(default=None, max_length=MEMORY_TEXT_MAX_LENGTH)
    # The memory document (topics.py). Unknown keys fall back to the type's
    # default, and long titles are trimmed, so neither fails the whole op.
    topic: str | None = None
    topic_title: str | None = None
    topic_summary: str | None = None


MEMORY_REPLY_MAX_LENGTH = 400


class MemoryFactUpdateResult(BaseModel):
    ops: list[MemoryFactOp] = Field(default_factory=list)
    # A direct memory edit also says, in a sentence, what changed.
    reply: str = Field(default="", max_length=MEMORY_REPLY_MAX_LENGTH)


class MemoryDocumentOut(BaseModel):
    """One memory document: every fact with the same topic."""

    key: str
    group: Literal["you", "topics", "areas"]
    title: str
    summary: str
    updated_at: datetime | None
    facts: list[MemoryOut]


class MemoryDocumentsOut(BaseModel):
    documents: list[MemoryDocumentOut]
    # True while memory reads the user's recent chats for the first time.
    scanning: bool = False


MEMORY_INSTRUCTION_MAX_LENGTH = 500


class MemoryInstructIn(BaseModel):
    instruction: str = Field(min_length=1, max_length=MEMORY_INSTRUCTION_MAX_LENGTH)
    # The document the user is looking at, if any.
    topic: str | None = Field(default=None, max_length=64)


class MemoryInstructOut(BaseModel):
    reply: str
    applied: int
    documents: list[MemoryDocumentOut]

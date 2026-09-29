from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HomeUrgentTodo(BaseModel):
    id: UUID
    content: str
    topic: str
    due_at: datetime
    minutes_until: int


class HomeStarter(BaseModel):
    id: str | None = None
    text: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=2000)
    kind: Literal["time", "memory", "chat", "general", "todo"] = "general"
    # When set, tapping this starter should open the existing chat (instead
    # of creating a new one) so the prior conversation context is loaded.
    # Used by the "Pick up where we left off" chat starter.
    chat_id: UUID | None = None


class HomeScreenOut(BaseModel):
    greeting: str
    subtitle: str | None = None
    urgent_todos: list[HomeUrgentTodo] = Field(default_factory=list)
    starters: list[HomeStarter] = Field(default_factory=list)


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

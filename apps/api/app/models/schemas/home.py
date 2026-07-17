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
    kind: Literal["time", "memory", "chat", "general", "todo", "project"] = "general"


class HomeProjectHighlight(BaseModel):
    project_id: UUID
    title: str
    kind: Literal["language", "trivia"]
    daily_goal: int = Field(ge=1, le=50)
    mastered_today: int = Field(ge=0)
    missed_today: int = Field(ge=0, default=0)
    cue: Literal[
        "start",
        "continue",
        "not_started_today",
        "missed_yesterday",
        "finish_pending",
    ]
    streak_days: int = 0
    days_inactive: int | None = None
    due_for_review: int = 0
    suggested_level: Literal["up", "down"] | None = None


class HomeScreenOut(BaseModel):
    greeting: str
    subtitle: str | None = None
    project_highlight: HomeProjectHighlight | None = None
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

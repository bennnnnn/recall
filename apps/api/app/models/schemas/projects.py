from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Product learning kinds: English vocabulary + general knowledge.
# `vocabulary` is accepted as a write alias and normalized to `language`.
ProjectKind = Literal["language", "vocabulary", "trivia"]

LanguageLevel = Literal["level1", "level2", "level3", "level4", "level5", "level6"]

VocabStatus = Literal["new", "learning", "mastered"]


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    kind: ProjectKind
    target_language: str = "en"
    native_language: str | None = None
    level: LanguageLevel = "level1"
    daily_goal: int | None = None
    archived: bool
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    kind: ProjectKind = "language"
    target_language: str = Field(default="en", max_length=10)
    native_language: str | None = Field(default=None, max_length=10)
    level: LanguageLevel = "level1"
    daily_goal: int | None = Field(default=None, ge=1, le=50)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    kind: ProjectKind | None = None
    target_language: str | None = Field(default=None, max_length=10)
    native_language: str | None = Field(default=None, max_length=10)
    level: LanguageLevel | None = None
    daily_goal: int | None = Field(default=None, ge=1, le=50)
    archived: bool | None = None


class ProjectItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    list_title: str
    content: str
    note: str | None
    definition: str | None
    example_sentence: str | None
    status: VocabStatus
    mastered: bool
    mastered_at: datetime | None
    last_reviewed_at: datetime | None
    last_incorrect_at: datetime | None = None
    review_count: int
    ease_factor: float = 2.5
    interval_days: int = 0
    due_at: datetime | None = None
    pronunciation_url: str | None
    created_at: datetime


class ProjectStats(BaseModel):
    total: int = 0
    new_count: int = 0
    learning_count: int = 0
    mastered_count: int = 0
    added_this_week: int = 0
    due_for_review: int = 0
    mastered_today: int = 0
    missed_today: int = 0
    pending_today: int = 0
    last_mastery_at: datetime | None = None
    streak_days: int = 0
    days_inactive: int | None = None
    quiz_accuracy_pct: int | None = Field(default=None, ge=0, le=100)
    suggested_level: Literal["up", "down"] | None = None


class ProjectListOut(ProjectOut):
    """Project list row; learning kinds include lightweight stats for list cards."""

    stats: ProjectStats | None = None


DailyHistoryStatus = Literal["complete", "partial", "skipped", "today", "inactive"]


class ProjectDailyHistoryDay(BaseModel):
    date: str
    weekday: int = Field(ge=0, le=6)
    mastered_count: int = Field(ge=0)
    missed_count: int = Field(ge=0, default=0)
    daily_goal: int = Field(ge=1)
    goal_met: bool = False
    status: DailyHistoryStatus


class ProjectListGroup(BaseModel):
    list_title: str
    items: list[ProjectItemOut] = Field(default_factory=list)


class ProjectItemUpdate(BaseModel):
    status: VocabStatus | None = None
    definition: str | None = Field(default=None, max_length=2000)

    @field_validator("definition")
    @classmethod
    def validate_definition(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class ProjectDetailOut(ProjectOut):
    mastered_count: int = 0
    total_count: int = 0
    stats: ProjectStats = Field(default_factory=ProjectStats)
    daily_history: list[ProjectDailyHistoryDay] = Field(default_factory=list)
    daily_items_by_date: dict[str, list[ProjectItemOut]] = Field(default_factory=dict)
    daily_missed_by_date: dict[str, list[ProjectItemOut]] = Field(default_factory=dict)
    lists: list[ProjectListGroup] = Field(default_factory=list)


class ProjectActionItem(BaseModel):
    action: Literal[
        "create_project",
        "delete_project",
        "set_description",
        "set_level",
        "add",
        "start_learning",
        "master",
        "unmaster",
        "delete",
        "delete_list",
    ]
    project_title: str = Field(min_length=1, max_length=200)
    kind: ProjectKind | None = None
    description: str | None = Field(default=None, max_length=4000)
    level: LanguageLevel | None = None
    list_title: str = Field(default="General", max_length=200)
    content: str = Field(default="", max_length=1000)
    note: str | None = Field(default=None, max_length=2000)
    definition: str | None = Field(default=None, max_length=2000)
    example_sentence: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_action_fields(self) -> Self:
        if self.action in ("delete_project", "delete_list", "set_level"):
            if self.action == "set_level" and not self.level:
                raise ValueError("set_level requires level")
            return self
        if self.action == "create_project":
            if not self.kind:
                raise ValueError("create_project requires kind")
            return self
        if self.action == "set_description":
            if not (self.description or "").strip():
                raise ValueError("set_description requires description")
            return self
        if self.action in ("start_learning", "master", "unmaster", "delete"):
            if not self.content.strip():
                raise ValueError("content is required for this action")
            return self
        if self.action == "add":
            if not self.content.strip():
                raise ValueError("content is required for add")
            return self
        if not self.content.strip():
            raise ValueError("content is required for this action")
        return self


class ProjectExtractionResult(BaseModel):
    actions: list[ProjectActionItem] = Field(default_factory=list)

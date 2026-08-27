from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Product learning kinds: vocabulary (one class per target language).
# `vocabulary` is accepted as a write alias and normalized to `language`.
LearningKind = Literal["language", "vocabulary"]
ProjectKind = LearningKind

LanguageLevel = Literal["level1", "level2", "level3", "level4", "level5", "level6"]

VocabStatus = Literal["new", "learning", "mastered"]


class PathChapterProgress(BaseModel):
    title: str
    domain: str = ""
    mastered: int = 0
    total: int = 0
    complete: bool = False


class LearningOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, title="ProjectOut")

    id: UUID
    title: str
    description: str | None
    kind: LearningKind
    target_language: str = "en"
    native_language: str | None = None
    level: LanguageLevel = "level1"
    daily_goal: int | None = None
    archived: bool
    created_at: datetime
    updated_at: datetime
    learning_path: list[str] = Field(default_factory=list)

    @field_validator("learning_path", mode="before")
    @classmethod
    def coerce_learning_path(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        titles: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                continue
            title = item.strip()[:200]
            if not title:
                continue
            key = title.casefold()
            if key in seen:
                continue
            seen.add(key)
            titles.append(title)
        return titles


class LearningCreate(BaseModel):
    model_config = ConfigDict(title="ProjectCreate")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    kind: LearningKind = "language"
    target_language: str = Field(default="en", max_length=10)
    native_language: str | None = Field(default=None, max_length=10)
    level: LanguageLevel = "level1"
    daily_goal: int | None = Field(default=None, ge=1, le=50)


class LearningUpdate(BaseModel):
    model_config = ConfigDict(title="ProjectUpdate")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    kind: LearningKind | None = None
    target_language: str | None = Field(default=None, max_length=10)
    native_language: str | None = Field(default=None, max_length=10)
    level: LanguageLevel | None = None
    daily_goal: int | None = Field(default=None, ge=1, le=50)
    archived: bool | None = None


class LearningItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, title="ProjectItemOut")

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


class LearningStats(BaseModel):
    model_config = ConfigDict(title="ProjectStats")

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


class LearningListOut(LearningOut):
    """Learning list row; language classes include lightweight stats for list cards."""

    model_config = ConfigDict(from_attributes=True, title="ProjectListOut")

    stats: LearningStats | None = None


DailyHistoryStatus = Literal["complete", "partial", "skipped", "today", "inactive"]


class LearningDailyHistoryDay(BaseModel):
    model_config = ConfigDict(title="ProjectDailyHistoryDay")

    date: str
    weekday: int = Field(ge=0, le=6)
    mastered_count: int = Field(ge=0)
    missed_count: int = Field(ge=0, default=0)
    daily_goal: int = Field(ge=1)
    goal_met: bool = False
    status: DailyHistoryStatus


class LearningListGroup(BaseModel):
    model_config = ConfigDict(title="ProjectListGroup")

    list_title: str
    items: list[LearningItemOut] = Field(default_factory=list)


class LearningItemUpdate(BaseModel):
    model_config = ConfigDict(title="ProjectItemUpdate")

    status: VocabStatus | None = None
    definition: str | None = Field(default=None, max_length=2000)
    was_correct: bool | None = None

    @field_validator("definition")
    @classmethod
    def validate_definition(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class LearningDetailOut(LearningOut):
    model_config = ConfigDict(from_attributes=True, title="ProjectDetailOut")

    mastered_count: int = 0
    total_count: int = 0
    stats: LearningStats = Field(default_factory=LearningStats)
    daily_history: list[LearningDailyHistoryDay] = Field(default_factory=list)
    daily_items_by_date: dict[str, list[LearningItemOut]] = Field(default_factory=dict)
    daily_missed_by_date: dict[str, list[LearningItemOut]] = Field(default_factory=dict)
    lists: list[LearningListGroup] = Field(default_factory=list)
    path_progress: list[PathChapterProgress] = Field(default_factory=list)
    up_next: str | None = None


class LearningActionItem(BaseModel):
    model_config = ConfigDict(title="ProjectActionItem")

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
    kind: LearningKind | None = None
    target_language: str | None = Field(default=None, max_length=10)
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
        if not self.content.strip():
            raise ValueError("content is required for add")
        return self


class LearningExtractionResult(BaseModel):
    model_config = ConfigDict(title="ProjectExtractionResult")

    actions: list[LearningActionItem] = Field(default_factory=list)


ProjectOut = LearningOut
ProjectCreate = LearningCreate
ProjectUpdate = LearningUpdate
ProjectItemOut = LearningItemOut
ProjectStats = LearningStats
ProjectListOut = LearningListOut
ProjectDailyHistoryDay = LearningDailyHistoryDay
ProjectListGroup = LearningListGroup
ProjectItemUpdate = LearningItemUpdate
ProjectDetailOut = LearningDetailOut
ProjectActionItem = LearningActionItem
ProjectExtractionResult = LearningExtractionResult

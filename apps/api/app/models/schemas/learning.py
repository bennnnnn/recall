from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

# Product learning kinds: vocabulary (one class per target language).
# `vocabulary` is accepted as a write alias and normalized to `language`.
LearningKind = Literal["language"]

VocabStatus = Literal["new", "learning", "mastered"]


def coerce_learning_kind(value: object) -> object:
    if isinstance(value, str) and value.strip().casefold() == "vocabulary":
        return "language"
    return value


class PathChapterProgress(BaseModel):
    title: str
    domain: str = ""
    mastered: int = 0
    total: int = 0
    complete: bool = False


class LearningOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, title="LearningOut")

    id: UUID
    title: str
    description: str | None
    kind: LearningKind
    target_language: str = "en"
    native_language: str | None = None
    daily_goal: int | None = None
    archived: bool
    created_at: datetime
    updated_at: datetime
    learning_path: list[str] = Field(default_factory=list)

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, value: object) -> object:
        return coerce_learning_kind(value)

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
    model_config = ConfigDict(title="LearningCreate")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    kind: LearningKind = "language"
    target_language: str = Field(default="en", max_length=10)
    native_language: str | None = Field(default=None, max_length=10)
    daily_goal: int | None = Field(default=None, ge=1, le=50)

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, value: object) -> object:
        return coerce_learning_kind(value)


class LearningUpdate(BaseModel):
    model_config = ConfigDict(title="LearningUpdate")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    kind: LearningKind | None = None
    target_language: str | None = Field(default=None, max_length=10)
    native_language: str | None = Field(default=None, max_length=10)
    daily_goal: int | None = Field(default=None, ge=1, le=50)
    archived: bool | None = None

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, value: object) -> object:
        return coerce_learning_kind(value)


class LearningItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, title="LearningItemOut")

    id: UUID
    list_title: str
    content: str
    note: str | None
    definition: str | None
    example_sentence: str | None
    ipa: str | None = None
    part_of_speech: str | None = None
    vocabulary_kind: str = "word"
    verb_kind: str | None = None
    noun_kind: str | None = None
    simple_gloss: str | None = None
    status: VocabStatus
    mastered: bool
    mastered_at: datetime | None
    last_reviewed_at: datetime | None
    last_completed_at: datetime | None = None
    last_incorrect_at: datetime | None = None
    review_count: int
    ease_factor: float = 2.5
    interval_days: int = 0
    due_at: datetime | None = None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def example_sentences(self) -> list[str]:
        return [
            line.strip()
            for line in (self.example_sentence or self.note or "").splitlines()
            if line.strip()
        ]


class LearningPracticeIn(BaseModel):
    attempt_id: UUID
    was_correct: bool
    completes_word: bool

    @model_validator(mode="after")
    def validate_completion(self) -> Self:
        if self.completes_word and not self.was_correct:
            raise ValueError("Only a correct answer can complete a word")
        return self


class LearningPracticeOut(BaseModel):
    item: LearningItemOut
    recorded: bool
    newly_mastered: bool


class LearningStats(BaseModel):
    model_config = ConfigDict(title="LearningStats")

    total: int = 0
    new_count: int = 0
    learning_count: int = 0
    mastered_count: int = 0
    added_this_week: int = 0
    due_for_review: int = 0
    mastered_today: int = 0
    newly_mastered_today: int = 0
    completed_today: int = 0
    attempted_today: int = 0
    incorrect_today: int = 0
    last_study_at: datetime | None = None
    missed_today: int = 0
    pending_today: int = 0
    last_mastery_at: datetime | None = None
    streak_days: int = 0
    days_inactive: int | None = None
    quiz_accuracy_pct: int | None = Field(default=None, ge=0, le=100)


class LearningListOut(LearningOut):
    """Learning list row; language classes include lightweight stats for list cards."""

    model_config = ConfigDict(from_attributes=True, title="LearningListOut")

    stats: LearningStats | None = None


DailyHistoryStatus = Literal["complete", "partial", "skipped", "today", "inactive"]


class LearningDailyHistoryDay(BaseModel):
    model_config = ConfigDict(title="LearningDailyHistoryDay")

    date: str
    weekday: int = Field(ge=0, le=6)
    mastered_count: int = Field(ge=0)
    missed_count: int = Field(ge=0, default=0)
    completed_count: int = Field(ge=0, default=0)
    attempted_count: int = Field(ge=0, default=0)
    daily_goal: int = Field(ge=1)
    goal_met: bool = False
    status: DailyHistoryStatus


class LearningListGroup(BaseModel):
    model_config = ConfigDict(title="LearningListGroup")

    list_title: str
    items: list[LearningItemOut] = Field(default_factory=list)


class LearningDetailOut(LearningOut):
    model_config = ConfigDict(from_attributes=True, title="LearningDetailOut")

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
    model_config = ConfigDict(title="LearningActionItem")

    action: Literal[
        "create_project",
        "delete_project",
        "set_description",
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
    list_title: str = Field(default="General", max_length=200)
    content: str = Field(default="", max_length=1000)
    note: str | None = Field(default=None, max_length=2000)
    definition: str | None = Field(default=None, max_length=2000)
    example_sentence: str | None = Field(default=None, max_length=2000)

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, value: object) -> object:
        return coerce_learning_kind(value)

    @model_validator(mode="after")
    def validate_action_fields(self) -> Self:
        if self.action in ("delete_project", "delete_list"):
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
    model_config = ConfigDict(title="LearningExtractionResult")

    actions: list[LearningActionItem] = Field(default_factory=list)

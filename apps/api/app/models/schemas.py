from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services import model_catalog

MessageRole = Literal["user", "assistant", "system"]
MemoryType = Literal["profile", "preference", "project", "fact", "focus"]
ResponseStyle = Literal["short", "balanced", "detailed"]
ResponseTone = Literal["funny", "professional", "casual", "soft"]
MessageFeedback = Literal["up", "down"]
QuizMode = Literal["exam", "chat"]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str | None
    avatar_url: str | None
    default_model: str
    plan: str = "free"
    enabled_models: list[str] | None = None
    response_style: str
    response_tone: str = "funny"
    memory_enabled: bool
    push_notifications_enabled: bool = True
    email_reminders_enabled: bool = False
    reminder_lead_minutes: int = 10
    locale: str = "en"
    timezone: str = "UTC"
    location: str | None = None
    location_enabled: bool = False
    custom_instructions: str | None = None
    created_at: datetime


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    default_model: str | None = None
    enabled_models: list[str] | None = None
    response_style: ResponseStyle | None = None
    response_tone: ResponseTone | None = None
    memory_enabled: bool | None = None
    push_notifications_enabled: bool | None = None
    email_reminders_enabled: bool | None = None
    reminder_lead_minutes: int | None = Field(default=None, ge=5, le=60)
    locale: str | None = None
    timezone: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=128)
    location_enabled: bool | None = None
    custom_instructions: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from app.services.profile import normalize_display_name

        normalized = normalize_display_name(value)
        if not normalized:
            raise ValueError("Name must be 1\u201380 characters.")
        return normalized

    @field_validator("default_model")
    @classmethod
    def validate_default_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        model_catalog.validate_user_alias(value, allow_auto=True)
        return value

    @field_validator("enabled_models")
    @classmethod
    def validate_enabled_models(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("Turn on Auto or at least one model.")
        for entry in value:
            if entry == "auto":
                continue
            model_catalog.validate_user_alias(entry)
        return value

    @field_validator("reminder_lead_minutes")
    @classmethod
    def validate_reminder_lead_minutes(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value not in {5, 10, 15, 30, 60}:
            raise ValueError("reminder_lead_minutes must be 5, 10, 15, 30, or 60")
        return value

    @field_validator("custom_instructions")
    @classmethod
    def validate_custom_instructions(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, value: str | None) -> str | None:
        if value is None:
            return None
        # Empty/whitespace locale → no change (treat as unset), matching the
        # custom_instructions blank-clears behavior.
        if not value.strip():
            return None
        from app.services.locale import LOCALE_NAMES, normalize_locale_code

        code = normalize_locale_code(value)
        if code not in LOCALE_NAMES:
            supported = ", ".join(sorted(LOCALE_NAMES))
            raise ValueError(f"Unsupported locale code. Supported: {supported}.")
        return code


class GoogleAuthRequest(BaseModel):
    id_token: str


class AppleAuthRequest(BaseModel):
    id_token: str
    name: str | None = None


class DevAuthRequest(BaseModel):
    email: str = "dev@recall.local"
    name: str = "bini"


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class ChatCreate(BaseModel):
    model: str = "auto"
    project_id: UUID | None = None
    quiz_mode: QuizMode | None = None

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        model_catalog.validate_user_alias(value, allow_auto=True)
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
        from app.services.chat_titles import normalize_chat_title

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
    used_tokens: int
    remaining: int


class ModelInfo(BaseModel):
    id: str
    label: str
    description: str
    tier: str
    plan_access: str = "pro"
    available: bool
    input_price_per_m: float | None = None
    output_price_per_m: float | None = None
    quota_multiplier: float = 1.0
    healthy: bool = True
    latency_p50_ms: int | None = None
    health_samples: int = 0


class ChatMessageRequest(BaseModel):
    content: str = ""
    model: str | None = None
    attachment_ids: list[UUID] = Field(default_factory=list)
    client_timezone: str | None = Field(default=None, max_length=64)
    client_location: str | None = Field(default=None, max_length=200)
    client_latitude: float | None = Field(default=None, ge=-90, le=90)
    client_longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        model_catalog.validate_user_alias(value, allow_auto=True)
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
        model_catalog.validate_user_alias(value, allow_auto=True)
        return value


class TitleGenerationResult(BaseModel):
    title: str = Field(min_length=3, max_length=80)


class MemorySectionItem(BaseModel):
    type: MemoryType
    summary: str = Field(min_length=3, max_length=4000)
    confidence: float = Field(ge=0.0, le=1.0)


class MemorySectionUpdateResult(BaseModel):
    sections: list[MemorySectionItem] = Field(default_factory=list)


class TodoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    topic: str
    checked: bool
    due_at: datetime | None = None
    sort_order: int | None = None
    chat_id: UUID | None = None
    project_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class TodoCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    topic: str = Field(default="General", min_length=1, max_length=200)
    chat_id: UUID | None = None
    project_id: UUID | None = None
    due_at: datetime | None = None


class TodoUpdate(BaseModel):
    content: str | None = None
    topic: str | None = Field(default=None, min_length=1, max_length=200)
    checked: bool | None = None
    due_at: datetime | None = None
    sort_order: int | None = None
    project_id: UUID | None = None


class TodoReorderItem(BaseModel):
    id: UUID
    sort_order: int = Field(ge=0)
    topic: str | None = Field(default=None, min_length=1, max_length=200)


class TodoReorderBody(BaseModel):
    items: list[TodoReorderItem] = Field(min_length=1, max_length=100)


class TodoActionItem(BaseModel):
    action: Literal[
        "add",
        "complete",
        "uncheck",
        "delete",
        "delete_list",
        "set_due",
        "clear_due",
    ]
    # Empty topic allowed for dated reminder adds (server defaults to Reminders).
    topic: str = Field(default="", max_length=200)
    content: str = Field(default="", max_length=1000)
    due_at: datetime | None = None

    @model_validator(mode="after")
    def validate_action_fields(self) -> Self:
        if self.action == "delete_list":
            if not self.topic.strip():
                raise ValueError("delete_list requires topic")
            return self
        if not self.content.strip():
            raise ValueError("content is required for this action")
        if self.action == "set_due" and self.due_at is None:
            raise ValueError("set_due requires due_at")
        # Dated reminder adds may omit topic; everything else needs a list title.
        if self.action == "add" and self.due_at is not None:
            return self
        if not self.topic.strip():
            raise ValueError("topic is required for this action")
        return self


class TodoExtractionResult(BaseModel):
    actions: list[TodoActionItem] = Field(default_factory=list)


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


class WebSearchClassification(BaseModel):
    needs_search: bool
    query: str | None = Field(
        default=None,
        description="Concise web search query when needs_search is true",
    )


class SpeechTranscriptionOut(BaseModel):
    text: str


class SpeechTranscriptionIn(BaseModel):
    audio_base64: str = Field(max_length=7_000_000)
    filename: str = "speech.m4a"


class SpeechTtsIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: str | None = Field(default=None, max_length=16)


class SpeechTtsOut(BaseModel):
    audio_base64: str
    content_type: str = "audio/mpeg"
    model: str = "tts-model"


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


class GoogleCalendarConnectRequest(BaseModel):
    server_auth_code: str = Field(min_length=8, max_length=4096)


class GoogleCalendarStatusOut(BaseModel):
    connected: bool
    email: str | None = None
    configured: bool = False
    can_write: bool = False


class CalendarEventProposalIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    start_at: datetime
    end_at: datetime
    location: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=2000)


class CalendarEventProposalOut(BaseModel):
    proposal_id: str
    title: str
    start_at: datetime
    end_at: datetime
    location: str | None = None


class CalendarConflictOut(BaseModel):
    event_id: str
    title: str
    start_at: datetime
    end_at: datetime | None = None


class CalendarConflictsOut(BaseModel):
    conflicts: list[CalendarConflictOut] = Field(default_factory=list)


class GoogleCalendarEventOut(BaseModel):
    id: str
    title: str
    start_at: datetime
    end_at: datetime | None = None
    location: str | None = None
    all_day: bool = False
    calendar_name: str | None = None


class GoogleCalendarEventsOut(BaseModel):
    events: list[GoogleCalendarEventOut] = Field(default_factory=list)
    load_error: str | None = None


class GoogleGmailConnectRequest(BaseModel):
    server_auth_code: str = Field(min_length=8, max_length=4096)


class GoogleGmailStatusOut(BaseModel):
    connected: bool
    email: str | None = None
    configured: bool = False
    last_sync_at: datetime | None = None


class SuggestedReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    due_at: datetime | None = None
    notes: str | None = None
    confidence: float
    source_snippet: str | None = None
    status: str
    created_at: datetime
    gmail_message_id: str


class SuggestedRemindersOut(BaseModel):
    reminders: list[SuggestedReminderOut] = Field(default_factory=list)
    pending_count: int = 0


class PushTokenIn(BaseModel):
    expo_push_token: str = Field(min_length=8, max_length=512)
    platform: str = Field(min_length=2, max_length=20)
    device_id: str | None = Field(default=None, max_length=128)


class AttachmentPresignIn(BaseModel):
    content_type: str = Field(min_length=3, max_length=128)
    size_bytes: int = Field(gt=0, le=10_485_760)


class AttachmentPresignOut(BaseModel):
    attachment_id: UUID
    upload_url: str
    storage_key: str
    headers: dict[str, str] = Field(default_factory=dict)
    api_upload: bool = False


class AttachmentOut(BaseModel):
    id: UUID
    content_type: str
    size_bytes: int
    download_url: str
    created_at: datetime

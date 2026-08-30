from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Decoded audio cap. Router and transcribe_audio must use this same value
# so a 6MB clip is 413, not a service None → 502 after quota reserve.
SPEECH_MAX_AUDIO_BYTES = 5_000_000
SPEECH_MAX_B64_CHARS = 4 * ((SPEECH_MAX_AUDIO_BYTES + 2) // 3)
SPEECH_MAX_REQUEST_BYTES = SPEECH_MAX_B64_CHARS + 4096


class WebSearchClassification(BaseModel):
    needs_search: bool
    query: str | None = Field(
        default=None,
        description="Concise web search query when needs_search is true",
    )


class SpeechTranscriptionOut(BaseModel):
    text: str


class SpeechTranscriptionIn(BaseModel):
    audio_base64: str = Field(max_length=SPEECH_MAX_B64_CHARS)
    filename: str = "speech.m4a"


class SpeechTtsIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: str | None = Field(default=None, max_length=16)
    model: str | None = Field(default=None, max_length=64)
    # "lead" + one or more "rest" clips are one user tap: reserve quota on lead only.
    part: str | None = Field(default="full", max_length=8)
    # SHA-256 prefix of the lead clip text. Required for unbilled ``rest``.
    lead_hash: str | None = Field(default=None, max_length=64)


class SpeechTtsOut(BaseModel):
    audio_base64: str
    content_type: str = "audio/mpeg"
    model: str = "speech-tts-model"
    lead_hash: str | None = None


class SpeechLiveSpeakIn(BaseModel):
    audio_base64: str = Field(max_length=SPEECH_MAX_B64_CHARS)
    filename: str = "speech.m4a"
    chat_id: UUID | None = None


class SpeechLiveSpeakOut(BaseModel):
    audio_base64: str
    content_type: str = "audio/wav"
    transcript: str = ""
    remaining: int
    limit: int


class SpeechLiveStatusOut(BaseModel):
    enabled: bool
    entitled: bool
    remaining: int
    limit: int
    refunded: bool = False


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
    source_sender: str | None = None
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

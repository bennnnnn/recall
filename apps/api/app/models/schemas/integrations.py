from pydantic import BaseModel, Field

from app.modules.integrations.schemas import (
    CalendarConflictOut as CalendarConflictOut,
)
from app.modules.integrations.schemas import (
    CalendarConflictsOut as CalendarConflictsOut,
)
from app.modules.integrations.schemas import (
    CalendarEventProposalIn as CalendarEventProposalIn,
)
from app.modules.integrations.schemas import (
    CalendarEventProposalOut as CalendarEventProposalOut,
)
from app.modules.integrations.schemas import (
    GoogleCalendarConnectRequest as GoogleCalendarConnectRequest,
)
from app.modules.integrations.schemas import (
    GoogleCalendarEventOut as GoogleCalendarEventOut,
)
from app.modules.integrations.schemas import (
    GoogleCalendarEventsOut as GoogleCalendarEventsOut,
)
from app.modules.integrations.schemas import (
    GoogleCalendarStatusOut as GoogleCalendarStatusOut,
)
from app.modules.integrations.schemas import (
    GoogleGmailConnectRequest as GoogleGmailConnectRequest,
)
from app.modules.integrations.schemas import (
    GoogleGmailStatusOut as GoogleGmailStatusOut,
)
from app.modules.integrations.schemas import (
    SuggestedReminderOut as SuggestedReminderOut,
)
from app.modules.integrations.schemas import (
    SuggestedRemindersOut as SuggestedRemindersOut,
)

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
    language: str | None = Field(default=None, max_length=16)


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


class SpeechLiveStatusOut(BaseModel):
    enabled: bool
    entitled: bool
    remaining: int
    limit: int
    refunded: bool = False


class PushTokenIn(BaseModel):
    expo_push_token: str = Field(min_length=8, max_length=512)
    platform: str = Field(min_length=2, max_length=20)
    device_id: str | None = Field(default=None, max_length=128)

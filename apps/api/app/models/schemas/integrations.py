from typing import Literal

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
from app.modules.speech.schemas import (
    SPEECH_MAX_AUDIO_BYTES as SPEECH_MAX_AUDIO_BYTES,
)
from app.modules.speech.schemas import (
    SPEECH_MAX_B64_CHARS as SPEECH_MAX_B64_CHARS,
)
from app.modules.speech.schemas import (
    SPEECH_MAX_REQUEST_BYTES as SPEECH_MAX_REQUEST_BYTES,
)
from app.modules.speech.schemas import (
    SpeechLiveStatusOut as SpeechLiveStatusOut,
)
from app.modules.speech.schemas import (
    SpeechTranscriptionIn as SpeechTranscriptionIn,
)
from app.modules.speech.schemas import (
    SpeechTranscriptionOut as SpeechTranscriptionOut,
)
from app.modules.speech.schemas import (
    SpeechTtsIn as SpeechTtsIn,
)
from app.modules.speech.schemas import (
    SpeechTtsOut as SpeechTtsOut,
)


class WebSearchClassification(BaseModel):
    needs_search: bool
    query: str | None = Field(
        default=None,
        description="Concise web search query when needs_search is true",
    )


class PushTokenIn(BaseModel):
    expo_push_token: str = Field(min_length=8, max_length=512)
    platform: str = Field(min_length=2, max_length=20)
    device_id: str | None = Field(default=None, max_length=128)
    # "split" created the first three channels. "tone" created the v2 channels
    # that play the bundled cue. Older installs omit this.
    android_channels: Literal["split", "tone"] | None = None

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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

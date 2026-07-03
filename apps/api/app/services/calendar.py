"""Google Calendar context — detect questions, inject events, handle not-connected."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.secrets import decrypt_refresh_token
from app.gateways import google_calendar_gateway
from app.gateways.google_calendar_gateway import CalendarEvent, GoogleCalendarError
from app.models.orm import User
from app.repositories import calendar_connections as calendar_repo
from app.services import day_planning as day_planning_service
from app.services import time_context as time_context_service

logger = logging.getLogger(__name__)

_EXTERNAL_CALENDAR = re.compile(
    r"\b("
    r"google calendar|my calendar|check my calendar|connect my calendar|"
    r"what(?:'s| is) on my calendar|calendar today|calendar tomorrow|"
    r"meetings today|meetings tomorrow|any meetings|"
    r"what do i have (?:on|scheduled)|what am i doing (?:today|tomorrow)|"
    r"what(?:'s| is) my schedule|my schedule (?:today|tomorrow|this week)"
    r")\b",
    re.IGNORECASE,
)

CALENDAR_HINT = (
    "The user may have Google Calendar connected. When a **Google Calendar** block is present, "
    "use it for external meetings and events. In-app **Reminders** (due-dated todos) are separate — "
    "mention both when relevant. "
    "For day-planning questions (how's my day, plan my day, what to prioritize), lead with today's "
    "calendar when a block is present. "
    "When they ask to check their calendar and no Google Calendar block is present, tell them "
    "it is not connected and they can connect it in Settings → Google Calendar."
)

CALENDAR_WRITE_HINT = (
    "The user may grant Google Calendar **write** access. When they ask to schedule, block, or add "
    "an event/meeting/appointment, propose it with ONLY this fence (one event per fence):\n"
    "```calendar_proposal\n"
    '{"title":"Team sync","start_at":"2026-06-28T15:00:00-07:00","end_at":"2026-06-28T16:00:00-07:00",'
    '"location":"optional","description":"optional"}\n'
    "```\n"
    "Use ISO8601 datetimes in the user's timezone. The app shows an Add to Calendar button — "
    "do NOT say the event was created until they confirm. "
    "If write access is missing, tell them to enable it in Settings → Google Calendar."
)

_CALENDAR_PROPOSAL_FENCE = re.compile(
    r"```calendar_proposal\s*\n([\s\S]*?)```",
    re.IGNORECASE,
)

_CREATE_CALENDAR_EVENT = re.compile(
    r"\b("
    r"schedule|book|block(?:\s+off)?|add(?:\s+to)?\s+(?:my\s+)?calendar|"
    r"create(?:\s+an?)?\s+(?:calendar\s+)?event|set up a meeting|"
    r"put (?:it|that) on my calendar|calendar invite"
    r")\b",
    re.IGNORECASE,
)


class CalendarProposalDraft(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    start_at: datetime
    end_at: datetime
    location: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=2000)


def is_calendar_create_request(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_CREATE_CALENDAR_EVENT.search(cleaned))


def is_external_calendar_question(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_EXTERNAL_CALENDAR.search(cleaned))


_SCHEDULE_CONTEXT = re.compile(
    r"\b("
    r"meeting|meetings|schedule|calendar|busy|free(?:\s+time)?|appointment|"
    r"conflict|overlap|when am i|what am i doing|am i free"
    r")\b",
    re.IGNORECASE,
)


def should_inject_calendar_block(text: str) -> bool:
    """Load live calendar events only when the turn likely needs schedule context."""
    cleaned = text.strip()
    if not cleaned:
        return False
    if day_planning_service.is_day_planning_question(cleaned):
        return True
    if is_external_calendar_question(cleaned):
        return True
    if is_calendar_create_request(cleaned):
        return True
    return bool(_SCHEDULE_CONTEXT.search(cleaned))


def format_not_connected_answer() -> str:
    return (
        "I don't have your Google Calendar connected yet.\n\n"
        "To check meetings and events, connect it in **Settings → Google Calendar**. "
        "Once connected, I can show your upcoming schedule and, with the right permission, "
        "create new events for you (you'll confirm each one before it's added).\n\n"
        "Want me to help with something else in the meantime?"
    )


def _cache_key(user_id: UUID) -> str:
    return f"calendar:events:{user_id}"


async def is_connected(session: AsyncSession, user_id: UUID) -> bool:
    return await calendar_repo.get_for_user(session, user_id) is not None


async def has_write_access(session: AsyncSession, user_id: UUID) -> bool:
    connection = await calendar_repo.get_for_user(session, user_id)
    if connection is None:
        return False
    return has_write_scope(connection.scopes)


async def _load_cached_events(redis: Redis, user_id: UUID) -> list[CalendarEvent] | None:
    try:
        raw = await redis.get(_cache_key(user_id))
        if not raw:
            return None
        payload = json.loads(raw)
        if not isinstance(payload, list):
            return None
        events: list[CalendarEvent] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                start = datetime_from_iso(str(item["start"]))
                end_raw = item.get("end")
                end = datetime_from_iso(str(end_raw)) if end_raw else None
                events.append(
                    CalendarEvent(
                        id=str(item.get("id") or f"{item.get('title', 'Busy')}:{item['start']}"),
                        title=str(item.get("title") or "Busy"),
                        start=start,
                        end=end,
                        location=str(item["location"]) if item.get("location") else None,
                        all_day=bool(item.get("all_day")),
                        calendar_name=str(item["calendar_name"])
                        if item.get("calendar_name")
                        else None,
                    )
                )
            except (KeyError, ValueError):
                continue
        return events
    except Exception:
        return None


def datetime_from_iso(value: str) -> datetime:
    from datetime import datetime

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _store_cached_events(
    redis: Redis,
    user_id: UUID,
    events: list[CalendarEvent],
    ttl: int,
) -> None:
    payload = [
        {
            "id": event.id,
            "title": event.title,
            "start": event.start.isoformat(),
            "end": event.end.isoformat() if event.end else None,
            "location": event.location,
            "all_day": event.all_day,
            "calendar_name": event.calendar_name,
        }
        for event in events
    ]
    try:
        await redis.set(_cache_key(user_id), json.dumps(payload), ex=max(60, ttl))
    except Exception:
        logger.exception("Failed to cache calendar events for user=%s", user_id)


def _format_event_line(event: CalendarEvent, tz_name: str) -> str:
    tz = time_context_service.resolve_timezone(tz_name)
    start_local = event.start.astimezone(tz)
    if event.end and event.end.date() != event.start.date():
        end_local = event.end.astimezone(tz)
        when = f"{start_local.strftime('%a %b %d %I:%M %p')} – {end_local.strftime('%a %b %d %I:%M %p')}"
    elif event.end:
        end_local = event.end.astimezone(tz)
        when = f"{start_local.strftime('%a %b %d %I:%M %p')} – {end_local.strftime('%I:%M %p')}"
    else:
        when = start_local.strftime("%a %b %d %I:%M %p")
    line = f"- {when}: {event.title}"
    if event.location:
        line += f" ({event.location})"
    return line


def format_calendar_block(
    events: list[CalendarEvent],
    timezone: str | None,
    days: int = 14,
) -> str:
    window = max(1, days)
    prompt_events = _events_within_days(events, window)
    header = f"Google Calendar (next {window} days):"
    if not prompt_events:
        return f"{header}\nNo upcoming events found in the connected calendar."
    lines = [header]
    for event in prompt_events[:25]:
        lines.append(_format_event_line(event, timezone or "UTC"))
    return "\n".join(lines)


def _events_within_days(events: list[CalendarEvent], days: int) -> list[CalendarEvent]:
    now = datetime.now(UTC)
    cutoff = now + timedelta(days=max(1, days))
    return [event for event in events if event.start <= cutoff]


async def fetch_upcoming_events(
    session: AsyncSession,
    redis: Redis,
    user: User,
    settings: Settings,
) -> list[CalendarEvent]:
    result = await _fetch_upcoming_events(session, redis, user, settings, report_errors=False)
    return result.events


@dataclass(frozen=True)
class CalendarListResult:
    events: list[CalendarEvent]
    load_error: str | None = None


async def _fetch_upcoming_events(
    session: AsyncSession,
    redis: Redis,
    user: User,
    settings: Settings,
    *,
    report_errors: bool,
) -> CalendarListResult:
    connection = await calendar_repo.get_for_user(session, user.id)
    if connection is None:
        return CalendarListResult(events=[])

    cached = await _load_cached_events(redis, user.id)
    if cached is not None:
        return CalendarListResult(events=cached)

    try:
        events = await google_calendar_gateway.list_upcoming_events(
            settings,
            refresh_token=decrypt_refresh_token(settings, connection.refresh_token),
            calendar_id=connection.calendar_id,
            timezone=user.timezone,
            days=settings.calendar_fetch_days,
        )
    except GoogleCalendarError:
        if report_errors:
            return CalendarListResult(events=[], load_error="fetch_failed")
        return CalendarListResult(events=[])

    await _store_cached_events(redis, user.id, events, settings.calendar_cache_ttl)
    return CalendarListResult(events=events)


async def load_calendar_for_prompt(
    session: AsyncSession,
    redis: Redis,
    user: User,
    settings: Settings,
) -> str | None:
    if not google_calendar_gateway.is_configured(settings):
        return None
    if not await is_connected(session, user.id):
        return None
    events = await fetch_upcoming_events(session, redis, user, settings)
    return format_calendar_block(events, user.timezone, settings.calendar_prompt_days)


async def list_events_for_api(
    session: AsyncSession,
    redis: Redis,
    user: User,
    settings: Settings,
) -> CalendarListResult:
    if not await is_connected(session, user.id):
        return CalendarListResult(events=[])
    return await _fetch_upcoming_events(session, redis, user, settings, report_errors=True)


def has_write_scope(scopes: str) -> bool:
    return google_calendar_gateway.CALENDAR_EVENTS_SCOPE in scopes or "calendar.events" in scopes


def _proposal_key(user_id: UUID, proposal_id: str) -> str:
    return f"calendar:proposal:{user_id}:{proposal_id}"


async def store_event_proposal(
    redis: Redis,
    user_id: UUID,
    proposal_id: str,
    payload: dict[str, str],
    *,
    ttl: int = 900,
) -> None:
    await redis.set(_proposal_key(user_id, proposal_id), json.dumps(payload), ex=ttl)


async def load_event_proposal(
    redis: Redis, user_id: UUID, proposal_id: str
) -> dict[str, str] | None:
    raw = await redis.get(_proposal_key(user_id, proposal_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


async def confirm_create_event(
    session: AsyncSession,
    redis: Redis,
    user: User,
    settings: Settings,
    proposal_id: str,
) -> CalendarEvent:
    connection = await calendar_repo.get_for_user(session, user.id)
    if connection is None:
        raise GoogleCalendarError("Google Calendar is not connected.")
    if not has_write_scope(connection.scopes):
        raise GoogleCalendarError(
            "Calendar write access not granted. Re-connect with write permission."
        )

    proposal = await load_event_proposal(redis, user.id, proposal_id)
    if proposal is None:
        raise GoogleCalendarError("Proposal expired or not found.")

    start = datetime_from_iso(proposal["start"])
    end = datetime_from_iso(proposal["end"])
    event = await google_calendar_gateway.create_event(
        settings,
        refresh_token=decrypt_refresh_token(settings, connection.refresh_token),
        calendar_id=connection.calendar_id or "primary",
        title=proposal.get("title") or "Event",
        start=start,
        end=end,
        timezone=user.timezone or "UTC",
        location=proposal.get("location") or None,
        description=proposal.get("description") or None,
    )
    await redis.delete(_cache_key(user.id))
    await redis.delete(_proposal_key(user.id, proposal_id))
    return event


async def materialize_calendar_proposals(
    session: AsyncSession,
    redis: Redis,
    user: User,
    settings: Settings,
    assistant_text: str,
) -> str:
    """Parse model calendar_proposal fences, store Redis proposals, inject proposal_id."""
    if not _CALENDAR_PROPOSAL_FENCE.search(assistant_text):
        return assistant_text
    if not google_calendar_gateway.is_configured(settings):
        return assistant_text
    connection = await calendar_repo.get_for_user(session, user.id)
    if connection is None or not has_write_scope(connection.scopes):
        return assistant_text

    pending: list[tuple[str, dict[str, str], CalendarProposalDraft]] = []

    def replace_sync(match: re.Match[str]) -> str:
        raw = match.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return match.group(0)
        if not isinstance(data, dict) or data.get("proposal_id"):
            return match.group(0)
        try:
            draft = CalendarProposalDraft.model_validate(data)
        except Exception:
            return match.group(0)
        if draft.end_at <= draft.start_at:
            return match.group(0)
        proposal_id = str(uuid4())
        pending.append(
            (
                proposal_id,
                {
                    "title": draft.title,
                    "start": draft.start_at.isoformat(),
                    "end": draft.end_at.isoformat(),
                    "location": draft.location or "",
                    "description": draft.description or "",
                },
                draft,
            )
        )
        stored = {
            "proposal_id": proposal_id,
            "title": draft.title,
            "start_at": draft.start_at.isoformat(),
            "end_at": draft.end_at.isoformat(),
        }
        if draft.location:
            stored["location"] = draft.location
        if draft.description:
            stored["description"] = draft.description
        return f"```calendar_proposal\n{json.dumps(stored, ensure_ascii=False)}\n```"

    updated = _CALENDAR_PROPOSAL_FENCE.sub(replace_sync, assistant_text)
    for proposal_id, payload, _draft in pending:
        await store_event_proposal(redis, user.id, proposal_id, payload)
    return updated


OVERLAP_MS = 15 * 60 * 1000


def find_conflicting_events(
    events: list[CalendarEvent],
    due_at: datetime,
    *,
    overlap_ms: int = OVERLAP_MS,
) -> list[CalendarEvent]:
    target = due_at.timestamp() * 1000
    if target != target:  # NaN guard
        return []
    conflicts: list[CalendarEvent] = []
    for event in events:
        start_ms = event.start.timestamp() * 1000
        end_ms = (event.end or event.start).timestamp() * 1000
        window_start = target - overlap_ms
        window_end = target + overlap_ms
        if start_ms <= window_end and end_ms >= window_start:
            conflicts.append(event)
    return conflicts

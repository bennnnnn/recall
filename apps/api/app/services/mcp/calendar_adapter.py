"""Calendar MCP adapter — wraps calendar service actions."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways.google_calendar_gateway import CalendarEvent
from app.gateways.mcp.base import ToolResult
from app.models.orm import User
from app.models.tool_schemas import CalendarConflictsInput
from app.services import calendar as calendar_service

logger = logging.getLogger(__name__)

_calendar_user: ContextVar[User | None] = ContextVar("mcp_calendar_user", default=None)
_calendar_redis: ContextVar[Redis | None] = ContextVar("mcp_calendar_redis", default=None)
_calendar_settings: ContextVar[Settings | None] = ContextVar("mcp_calendar_settings", default=None)


@contextmanager
def bind_calendar_context(
    *,
    user: User | None = None,
    redis: Redis | None = None,
    settings: Settings | None = None,
) -> Iterator[None]:
    """Bind the calling turn so conflict checks can load Google events."""
    token_user = _calendar_user.set(user)
    token_redis = _calendar_redis.set(redis)
    token_settings = _calendar_settings.set(settings)
    try:
        yield
    finally:
        _calendar_user.reset(token_user)
        _calendar_redis.reset(token_redis)
        _calendar_settings.reset(token_settings)


def _parse_calendar_events(raw_events: object) -> list[CalendarEvent]:
    if not isinstance(raw_events, list):
        return []
    parsed: list[CalendarEvent] = []
    for raw in raw_events:
        if isinstance(raw, CalendarEvent):
            parsed.append(raw)
            continue
        if hasattr(raw, "model_dump"):
            raw = raw.model_dump()
        if not isinstance(raw, dict):
            continue
        start_raw = raw.get("start")
        if not start_raw:
            continue
        try:
            start = calendar_service.datetime_from_iso(str(start_raw))
        except (TypeError, ValueError):
            continue
        end_raw = raw.get("end")
        end = None
        if end_raw:
            try:
                end = calendar_service.datetime_from_iso(str(end_raw))
            except (TypeError, ValueError):
                end = None
        parsed.append(
            CalendarEvent(
                id=str(raw.get("id") or ""),
                title=str(raw.get("title") or raw.get("summary") or "Event"),
                start=start,
                end=end,
                location=str(raw.get("location") or "") or None,
                all_day=bool(raw.get("all_day")),
                calendar_name=str(raw.get("calendar_name") or "") or None,
            )
        )
    return parsed


def _merge_events(
    google_events: list[CalendarEvent], extra: list[CalendarEvent]
) -> list[CalendarEvent]:
    merged: list[CalendarEvent] = []
    seen: set[str] = set()
    for event in google_events + extra:
        key = event.id or f"{event.start.isoformat()}|{event.title}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(event)
    return merged


async def _google_events() -> list[CalendarEvent]:
    user = _calendar_user.get()
    redis = _calendar_redis.get()
    settings = _calendar_settings.get()
    if user is None or redis is None or settings is None:
        return []
    try:
        async with SessionLocal() as session:
            return await calendar_service.fetch_upcoming_events(session, redis, user, settings)
    except Exception:
        logger.exception("Calendar tool failed to load Google events")
        return []


class CalendarAdapter:
    name = "calendar"
    input_schema = CalendarConflictsInput

    def describe(self) -> str:
        return (
            "Check the user's Google Calendar for conflicts at a due time. "
            "Create events with the calendar_proposal fence, not this tool."
        )

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.describe(),
                "parameters": CalendarConflictsInput.model_json_schema(),
            },
        }

    async def invoke(self, args: dict[str, Any]) -> ToolResult:
        action = str(args.get("action") or "conflicts")
        if action == "conflicts":
            extra = _parse_calendar_events(args.get("events") or [])
            due_at = args.get("due_at")
            if not due_at:
                return ToolResult(name=self.name, content="Missing due_at.")
            # BUG FIX (was uncaught): due_at is model-supplied and only
            # Pydantic-constrained to "a 1-64 char string", not ISO format —
            # a plausible-but-malformed value (e.g. "tomorrow afternoon")
            # raised straight out of this adapter with nothing upstream
            # catching it, taking down the whole chat turn. The sibling
            # helper _parse_calendar_events already guards the identical
            # call for list entries; do the same here.
            try:
                due_at_parsed = calendar_service.datetime_from_iso(str(due_at))
            except (TypeError, ValueError):
                return ToolResult(name=self.name, content=f"Invalid due_at: {due_at!r}")
            events = _merge_events(await _google_events(), extra)
            conflicts = calendar_service.find_conflicting_events(events, due_at_parsed)
            if not conflicts:
                return ToolResult(name=self.name, content="No conflicts.")
            lines = [f"- {e.title} at {e.start.isoformat()}" for e in conflicts]
            return ToolResult(name=self.name, content="\n".join(lines))
        return ToolResult(name=self.name, content=f"Unknown action: {action}")

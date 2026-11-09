"""A to-do with a date and no time (``todo_items.due_has_time`` false).

Picking a date on the phone used to write a time with it (9:00, or the next hour), so a
date alone came with a time and a reminder. A date-only to-do keeps ``due_at`` at the
start of its day on the user's clock, so it sorts and groups by ``due_at`` with the timed
ones, first on its day. Nothing reminds of it: push, email and the phone's own alert read
only a to-do with a time. It is overdue once its day has ended there, not at its start.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from app.core.timezone import resolve_timezone
from app.services import time_context as time_context_service


def has_time(todo: object) -> bool:
    """Whether the to-do's due date has a time. A row built before the flag was read, or
    with none set yet, has one, as every to-do did."""
    return getattr(todo, "due_has_time", None) is not False


def _local(due_at: datetime, timezone: str | None) -> datetime:
    """``due_at`` on the user's clock; a naive one is already on it."""
    zone = resolve_timezone(timezone)
    return due_at.replace(tzinfo=zone) if due_at.tzinfo is None else due_at.astimezone(zone)


def _day_start(day_offset: int, due_at: datetime, timezone: str | None) -> datetime:
    zone = resolve_timezone(timezone)
    day = _local(due_at, timezone).date() + timedelta(days=day_offset)
    return datetime.combine(day, time(), zone).astimezone(UTC)


def start_of_day(due_at: datetime, timezone: str | None) -> datetime:
    """The start of the day ``due_at`` falls on in the user's zone, in UTC: where a
    date-only to-do is held."""
    return _day_start(0, due_at, timezone)


def stored_due(due_at: datetime | None, timezone: str | None, *, has_time: bool) -> datetime | None:
    """``due_at`` as a save stores it: a time in UTC, a date alone at its day's start."""
    if due_at is None or has_time:
        return time_context_service.normalize_due_at(due_at, timezone)
    return start_of_day(due_at, timezone)


def overdue_from(due_at: datetime, timezone: str | None, *, has_time: bool) -> datetime:
    """When a to-do is overdue: at its time, or for a date alone once its day has ended."""
    if has_time:
        return due_at if due_at.tzinfo is not None else due_at.replace(tzinfo=UTC)
    return _day_start(1, due_at, timezone)


def same_day_in(due_at: datetime, old_timezone: str | None, new_timezone: str | None) -> datetime:
    """A date-only to-do's day held in a new zone: the start of the same date there. The day
    of the old start, read on the new clock, can be the day before (New York to Los Angeles)."""
    day = _local(due_at, old_timezone).date()
    return datetime.combine(day, time(), resolve_timezone(new_timezone)).astimezone(UTC)


def describe_due(
    due_at: datetime | None, timezone: str | None, *, has_time: bool, checked: bool = False
) -> str:
    """How far off a to-do is, for the model: ``describe_due_at`` for a time; a date alone
    says its day and is overdue only after it."""
    if due_at is None or checked or has_time:
        return time_context_service.describe_due_at(due_at, timezone, checked=checked)
    zone = resolve_timezone(timezone)
    days = (_local(due_at, timezone).date() - datetime.now(zone).date()).days
    if days < 0:
        return f"overdue by {-days} day{'s' if days != -1 else ''}"
    if days <= 1:
        return "due today" if days == 0 else "due tomorrow"
    day = _local(due_at, timezone)
    if days <= 7:
        return f"due in {days} days ({day.strftime('%a %b %d')})"
    return f"due {day.strftime('%a %b %d, %Y')}"

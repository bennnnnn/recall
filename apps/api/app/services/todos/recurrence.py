"""Simple Schedule repeats — daily / weekdays / weekly / monthly."""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

RecurrenceRule = Literal["daily", "weekdays", "weekly", "monthly"]
RECURRENCE_RULES: tuple[RecurrenceRule, ...] = (
    "daily",
    "weekdays",
    "weekly",
    "monthly",
)


def is_recurrence_rule(value: object) -> bool:
    return value in RECURRENCE_RULES


def _zone(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def _as_local(dt: datetime, tz_name: str | None) -> datetime:
    tz = _zone(tz_name)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def _add_month(local: datetime) -> datetime:
    month = local.month + 1
    year = local.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(local.day, monthrange(year, month)[1])
    return local.replace(year=year, month=month, day=day)


def _step_local(local: datetime, rule: RecurrenceRule) -> datetime:
    if rule == "daily":
        return local + timedelta(days=1)
    if rule == "weekly":
        return local + timedelta(days=7)
    if rule == "monthly":
        return _add_month(local)
    nxt = local + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


def snap_first_due(
    due_at: datetime, rule: RecurrenceRule | None, *, timezone: str | None
) -> datetime:
    """Weekday repeats skip Sat/Sun for the first fire."""
    if rule != "weekdays":
        return due_at
    local = _as_local(due_at, timezone)
    while local.weekday() >= 5:
        local += timedelta(days=1)
    return local.astimezone(due_at.tzinfo or _zone(timezone))


def next_recurring_due(
    due_at: datetime,
    rule: RecurrenceRule,
    *,
    now: datetime,
    timezone: str | None,
) -> datetime:
    """Advance *due_at* until it is strictly after *now* in the user's timezone."""
    local = _as_local(due_at, timezone)
    now_local = _as_local(now, timezone)
    nxt = local
    for _ in range(400):
        if nxt > now_local:
            return nxt.astimezone(due_at.tzinfo or _zone(timezone))
        nxt = _step_local(nxt, rule)
    return nxt.astimezone(due_at.tzinfo or _zone(timezone))

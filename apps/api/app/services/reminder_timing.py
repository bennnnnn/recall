"""Shared reminder lead-time rules for push and prompt logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

DEFAULT_REMINDER_LEAD_MINUTES = 10
MAX_REMINDER_LEAD_MINUTES = 60
VALID_REMINDER_LEAD_MINUTES = frozenset({5, 10, 15, 30, 60})
OVERDUE_MAX_HOURS = 48


def resolve_reminder_lead_minutes(raw: int | None) -> int:
    if raw in VALID_REMINDER_LEAD_MINUTES:
        return raw
    return DEFAULT_REMINDER_LEAD_MINUTES


def should_notify_todo(
    due_at: datetime,
    *,
    now: datetime,
    lead_minutes: int,
) -> bool:
    """True when a reminder push/local alert should fire."""
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    if due_at < now:
        overdue_cutoff = now - timedelta(hours=OVERDUE_MAX_HOURS)
        return due_at >= overdue_cutoff

    lead = resolve_reminder_lead_minutes(lead_minutes)
    return due_at <= now + timedelta(minutes=lead)

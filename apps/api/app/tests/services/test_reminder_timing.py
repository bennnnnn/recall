from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.services.reminder_timing import (
    DEFAULT_REMINDER_LEAD_MINUTES,
    in_quiet_hours,
    reminder_title,
    resolve_reminder_lead_minutes,
    should_notify_todo,
)


def test_resolve_reminder_lead_minutes():
    assert resolve_reminder_lead_minutes(5) == 5
    assert resolve_reminder_lead_minutes(30) == 30
    assert resolve_reminder_lead_minutes(60) == 60
    assert resolve_reminder_lead_minutes(99) == DEFAULT_REMINDER_LEAD_MINUTES
    assert resolve_reminder_lead_minutes(None) == DEFAULT_REMINDER_LEAD_MINUTES


@pytest.mark.parametrize(
    "due_offset_min, lead, expected",
    [
        (4, 5, True),
        (20, 5, False),
        (20, 30, True),
        (45, 60, True),
        (90, 60, False),
        (-30, 10, True),
    ],
)
def test_should_notify_todo(due_offset_min, lead, expected):
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    due = now + timedelta(minutes=due_offset_min)
    assert should_notify_todo(due, now=now, lead_minutes=lead) is expected


def test_should_notify_todo_ignores_stale_overdue():
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    due = now - timedelta(hours=72)
    assert should_notify_todo(due, now=now, lead_minutes=10) is False


def test_reminder_title_localizes_and_distinguishes_overdue():
    """Shared by both push and email so they can't drift apart on this — see
    the BUG FIX comment above _REMINDER_TITLES."""
    assert reminder_title(is_overdue=False, locale="en") == "Reminder"
    assert reminder_title(is_overdue=True, locale="en") == "Overdue reminder"
    assert reminder_title(is_overdue=False, locale="es") == "Recordatorio"
    assert reminder_title(is_overdue=True, locale="es") == "Recordatorio atrasado"
    # Unsupported/unset locale falls back to English rather than crashing.
    assert reminder_title(is_overdue=False, locale=None) == "Reminder"
    assert reminder_title(is_overdue=False, locale="am") == "Reminder"


def _quiet_user(*, enabled: bool = True, start: int = 1320, end: int = 420, tz: str = "UTC"):
    user = MagicMock()
    user.quiet_hours_enabled = enabled
    user.quiet_hours_start_minute = start
    user.quiet_hours_end_minute = end
    user.timezone = tz
    return user


def test_in_quiet_hours_disabled_and_magicmock_are_false():
    user = MagicMock()
    user.timezone = "UTC"
    assert in_quiet_hours(user) is False
    assert (
        in_quiet_hours(_quiet_user(enabled=False), now=datetime(2026, 1, 2, 23, 0, tzinfo=UTC))
        is False
    )


def test_in_quiet_hours_wraps_midnight():
    user = _quiet_user()
    assert in_quiet_hours(user, now=datetime(2026, 1, 2, 22, 0, tzinfo=UTC)) is True
    assert in_quiet_hours(user, now=datetime(2026, 1, 2, 23, 30, tzinfo=UTC)) is True
    assert in_quiet_hours(user, now=datetime(2026, 1, 2, 6, 59, tzinfo=UTC)) is True
    assert in_quiet_hours(user, now=datetime(2026, 1, 2, 7, 0, tzinfo=UTC)) is False
    assert in_quiet_hours(user, now=datetime(2026, 1, 2, 12, 0, tzinfo=UTC)) is False


def test_in_quiet_hours_same_start_and_end_is_never_quiet():
    user = _quiet_user(start=600, end=600)
    assert in_quiet_hours(user, now=datetime(2026, 1, 2, 10, 0, tzinfo=UTC)) is False


def test_in_quiet_hours_same_day_window():
    user = _quiet_user(start=540, end=720)
    assert in_quiet_hours(user, now=datetime(2026, 1, 2, 9, 0, tzinfo=UTC)) is True
    assert in_quiet_hours(user, now=datetime(2026, 1, 2, 12, 0, tzinfo=UTC)) is False
    assert in_quiet_hours(user, now=datetime(2026, 1, 2, 8, 59, tzinfo=UTC)) is False

from datetime import UTC, datetime, timedelta

import pytest

from app.services.reminder_timing import (
    DEFAULT_REMINDER_LEAD_MINUTES,
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

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services.reminder_timing import (
    DEFAULT_REMINDER_LEAD_MINUTES,
    learning_dedupe_key,
    resolve_reminder_lead_minutes,
    should_notify_todo,
    user_day_key,
    user_local_hour,
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


def test_user_local_hour_and_day_key_use_user_timezone():
    user = MagicMock()
    user.timezone = "UTC"
    assert user_local_hour(user) == datetime.now(UTC).hour
    assert user_day_key(user) == datetime.now(UTC).strftime("%Y-%m-%d")


def test_learning_dedupe_key_scopes_by_prefix_user_and_day():
    user_id = uuid4()
    push_key = learning_dedupe_key("recall:push:learning", user_id, "2026-07-12")
    email_key = learning_dedupe_key("recall:email:learning", user_id, "2026-07-12")
    assert push_key == f"recall:push:learning:{user_id}:2026-07-12"
    assert email_key == f"recall:email:learning:{user_id}:2026-07-12"
    assert push_key != email_key

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.todos.recurrence import next_recurring_due, snap_first_due


def test_next_daily_skips_to_future_morning() -> None:
    due = datetime(2026, 8, 20, 8, 0, tzinfo=ZoneInfo("America/New_York"))
    now = datetime(2026, 8, 22, 9, 0, tzinfo=ZoneInfo("America/New_York"))
    nxt = next_recurring_due(due, "daily", now=now, timezone="America/New_York")
    local = nxt.astimezone(ZoneInfo("America/New_York"))
    assert local.day == 23
    assert local.hour == 8


def test_weekdays_skips_weekend() -> None:
    friday = datetime(2026, 8, 21, 8, 0, tzinfo=ZoneInfo("UTC"))
    saturday = datetime(2026, 8, 22, 9, 0, tzinfo=ZoneInfo("UTC"))
    nxt = next_recurring_due(friday, "weekdays", now=saturday, timezone="UTC")
    assert nxt.weekday() == 0


def test_snap_first_due_skips_saturday() -> None:
    saturday = datetime(2026, 8, 22, 8, 0, tzinfo=ZoneInfo("UTC"))
    snapped = snap_first_due(saturday, "weekdays", timezone="UTC")
    assert snapped.weekday() == 0

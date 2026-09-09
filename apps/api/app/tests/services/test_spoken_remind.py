"""Linear spoken-reminder parser (Live Talk / explicit user text)."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.services.todos.reminder_fences import parse_spoken_remind


def test_parse_spoken_remind_today_and_tomorrow():
    now = datetime(2026, 9, 9, 12, tzinfo=UTC)
    today = parse_spoken_remind(
        "remind me to water the plants today at 6pm",
        user_timezone="UTC",
        now=now,
    )
    assert today is not None
    title, due = today
    assert title == "water the plants"
    assert due == datetime(2026, 9, 9, 18, 0, tzinfo=UTC)

    tomorrow = parse_spoken_remind(
        "remind me to water the plants tomorrow at 6pm",
        user_timezone="UTC",
        now=now,
    )
    assert tomorrow is not None
    assert tomorrow[1] == datetime(2026, 9, 10, 18, 0, tzinfo=UTC)


def test_parse_spoken_remind_weekday_friday_at_five():
    now = datetime(2026, 9, 9, 12, tzinfo=UTC)  # Wednesday
    parsed = parse_spoken_remind(
        "Remind me to call Mom Friday at 5pm",
        user_timezone="UTC",
        now=now,
    )
    assert parsed is not None
    title, due = parsed
    assert title == "call Mom"
    assert due == datetime(2026, 9, 11, 17, 0, tzinfo=UTC)


def test_parse_spoken_remind_same_weekday_stays_today():
    now = datetime(2026, 9, 11, 8, tzinfo=UTC)  # Friday
    parsed = parse_spoken_remind(
        "remind me to call mom friday at 7:30 am",
        user_timezone="UTC",
        now=now,
    )
    assert parsed is not None
    assert parsed[1] == datetime(2026, 9, 11, 7, 30, tzinfo=UTC)


def test_parse_spoken_remind_requires_clock_and_ampm():
    now = datetime(2026, 9, 9, 12, tzinfo=UTC)
    assert parse_spoken_remind("remind me to call mom Friday at 5", now=now) is None
    assert parse_spoken_remind("remind me to call mom Friday", now=now) is None
    assert parse_spoken_remind("remind me to water the plants tomorrow", now=now) is None


def test_parse_spoken_remind_uses_last_at_for_clock():
    now = datetime(2026, 9, 9, 12, tzinfo=UTC)
    parsed = parse_spoken_remind(
        "remind me to meet at the office tomorrow at 9am",
        user_timezone="UTC",
        now=now,
    )
    assert parsed is not None
    assert parsed[0] == "meet at the office"
    assert parsed[1].hour == 9


def test_parse_spoken_remind_dotted_ampm_and_timezone():
    now = datetime(2026, 9, 9, 12, tzinfo=UTC)
    parsed = parse_spoken_remind(
        "remind me to stretch today at 5:00 p.m.",
        user_timezone="America/New_York",
        now=now,
    )
    assert parsed is not None
    due = parsed[1]
    assert due.tzinfo == ZoneInfo("America/New_York")
    assert due.hour == 17

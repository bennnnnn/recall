from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services.time_context import (
    describe_due_at,
    effective_timezone,
    format_digital_clock,
    format_location_answer,
    format_time_answer,
    is_location_question,
    is_time_question,
    normalize_due_at,
)


def test_normalize_due_at_naive_uses_user_timezone():
    due = datetime(2026, 6, 28, 17, 0, 0)
    utc = normalize_due_at(due, "America/New_York")
    assert utc is not None
    assert utc.tzinfo == UTC


def test_describe_due_at_overdue():
    tz = ZoneInfo("UTC")
    now = datetime.now(tz)
    past = (now - timedelta(days=2)).astimezone(UTC)
    label = describe_due_at(past, "UTC")
    assert label.startswith("overdue")


def test_describe_due_at_skips_checked():
    due = datetime.now(UTC) + timedelta(days=1)
    assert describe_due_at(due, "UTC", checked=True) == ""


@pytest.mark.parametrize(
    "text,expected",
    [
        ("what time is it", True),
        ("What time is it?", True),
        ("what's the time", True),
        ("current time", True),
        ("tell me the time", True),
        ("again", True),
        ("what time is the meeting", False),
        ("what time is my flight", False),
        ("schedule a reminder for 5pm", False),
    ],
)
def test_is_time_question(text, expected):
    assert is_time_question(text) is expected


def test_format_digital_clock_24h():
    when = datetime(2026, 6, 28, 14, 32, 5, tzinfo=ZoneInfo("UTC"))
    assert format_digital_clock(when, "de") == "14:32:05"


def test_format_digital_clock_12h():
    when = datetime(2026, 6, 28, 14, 32, 5, tzinfo=ZoneInfo("UTC"))
    assert format_digital_clock(when, "en") == "02:32:05 PM"


def test_format_time_answer_uses_clock_fence():
    answer = format_time_answer("America/Los_Angeles", "en")
    assert answer == "```clock\n```"


def test_is_location_question():
    assert is_location_question("location")
    assert is_location_question("Where am I?")
    assert is_location_question("Where is my location?")
    assert is_location_question("Where's my location")
    assert is_location_question("What's my location")
    assert not is_location_question("weather in Paris")
    assert not is_location_question("Where is the meeting")


def test_format_location_answer_with_city():
    answer = format_location_answer("Los Angeles, CA, United States", "America/Los_Angeles")
    assert "Los Angeles" in answer


def test_format_location_answer_without_city():
    answer = format_location_answer(None, "UTC")
    assert "don't have your location" in answer.lower()


def test_effective_timezone_prefers_client():
    assert effective_timezone("UTC", "America/New_York") == "America/New_York"


def test_effective_timezone_falls_back_to_profile():
    assert effective_timezone("Europe/London", None) == "Europe/London"


def test_effective_timezone_invalid_client_uses_profile():
    assert effective_timezone("America/Chicago", "Not/A/Zone") == "America/Chicago"

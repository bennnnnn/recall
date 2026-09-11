from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services.time_context import (
    describe_due_at,
    effective_timezone,
    format_date_answer,
    format_digital_clock,
    format_location_answer,
    format_time_answer,
    format_year_answer,
    is_current_date_question,
    is_local_now_question,
    is_location_question,
    is_time_question,
    is_year_question,
    maybe_local_now_reply,
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
        ("what time", True),
        ("What time?", True),
        ("what time now", True),
        ("what's the time", True),
        ("current time", True),
        ("tell me the time", True),
        ("again", False),
        ("Again!", False),
        ("one more time", False),
        ("tell me again", False),
        ("refresh", False),
        ("update", False),
        ("update it", False),
        ("is it", False),
        ("what time is it in dc", False),
        ("what time is it in Tokyo", False),
        ("what time is the meeting", False),
        ("what time is my flight", False),
        ("schedule a reminder for 5pm", False),
    ],
)
def test_is_time_question(text, expected):
    assert is_time_question(text) is expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("what year is it", True),
        ("What year is it?", True),
        ("what year is it now", True),
        ("what year", False),
        ("current year", True),
        ("what's the current year", True),
        ("What’s the year", True),  # curly apostrophe
        ("what year are we in", True),
        ("tell me the year", True),
        ("what year did WWII end", False),
        ("what year was I born", False),
        ("what year is it in Japan", False),
        ("what time is it", False),
        ("U sure?", False),
    ],
)
def test_is_year_question(text, expected):
    assert is_year_question(text) is expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("what's the date", True),
        ("what is the date", True),
        ("what's today's date", True),
        ("what date is it", True),
        ("current date", True),
        ("what day is it", True),
        ("what day is it today", True),
        ("what day", False),
        ("what's today", False),
        ("what is today", False),
        ("what date is Christmas", False),
        ("what day is Christmas", False),
        ("what time is it", False),
    ],
)
def test_is_current_date_question(text, expected):
    assert is_current_date_question(text) is expected


def test_is_local_now_question_covers_time_year_and_date():
    assert is_local_now_question("what time is it") is True
    assert is_local_now_question("what year is it") is True
    assert is_local_now_question("what's the date") is True
    assert is_local_now_question("what year did WWII end") is False


def test_format_year_answer_uses_timezone_year():
    now = datetime.now(ZoneInfo("UTC"))
    assert format_year_answer("UTC") == f"It's {now.year}."


def test_format_date_answer_uses_local_calendar_day():
    now = datetime.now(ZoneInfo("UTC"))
    assert format_date_answer("UTC") == f"{now.strftime('%A, %B')} {now.day}, {now.year}."


def test_maybe_local_now_reply_dispatches():
    assert maybe_local_now_reply("what time is it", "UTC") == "```clock\n```"
    now = datetime.now(ZoneInfo("UTC"))
    assert maybe_local_now_reply("what year is it", "UTC") == f"It's {now.year}."
    assert maybe_local_now_reply("what's the date", "UTC") == (
        f"{now.strftime('%A, %B')} {now.day}, {now.year}."
    )
    assert maybe_local_now_reply("what year did WWII end", "UTC") is None
    assert maybe_local_now_reply("what year", "UTC") is None
    assert maybe_local_now_reply("what day", "UTC") is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("what time is my flight", True),
        ("When is the meeting?", True),
        ("what time does my train leave", True),
        ("what time is it", False),
        ("tell me about flight delays", False),
        ("schedule a reminder for 5pm", False),
    ],
)
def test_is_scheduled_event_time_question(text, expected):
    from app.services.time_context import is_scheduled_event_time_question

    assert is_scheduled_event_time_question(text) is expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("what time is it in dc", True),
        ("What time is it in Tokyo?", True),
        ("what's the time in London", True),
        ("time in Paris", True),
        ("what time is it", False),
        ("what time", False),
    ],
)
def test_is_remote_time_question(text, expected):
    from app.services.time_context import is_remote_time_question

    assert is_remote_time_question(text) is expected


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
    assert is_location_question("Where am I right now")
    assert is_location_question("where am i right nwo")
    assert is_location_question("where am I currently")
    assert is_location_question("Where is my location?")
    assert is_location_question("Where's my location")
    assert is_location_question("What's my location")
    assert is_location_question("what's my current location")
    assert is_location_question("Where am iI")
    assert is_location_question("where am ii")
    assert not is_location_question("weather in Paris")
    assert not is_location_question("Where is the meeting")
    assert not is_location_question("where am I going tomorrow")


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


def test_effective_timezone_invalid_profile_falls_back_to_utc():
    assert effective_timezone("Not/A/Zone", None) == "UTC"
    assert effective_timezone("Not/A/Zone", "Also/Bogus") == "UTC"

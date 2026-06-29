from datetime import UTC, datetime

import pytest

from app.gateways.google_calendar_gateway import CalendarEvent
from app.services.calendar import (
    format_calendar_block,
    format_not_connected_answer,
    is_external_calendar_question,
    should_inject_calendar_block,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("check my calendar", True),
        ("what's on my calendar tomorrow", True),
        ("any meetings today", True),
        ("what am I doing today", True),
        ("Ethiopias game score", False),
        ("what's due today", False),
    ],
)
def test_is_external_calendar_question(text, expected):
    assert is_external_calendar_question(text) is expected


def test_format_not_connected_mentions_settings():
    answer = format_not_connected_answer()
    assert "Google Calendar" in answer
    assert "Settings" in answer


@pytest.mark.parametrize(
    "text,expected",
    [
        ("check my calendar", True),
        ("schedule a meeting tomorrow", True),
        ("am I free at 3pm", True),
        ("solve for the hypotenuse", False),
        ("best restaurants near me", False),
        ("what is photosynthesis", False),
    ],
)
def test_should_inject_calendar_block(text, expected):
    assert should_inject_calendar_block(text) is expected


def test_format_calendar_block_lists_events():
    block = format_calendar_block(
        [
            CalendarEvent(
                id="evt-1",
                title="Team sync",
                start=datetime(2026, 6, 28, 14, 0, tzinfo=UTC),
                end=datetime(2026, 6, 28, 15, 0, tzinfo=UTC),
                location="Zoom",
            )
        ],
        "UTC",
    )
    assert "Team sync" in block
    assert "Zoom" in block

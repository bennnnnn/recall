"""A reply swapped for the clock only when it denies the clock, not other live data."""

from __future__ import annotations

import pytest

from app.modules.chat.clock_denial import model_denies_clock


@pytest.mark.parametrize(
    ("reply", "asked"),
    [
        (
            "I don't have access to the current clock, so I can't tell you the exact time "
            "right now.",
            "what time is it",
        ),
        ("I don't have access to real-time data, so I can't tell you the current time.", ""),
        ("I can't tell you the exact time. Please check a device nearby.", "yo whats the time rn"),
        ("I don’t have access to a clock, sorry!", "do you know what time it is"),
        ("I don't have access to real-time information, so I can't tell you today's date.", ""),
    ],
)
def test_a_denial_of_the_clock_is_swapped(reply: str, asked: str) -> None:
    assert model_denies_clock(reply, asked)


@pytest.mark.parametrize(
    ("reply", "asked"),
    [
        # The live chat: a denial of the weather became the clock (2026-10-25).
        (
            "I don't have access to real-time information, so I can't tell you tomorrow's "
            "weather in Chicago.",
            "I told you, chicago",
        ),
        ("I don't have access to real-time sports scores, so check the NFL app.", ""),
        ("I don't have access to real-time data for game times.", "when do the bears play"),
        ("I don't have access to real-time stock prices.", "whats apple at"),
        ("I can't tell you the exact time of the flight. Check the airline's app.", ""),
        # Another place's clock, or a scheduled time, is not the local clock.
        ("I don't have access to a clock.", "what time is it in tokyo"),
        ("I can't tell you the exact time right now.", "what time is my flight"),
        # Long replies and plain answers are left alone.
        ("It's 3:20 PM.", "what time is it"),
        ("I don't have access to the clock. " + "More words. " * 40, "what time is it"),
    ],
)
def test_other_denials_are_left_alone(reply: str, asked: str) -> None:
    assert not model_denies_clock(reply, asked)

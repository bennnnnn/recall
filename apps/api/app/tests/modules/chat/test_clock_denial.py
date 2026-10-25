"""A reply swapped for the clock only when it denies the current clock, not other live data."""

from __future__ import annotations

import pytest

from app.modules.chat.clock_denial import model_denies_clock

_LIVE = "I don't have access to real-time information, so I can't tell you"


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
        (f"{_LIVE} today's date.", ""),
        # The clock named in the next sentence, or as clocks.
        (
            "I don't have access to real-time data. Please check your device for the current time.",
            "what time is it",
        ),
        (
            "I don't have access to real-time information. You can check the clock on your phone.",
            "what time is it",
        ),
        ("I don't have access to real-time clocks.", "what time is it"),
        ("I'm unable to check the time. Your phone shows the current time.", "what time is it"),
        # Still the local clock, in other words.
        ("I can't tell you the exact time right now.", "what time is it in my time zone"),
        ("I can't tell you the exact time right now.", "what time is it? i have a meeting at 4"),
        ("I can't tell you the current time in your area.", "time?"),
    ],
)
def test_a_denial_of_the_clock_is_swapped(reply: str, asked: str) -> None:
    assert model_denies_clock(reply, asked)


@pytest.mark.parametrize(
    ("reply", "asked"),
    [
        # The live chat: a denial of the weather became the clock (2026-10-25).
        (f"{_LIVE} tomorrow's weather in Chicago.", "I told you, chicago"),
        ("I don't have access to real-time sports scores, so check the NFL app.", ""),
        ("I don't have access to real-time data for game times.", "when do the bears play"),
        ("I don't have access to real-time stock prices.", "whats apple at"),
        ("I can't tell you the exact time of the flight. Check the airline's app.", ""),
        # Another thing's time or date (review, 2026-10-25).
        (f"{_LIVE} the date of the next election.", "when is the next election"),
        (f"{_LIVE} the opening time of the store.", "when does target open"),
        (f"{_LIVE} the release date.", "when does gta 6 come out"),
        (f"{_LIVE} the sunset time in Chicago.", "when is sunset"),
        (f"{_LIVE} the exact time of the eclipse.", "when is the eclipse"),
        (f"{_LIVE} the current wait time.", "how long is the wait at disney"),
        (f"{_LIVE} the current time in Tokyo.", "and in tokyo?"),
        (f"{_LIVE} the time in Tokyo.", "whats the time over in tokyo"),
        ("I don't have access to real-time showtimes.", "when is dune playing"),
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

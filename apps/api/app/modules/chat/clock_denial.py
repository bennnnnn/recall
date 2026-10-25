"""A short reply that says it cannot see the clock, which the app always has.

The finalize pass swaps such a reply for the clock (``finalize_text.fix_clock``). The
reply must deny live data and name the current clock ("the current time", "what time it
is", "a clock"), and name no other live thing: "I don't have access to real-time
information, so I can't tell you tomorrow's weather in Chicago" denied the weather, and
the reply became "Sunday, October 25, 2026, 3:22:15 PM EDT" (live chat, 2026-10-25). The
time or date of something else ("the time of the eclipse", "the date of the next
election", "the current time in Tokyo") is no ask for the local clock, and neither is a
question about another place's clock or a scheduled time.
"""

from __future__ import annotations

import re

from app.services.text_normalize import collapse_ws, straighten_apostrophes
from app.services.time_context import is_remote_time_question, is_scheduled_event_time_question

# Linear substrings, one per way a model says it has no clock or no live data.
_DENIALS = (
    "don't have access to the current clock",
    "do not have access to the current clock",
    "don't have access to real-time",
    "do not have access to real-time",
    "don't have real-time",
    "do not have real-time",
    "unable to access real-time",
    "can't access real-time",
    "cannot access real-time",
    "can't access the current",
    "cannot access the current",
    "don't have access to a clock",
    "don't have access to the clock",
    "no access to real-time",
    "no access to a clock",
    "no access to the clock",
    "can't tell you the exact time",
    "cannot tell you the exact time",
    "can't tell the current time",
    "cannot tell the current time",
    "can't tell you the current time",
    "cannot tell you the current time",
    "unable to check the time",
    "can't check the time",
    "cannot check the time",
    "check a device nearby",
)
_MAX_LEN = 400
# The local clock named, as a phrase: "the current time", "what time it is", "a clock".
_CURRENT_CLOCK = re.compile(
    r"\b(?:(?:current|exact|local)\s+(?:local\s+)?(?:time|date)(?:\s+(?:and|or)\s+(?:time|date))?"
    r"|what\s+(?:time|day|date)\s+it\s+is"
    r"|today's\s+date"
    r"|the\s+(?:time|date)\s+(?:right\s+)?now"
    r"|(?<!around\s)(?:a|the|your|any|real-time)\s+clocks?)\b",
    re.IGNORECASE,
)
# "The current time in Tokyo", "the exact time of the eclipse": another thing's clock.
# Only the user's own place ("in your area", "for you") keeps it the local one.
_ELSEWHERE = re.compile(
    r"\s+(?:of|for|in|at)\b(?!\s+(?:your\s+(?:location|area|city|region|time\s?zone)|you)\b)",
    re.IGNORECASE,
)
# Another live thing the reply names: the denial is about that, not the clock.
_OTHER_LIVE = re.compile(
    r"\b(?:weather|forecast|temperature|rain|snow|scores?|games?|match|news|prices?|"
    r"stocks?|markets?|traffic|flights?|events?|schedules?|standings)\b",
    re.IGNORECASE,
)
# "What time is it in my time zone" asks the local clock in other words.
_IN_MY_PLACE = re.compile(r"\bin\s+(?:my|our|here)\b", re.IGNORECASE)


def _names_the_clock(reply: str) -> bool:
    return any(
        _ELSEWHERE.match(reply, found.end()) is None for found in _CURRENT_CLOCK.finditer(reply)
    )


def _asks_another_clock(asked: str) -> bool:
    """Another place's clock, or a scheduled time ("what time is my flight")."""
    if is_remote_time_question(asked) and not _IN_MY_PLACE.search(asked):
        return True
    # "What time is it? I have a meeting at 4" still asks the clock.
    return is_scheduled_event_time_question(asked) and "what time is it" not in asked.lower()


def model_denies_clock(reply: str, asked: str = "") -> bool:
    """True when a short ``reply`` claims it cannot read the current time for ``asked``."""
    cleaned = straighten_apostrophes(collapse_ws(reply))
    if not cleaned or len(cleaned) > _MAX_LEN:
        return False
    if asked and _asks_another_clock(straighten_apostrophes(asked)):
        return False
    lowered = cleaned.lower()
    if not any(mark in lowered for mark in _DENIALS):
        return False
    return _names_the_clock(cleaned) and _OTHER_LIVE.search(cleaned) is None

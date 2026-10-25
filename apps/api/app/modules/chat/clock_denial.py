"""A short reply that says it cannot see the clock, which the app always has.

The finalize pass swaps such a reply for the clock (``finalize_text.fix_clock``). A
denial counts only when its own sentence names the time, the clock or the date, and no
other live thing: "I don't have access to real-time information, so I can't tell you
tomorrow's weather in Chicago" denied the weather, and the reply became "Sunday, October
25, 2026, 3:22:15 PM EDT" (live chat, 2026-10-25). A question about another place's
clock or a scheduled time ("what time is it in Tokyo", "what time is my flight") is not
answered by the local clock either.
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
    "don't have access to a clock",
    "don't have access to the clock",
    "no access to real-time",
    "no access to a clock",
    "no access to the clock",
    "can't tell you the exact time",
    "cannot tell you the exact time",
    "can't tell the current time",
    "cannot tell the current time",
    "check a device nearby",
)
_MAX_LEN = 400
# The clock named as what the reply cannot give. "real-time" is no mention of the time.
_NAMES_THE_CLOCK = re.compile(r"(?<![\w-])(?:time|clock|date)\b", re.IGNORECASE)
# Another live thing the sentence names: the denial is about that, not the clock.
_OTHER_LIVE = re.compile(
    r"\b(?:weather|forecast|temperature|rain|snow|scores?|games?|match|results?|news|"
    r"prices?|stocks?|markets?|traffic|flights?|events?|schedules?|standings|updates?)\b",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def model_denies_clock(reply: str, asked: str = "") -> bool:
    """True when a short ``reply`` claims it cannot read the current time for ``asked``."""
    cleaned = collapse_ws(reply)
    if not cleaned or len(cleaned) > _MAX_LEN:
        return False
    if asked and (is_remote_time_question(asked) or is_scheduled_event_time_question(asked)):
        return False
    for sentence in _SENTENCE_END.split(cleaned):
        lowered = straighten_apostrophes(sentence).lower()
        if not any(mark in lowered for mark in _DENIALS):
            continue
        if _NAMES_THE_CLOCK.search(sentence) and not _OTHER_LIVE.search(sentence):
            return True
    return False

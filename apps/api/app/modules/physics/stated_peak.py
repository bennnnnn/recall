"""A motion's top stated as a fact about it: its result, never where it starts.

"A ball thrown straight up at 10 m/s reaches a maximum height of 20 m. How long does it take
to reach the top?" (live round, 2026-11-21): the launch-height reader took "height of 20 m"
for a starting height, verified t = v₀/g = 1.02 s, and drew the ball thrown from a 20 m
ledge. The 20 m is what the throw reaches, and at 10 m/s nothing reaches it: thrown up at
10 m/s a ball rises v₀²/2g = 5.10 m. So:

- a stated top is never a launch height (``without_stated_peaks`` hides it from that
  reader);
- the top the question's own values give is checked against the one it states
  (``peak_conflict``): values that contradict each other have no answer as written, and
  the reply says so instead of a verified card for one reading of them.

Only a top said to be one is read ("maximum height", "max height", "peak height",
"greatest height", "highest point"): "how long to reach a height of 20 m" asks for a
position on the way, which no top has to equal.
"""

from __future__ import annotations

import re

from app.modules.physics.extractors.unit_patterns import (
    LENGTH_UNIT_PATTERN,
    NUMBER,
    VELOCITY_UNIT_PATTERN,
)

# "a maximum height of 20 m", "max height = 20 m", "its highest point is 20 m above the
# ground", "a peak height of 5.1 m". The value follows within a few joining words.
_STATED_PEAK = re.compile(
    r"\b(?:(?:maximum|max\.?|peak|greatest)\s+(?:height|altitude)|highest\s+point)\s*"
    r"(?:(?:of|is|was|will\s+be|=|:|at|reached|reaches)\s*){0,2}"
    rf"(?P<value>{NUMBER})\s*(?P<unit>{LENGTH_UNIT_PATTERN})\b(?![/^])",
    re.IGNORECASE,
)
# The words that state the top, read out with it: "and reaches a maximum height of 20 m".
# Read back word by word from the top's phrase, never by a pattern searched from every place.
_STATING_WORDS = frozenset(
    {
        *("and", "which", "that", "it", "then", "just", "finally", "to", "up"),
        *("reach", "reaches", "reached", "rises", "rose", "attains", "attained", "climbs"),
        *("goes", "went", "has", "had", "with", "a", "an", "its", "the"),
    }
)
_STATING_REACH = 8
# A launch speed stated: "at 10 m/s", "with 15 km/h".
_LAUNCH_SPEED = re.compile(
    rf"(?<![\w.])(?:{NUMBER})\s*(?:{VELOCITY_UNIT_PATTERN})(?![\w/])", re.IGNORECASE
)


def stated_peaks(text: str) -> list[re.Match[str]]:
    """Each top the text states, value and unit."""
    return list(_STATED_PEAK.finditer(text))


def without_stated_peaks(text: str) -> str:
    """``text`` with each stated top's value blanked, same length: a launch height's reader
    never reads it."""
    for match in reversed(stated_peaks(text)):
        start, end = match.start("value"), match.end("unit")
        text = text[:start] + " " * (end - start) + text[end:]
    return text


def without_redundant_peaks(text: str) -> str:
    """``text`` with each top it states read out, when it states the launch speed too: the
    launch decides the top, so the stated one is a check of the values (``peak_conflict``)
    and no reader takes it for a given. Without a launch speed the top may be what the
    question gives ("reaches a maximum height of 20 m: how fast was it thrown?")."""
    peaks = stated_peaks(text)
    if not peaks or _LAUNCH_SPEED.search(text) is None:
        return text
    for match in reversed(peaks):
        start = _stating_start(text, match.start())
        text = text[:start].rstrip(" ,") + text[match.end() :]
    return text


def _stating_start(text: str, end: int) -> int:
    """Where the words stating the top begin: back from ``end`` over the stating words."""
    start = end
    for _ in range(_STATING_REACH):
        at = start
        while at > 0 and text[at - 1] in " ,":
            at -= 1
        word_end = at
        while at > 0 and text[at - 1].isalpha():
            at -= 1
        if at == word_end or text[at:word_end].lower() not in _STATING_WORDS:
            break
        start = at
    return start

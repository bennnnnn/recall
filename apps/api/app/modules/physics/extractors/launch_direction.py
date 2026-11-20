"""A quantity's direction from the words, read once for every physics reader that signs one.

A launch's (``launched_downward``), for the projectile extractor and the law binder:
"thrown down at an angle of 30°" and "kicked down off a 45 m cliff at 15 m/s at 30°" launch
30° below the horizontal. Read as above it, a 45 m cliff's throw landed in 3.89 s instead of
2.36 s (review, 2026-11-16 and PR #2490). A body's along a line (``moving_sense``), for a
collision's two velocities: east or west, left or right, +x or -x."""

from __future__ import annotations

import re

# A launch verb's own direction: "thrown down at an angle of 30°", "projected downward at
# 15 m/s", "thrown upward". Never another clause's word: "gravity acts downward" says
# nothing of the throw.
_LAUNCH_VERB = (
    r"\b(?:thrown|throws?|aimed|directed|projected|fired|launched|kicked|hit)\s+(?:\w+\s+){0,2}?"
)
# Only a "down" that is the launch's own: "downward", "down at 15 m/s", "down from", "down
# off a cliff", "straight down". "hit down the fairway" is a place, and "thrown ... to hit
# the water down below" a target clause, never the throw's direction.
_DOWNWARD_LAUNCH_RE = re.compile(
    r"(?<!\bto\s)" + _LAUNCH_VERB + r"(?:downwards?\b|down(?=\s+(?:at|from|off|with|into|"
    r"toward|towards|over)\b|\s*(?:[,.;!?]|$)))",
    re.IGNORECASE,
)
_UPWARD_LAUNCH_RE = re.compile(_LAUNCH_VERB + r"up(?:wards?)?\b", re.IGNORECASE)
# The angle named above the horizontal: no downward word elsewhere makes it negative.
_ABOVE_HORIZONTAL_RE = re.compile(
    r"\s*(?:degrees?|deg|°)?\s*(?:above|over)\s+(?:the\s+)?horizontal\b", re.IGNORECASE
)
# Read right after the angle: "30° below the horizontal", "at 20 degrees downward".
_BELOW_HORIZONTAL_RE = re.compile(
    r"\s*(?:degrees?|deg|°)?\s*(?:below|beneath|under)\s+(?:the\s+)?horizontal\b"
    r"|\s*(?:degrees?|deg|°)?\s*(?:down(?:wards?)?|downward)\b",
    re.IGNORECASE,
)
_SENTENCE_END_RE = re.compile(r"[.?!;](?!\d)")


def launched_downward(lower: str, start: int, end: int) -> bool:
    """Whether the launch angle at ``start:end`` points below the horizontal: the words right
    after it say so, or a downward launch verb anywhere in its sentence does, unless an
    upward one there or "above the horizontal" after it says otherwise."""
    if _BELOW_HORIZONTAL_RE.match(lower, end) is not None:
        return True
    first = max((m.end() for m in _SENTENCE_END_RE.finditer(lower, 0, start)), default=0)
    last = _SENTENCE_END_RE.search(lower, end)
    sentence = lower[first : last.start() if last else len(lower)]
    return (
        _DOWNWARD_LAUNCH_RE.search(sentence) is not None
        and _UPWARD_LAUNCH_RE.search(sentence) is None
        and _ABOVE_HORIZONTAL_RE.match(lower, end) is None
    )


# A body's direction along a line: "a 0.5 kg puck moving east at 4 m/s", "in the +x
# direction", "in the negative x-direction". A sign before an axis is its sense; the minus
# may be typed as the minus sign or a dash. Read once, for a collision's two bodies.
_LINE_DIRECTION_RE = re.compile(
    r"\b(east|west|north|south|left|right)(?:wards?)?\b"
    r"|(?<![\w.])([+\-\u2212\u2013]|\bpositive\s+|\bnegative\s+)([xy])(?:[\s-]*(?:direction|axis))?\b",
    re.IGNORECASE,
)
_AXIS_SIGN = {
    "east": ("east-west", 1),
    "west": ("east-west", -1),
    "north": ("north-south", 1),
    "south": ("north-south", -1),
    "right": ("left-right", 1),
    "left": ("left-right", -1),
}
_NEGATIVE_SIGNS = frozenset({"-", "\u2212", "\u2013", "negative"})
# A body said to move two ways at once ("east ... north").
TWO_WAYS = ("", 0)


def _sense(match: re.Match[str]) -> tuple[str, int]:
    """The axis and sign one direction names: east is +1 on east-west, "-x" is -1 on x."""
    if match[1]:
        return _AXIS_SIGN[match[1].lower()]
    return match[3].lower(), -1 if match[2].strip().lower() in _NEGATIVE_SIGNS else 1


def moving_sense(text: str, start: int, end: int) -> tuple[str, int] | None:
    """The one direction a body moves along a line, as the words at ``start:end`` give it:
    its axis and sign (east is +1 on east-west, "-x" -1 on x); ``TWO_WAYS`` when they give
    two, None when none. The launch's sense above is ``launched_downward``'s; a collision
    signs each body's velocity by this one (owner's phone, 2026-11-17: a 1.00 kg object
    "in the -x direction" read as moving the first one's way, 1.5 J lost for 13.5 J)."""
    found = {_sense(match) for match in _LINE_DIRECTION_RE.finditer(text, start, end)}
    if len(found) > 1:
        return TWO_WAYS
    return next(iter(found), None)

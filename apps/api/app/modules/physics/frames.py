"""Which frame each stated speed is measured in, and the frame a question asks in.

Relativistic velocity addition takes a mover's speed in one frame and a second body's speed
relative to the mover, and gives the second body's speed in the first frame. A speed the
question states in that first frame is the result already: "seen from Earth a probe moves
at 0.95c; the ship moves at 0.8c: its speed in the ship's frame?" was added up to 0.994c
for 0.625c (review 2026-11-12). So the law answers only when one stated speed is relative
to a mover and the question does not ask in the mover's frame.
"""

from __future__ import annotations

import re

from app.modules.physics.ask import ask_clause
from app.modules.physics.givens import scan_givens

# The marker the binder's excludes read (``binding._with_markers``).
FRAMES_UNREAD_MARKER = "framesunread"
# Frames at rest in the problem: no body there moves at a stated speed.
_AT_REST = frozenset(
    {"earth", "ground", "lab", "laboratory", "sun", "planet", "station", "rest", "observer"}
)
_THE = r"(?:the\s+|an?\s+)?"
_FRAME = re.compile(
    rf"\b(?:relative\s+to|with\s+respect\s+to|in\s+the\s+frame\s+of|according\s+to"
    rf"|(?:seen|measured|observed)\s+(?:from|by|in)|as\s+(?:seen|measured)\s+(?:from|by))"
    rf"\s+{_THE}(?P<a>[a-z]+)"
    rf"|\bin\s+{_THE}(?P<b>[a-z]+)(?:['\u2019]s)?\s+frame\b"
    rf"|\b(?:observers?|someone|people)\s+(?:on|aboard|in)\s+{_THE}(?P<c>[a-z]+)"
    rf"|\bdoes\s+{_THE}(?P<d>[a-z]+)\s+(?:see|measure|observe|record)\b"
)
_SENTENCE_BREAK = re.compile(r"[.;?!](?:\s|$)")


def _frame_in(window: str) -> str | None:
    found = _FRAME.search(window)
    if found is None:
        return None
    return next(group for group in found.groups() if group)


def _speed_frames(lower: str, asked_at: int) -> list[str | None]:
    """The frame each stated speed is given in: the words after it up to the next value
    ("0.5c relative to the ship"), or, for a sentence's first value, the words before it
    ("Seen from Earth, a probe moves at 0.95c")."""
    speeds = [
        given
        for given in scan_givens(lower[:asked_at])
        if given.dimension == "[length]^1 * [time]^-1"
    ]
    frames: list[str | None] = []
    for index, given in enumerate(speeds):
        following = speeds[index + 1].start if index + 1 < len(speeds) else asked_at
        stop = _SENTENCE_BREAK.search(lower, given.end, following)
        frame = _frame_in(lower[given.end : stop.start() if stop else following])
        breaks = [match.end() for match in _SENTENCE_BREAK.finditer(lower, 0, given.start)]
        start = max(breaks, default=0)
        first = index == 0 or speeds[index - 1].end <= start
        if frame is None and first:
            frame = _frame_in(lower[start : given.start])
        frames.append(frame)
    return frames


def adds_speeds_across_frames(text: str) -> bool:
    """One stated speed is relative to a mover, the other is in another frame, and the
    question asks in that other frame (or names none): what velocity addition answers."""
    lower = text.lower()
    clause = ask_clause(lower)
    asked_at = len(lower) if clause is None else lower.rfind(clause)
    asked_at = len(lower) if asked_at < 0 else asked_at
    frames = _speed_frames(lower, asked_at)
    asked = None if clause is None else _frame_in(clause)
    if len(frames) != 2 or frames[0] == frames[1]:
        return False
    movers = [frame for frame in frames if frame is not None and frame not in _AT_REST]
    if len(movers) == 2:
        return asked in frames
    if len(movers) != 1:
        return False
    return asked is None or asked in _AT_REST or (asked in frames and asked != movers[0])

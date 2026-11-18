"""A launch's direction, read once for the projectile extractor and the law binder: "thrown
down at an angle of 30°" and "kicked down off a 45 m cliff at 15 m/s at 30°" launch 30°
below the horizontal. Read as above it, a 45 m cliff's throw landed in 3.89 s instead of
2.36 s (review, 2026-11-16 and PR #2490)."""

from __future__ import annotations

import re

# A launch verb's own direction: "thrown down at an angle of 30°", "projected downward at
# 15 m/s", "thrown upward". Never another clause's word: "gravity acts downward" says
# nothing of the throw.
_LAUNCH_VERB = (
    r"\b(?:thrown|throws?|aimed|directed|projected|fired|launched|kicked|hit)\s+(?:\w+\s+){0,2}?"
)
_DOWNWARD_LAUNCH_RE = re.compile(_LAUNCH_VERB + r"down(?:wards?)?\b", re.IGNORECASE)
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

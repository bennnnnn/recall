"""Whether a stated share of a decaying sample is what is left or what has gone.

"How long until 25% remains?" and "How long for 75% to decay?" ask the same time: a share
that decayed, decomposed, reacted or was used up leaves 1 - p. Read as the share left,
"How long for 75% of a radioactive sample to decay, half-life 10 years?" was verified as
4.15 years for 20 (audit 2026-11-13). A share the words call neither, or both ("75% of the
sample"), is not read, and the law declines.

The binder reads the answer as markers (``binding._with_markers``): the share-left law
gives way to the share-gone law, and an unsaid share rules out both.
"""

from __future__ import annotations

import re
from typing import Literal

SHARE_GONE_MARKER = "sharegone"
SHARE_UNSAID_MARKER = "shareunsaid"

# A share of the sample: "75%", "75 percent", "1/16".
_SHARE = re.compile(r"(?<![\d.])(?:\d+(?:\.\d+)?\s*(?:%|per\s?cent\b)|\d+\s*/\s*\d+(?![\d.]))")
_CLAUSE_END = re.compile(r"[.?!;](?=\s|$)")
# Said before the share, what it ended at: "decays to 25%", "only 1/16", "falls to".
_LEFT_BEFORE = re.compile(
    r"(?:\b(?:decay|decompos|drop|fall|fell|reduc|declin|decreas|down)\w*\s+to"
    r"|\bonly|\bjust)\s*$"
)
# Said after it: "25% remains", "75% of the sample is left".
_LEFT_AFTER = re.compile(r"\b(?:remains?|remaining|left|stays?|still\s+there)\b")
# Said before the share, what went: "loses 75% of its activity", "drops by 75%".
_GONE_BEFORE = re.compile(
    r"\b(?:los(?:e|es|t|ing)|(?:decay|drop|fall|fell|reduc|declin|decreas)\w*\s+by)\s*$"
)
# Said after it, what happens to it: "75% of it to decay", "75% has decomposed". A verb with
# "to" after it says where the share ends ("75% of the activity decays to ..."), and is no
# share gone.
_GONE_AFTER = re.compile(
    r"\b(?:decay(?:s|ed)?|decompose[sd]?|disintegrate[sd]?|react(?:s|ed)?|used\s+up"
    r"|consumed|gone|lost|broken\s+down|breaks?\s+down)\b(?!\s+(?:to|down\s+to|until)\b)"
)


Reading = Literal["left", "gone", "unsaid"]


def share_reading(lower: str) -> Reading | None:
    """What the stated share is: left, gone or unsaid; None when no share is stated."""
    readings: set[Reading] = set()
    for share in _SHARE.finditer(lower):
        start = max((end.end() for end in _CLAUSE_END.finditer(lower, 0, share.start())), default=0)
        stop = _CLAUSE_END.search(lower, share.end())
        before = lower[start : share.start()]
        after = lower[share.end() : stop.start() if stop is not None else len(lower)]
        left = bool(_LEFT_BEFORE.search(before) or _LEFT_AFTER.search(after))
        gone = bool(_GONE_BEFORE.search(before) or _GONE_AFTER.search(after))
        readings.add("left" if left and not gone else "gone" if gone and not left else "unsaid")
    if not readings:
        return None
    return readings.pop() if len(readings) == 1 else "unsaid"


def share_markers(lower: str) -> str:
    """The markers the binder reads the share by: one for a share gone, one for a share it
    cannot read; none for a share left or no share at all."""
    reading = share_reading(lower)
    if reading == "gone":
        return SHARE_GONE_MARKER
    return SHARE_UNSAID_MARKER if reading == "unsaid" else ""

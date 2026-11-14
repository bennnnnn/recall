"""Whether a stated share of a decaying sample is what is left or what has gone.

"How long until 25% remains?" and "How long for 75% to decay?" ask the same time: a share
that decayed, decomposed, reacted or was used up leaves 1 - p. Read as the share left,
"How long for 75% of a radioactive sample to decay, half-life 10 years?" was verified as
4.15 years for 20 (audit 2026-11-13). A share the words call neither, or both ("75% of the
sample"), is not read, and the law declines.

The asked share is read the same way: "what percentage has decayed?" asks 1 - p, never the
share left. The binder reads both as markers (``binding._with_markers``): a law of the share
left gives way to its share-gone twin, and an unsaid share rules out both.
"""

from __future__ import annotations

import re
from typing import Literal

from app.modules.physics.ask import ask_clause
from app.modules.physics.givens import Given, scan_givens

SHARE_GONE_MARKER = "sharegone"
SHARE_UNSAID_MARKER = "shareunsaid"
# The question asks how much went: the laws of what is left give way.
ASKED_GONE_MARKER = "askedgone"

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


# A negation whose scope is the verb right after it: "not", "never", "n't", "yet to", "still to",
# with "yet", "been" or "have" between ("has not yet decayed", "are yet to decay").
_NEGATED = re.compile(
    r"\b(?:not|never|n't|yet\s+to|still\s+to)(?:\s+(?:yet|been|have|has|had|to))*\s+$"
)

Reading = Literal["left", "gone", "unsaid"]


def share_reading(lower: str) -> Reading | None:
    """What the stated share is: left, gone or unsaid; None when no share is stated.

    A share is any stated part of the whole, however it is written: "75%", "3/4" (which
    the number reader has already written 0.75) or "0.75". Read only as a percent or a
    fraction, "How long until 3/4 of it has decayed?" was the share left, 4.15 years for 20
    (review 2026-11-13).
    """
    readings: set[Reading] = set()
    for given in scan_givens(lower):
        if not _a_share(given):
            continue
        start = max((end.end() for end in _CLAUSE_END.finditer(lower, 0, given.start)), default=0)
        stop = _CLAUSE_END.search(lower, given.end)
        before = lower[start : given.start]
        after = lower[given.end : stop.start() if stop is not None else len(lower)]
        readings.add(_read(before, after))
    if not readings:
        return None
    return readings.pop() if len(readings) == 1 else "unsaid"


def asked_share(text: str) -> Reading | None:
    """What an asked share is: "what percentage has decayed" asks the share gone, "what
    fraction remains" the share left; None when the ask says neither. Answered as the share
    left, "What percentage of a sample has decayed after 2 half-lives?" was 25% for 75%."""
    clause = ask_clause(text)
    if clause is None:
        return None
    reading = _read("", clause.lower())
    return None if reading == "unsaid" else reading


def _a_share(given: Given) -> bool:
    """A part of a whole: a percent up to 100, or a bare number up to 1."""
    if given.unit in {"%", "percent", "per cent"}:
        return 0 < given.value <= 100
    return not given.unit and given.dimension is None and 0 < given.value <= 1


def _read(before: str, after: str) -> Reading:
    gone_verbs = list(_GONE_AFTER.finditer(after))
    # "has not decayed", "is yet to decay": a share gone, negated, is the share left.
    negated = [verb for verb in gone_verbs if _NEGATED.search(after, 0, verb.start())]
    left = bool(_LEFT_BEFORE.search(before) or _LEFT_AFTER.search(after) or negated)
    gone = bool(_GONE_BEFORE.search(before) or len(negated) < len(gone_verbs))
    return "left" if left and not gone else "gone" if gone and not left else "unsaid"


def share_markers(lower: str) -> str:
    """The markers the binder reads the shares by: a stated share gone or unread, and an
    asked share gone; none for a share left or no share at all."""
    reading = share_reading(lower)
    markers = [
        SHARE_GONE_MARKER if reading == "gone" else "",
        SHARE_UNSAID_MARKER if reading == "unsaid" else "",
        ASKED_GONE_MARKER if asked_share(lower) == "gone" else "",
    ]
    return " ".join(marker for marker in markers if marker)

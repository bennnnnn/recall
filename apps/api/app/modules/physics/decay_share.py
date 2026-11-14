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


# A negation whose scope is the verb right after it: "not", "never", "n't" ("hasn't"), "yet to",
# "still to", "left to", "failed to", with "yet", "been" or "have" between ("has not yet
# decayed", "are yet to decay"). The contraction has no word boundary before its "n".
_NEGATED = re.compile(
    r"(?:\b(?:not|never|(?:yet|still|left)\s+to|fail(?:s|ed)?\s+to)|n['\u2019]t)"
    r"(?:\s+(?:yet|been|have|has|had|to))*\s+$"
)
# A mention the ask itself sets aside: "how much has decayed, not how much is left".
_NOT_BEFORE = re.compile(r"\bnot(?:\s+\w+){0,3}\s+$")

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
    fraction remains" the share left, and an ask naming both is "unsaid"; None when the ask
    names neither. Answered as the share left, "What percentage of a sample has decayed after 2
    half-lives?" was 25% for 75%. A mention the ask sets aside ("has decayed, not how much is
    left") is not what it asks (review 2026-11-14)."""
    sentence = _asked_sentence(text)
    if sentence is None:
        return None
    gone_verbs = list(_GONE_AFTER.finditer(sentence))
    # "Has not decayed" is the share left; "not how much has decayed" sets that ask aside.
    negated = [verb for verb in gone_verbs if _NEGATED.search(sentence, 0, verb.start())]
    gone = any(
        verb not in negated and not _NOT_BEFORE.search(sentence, 0, verb.start())
        for verb in gone_verbs
    )
    left = bool(negated) or any(
        not _NOT_BEFORE.search(sentence, 0, word.start()) for word in _LEFT_AFTER.finditer(sentence)
    )
    if left and gone:
        return "unsaid"
    return "left" if left else "gone" if gone else None


def _asked_sentence(text: str) -> str | None:
    """The sentence the ask is in, whole: "How much has decayed, not how much is left, after
    2 half-lives?" asks its first clause, where the ask's own clause starts at its last."""
    clause = ask_clause(text)
    if clause is None:
        return None
    lower = text.lower()
    at = lower.rfind(clause.lower())
    if at < 0:
        return clause.lower()
    start = max((end.end() for end in _CLAUSE_END.finditer(lower, 0, at)), default=0)
    stop = _CLAUSE_END.search(lower, at + len(clause))
    return lower[start : stop.start() if stop is not None else len(lower)]


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

"""Which percent in a money request is its rate, and which a share of the price put down.

"A 400k house with 20% down at 6.5%" is a 6.5% rate on 320 000: a percent said as a rate
("at 6.5%", "the rate is 6%", "6% apr") is the rate, and one said with "down" closing its
phrase ("20% down", "put 20% down on", "a down payment of 20%") is a share. A review
(2026-10-25) found looser rules losing the rate of "car loan 25000 at 7% down payment of
5000" and "6.5% down 0.25% from last month" to a share; the parent reader had taken "20%
down" as the rate.
"""

from __future__ import annotations

import re

PERCENT = r"(?P<pct>\d{1,3}(?:\.\d{1,4})?)\s?(?:%|percent\b|per\s?cent\b|pct\b)"
_RATE = re.compile(PERCENT, re.I)
# "Down payment of 20%", "put 20% down": a share of the price. "5000 down 6.9%" (the 5000
# was put down), "the rate went down 1%" and "6% down from 7%" give none. "Down" must close
# the share's phrase (an end, a comma, "at", "and", "with", "on", "for"): a review
# (2026-10-25) found "at 7% down payment of 5000" and "6.5% down 0.25% from last month"
# losing their rate to a share. "20% down 6.5%" is a share and its rate.
_SHARE_AFTER = re.compile(
    r"\s?down(?:\s?payment)?(?=\s*(?:$|[,;.!?)]|(?:at|and|with|on|for)\b))"
    r"|\s?down\s\d{1,3}(?:\.\d{1,4})?\s?(?:%|percent\b)"
    r"(?!\s(?:from|since|ago|than|last|this|compared)\b)",
    re.I,
)
# A percent said as a rate ("at 6%", "the rate is 6%", "6% apr") is the rate, never a share.
_RATE_BEFORE = re.compile(
    r"\b(?:at|(?:interest\s)?(?:rates?|aprs?|apy|interest)(?:\s(?:is|are|was|were|of|at|to|be))?)"
    r"\s?$",
    re.I,
)
_RATE_AFTER = re.compile(r"\s?(?:apr|apy|rate|interest)\b", re.I)
_NUMBER_NEXT = re.compile(r"\s*,?\s*[$€£¥₹₦]?\d")
_SHARE_BEFORE = re.compile(
    r"\b(?:down\s?payment(?:\s(?:of|is|was|at))?|put(?:ting)?(?:\sdown)?)\s?$", re.I
)
# "The rate went down 1% to 5.5%", "from 7% to 6%": the rate is the one it goes to.
_TO_ANOTHER_RATE = re.compile(r"\s?(?:to|->|→)\s?\d{1,3}(?:\.\d{1,4})?\s?(?:%|percent\b)", re.I)
_SUM_END = re.compile(r"\d[\d,.]*\s?(?:k|m|grand|thousand|dollars?|bucks)?\s*$", re.I)


def stated_rate(text: str) -> float | None:
    """The yearly rate the message gives: one said as a rate first ("at 6%"), else the first
    percent. "20% down" is a share of the price, not a rate."""
    found = [
        match
        for match in _RATE.finditer(text)
        if not _down_share(text, match) and not _TO_ANOTHER_RATE.match(text, match.end())
    ]
    said = next((match for match in found if _said_as_rate(text, match)), None)
    match = said or (found[0] if found else None)
    return float(match["pct"]) if match is not None else None


def _said_as_rate(text: str, match: re.Match[str]) -> bool:
    before = text[max(0, match.start() - 24) : match.start()]
    return bool(_RATE_BEFORE.search(before) or _RATE_AFTER.match(text, match.end()))


def stated_down_share(text: str) -> float | None:
    """The percent of the price put down ("with 20% down"), or None."""
    return next(
        (float(match["pct"]) for match in _RATE.finditer(text) if _down_share(text, match)),
        None,
    )


def _down_share(text: str, match: re.Match[str]) -> bool:
    if _said_as_rate(text, match):
        return False
    if _SHARE_AFTER.match(text, match.end()):
        return True
    before = text[max(0, match.start() - 32) : match.start()]
    cue = _SHARE_BEFORE.search(before)
    return (
        cue is not None
        # "100k down payment 6.25%": the down payment was the sum before it.
        and not (cue.group(0).startswith("down") and _SUM_END.search(before[: cue.start()]))
        and _NUMBER_NEXT.match(text, match.end()) is None
    )

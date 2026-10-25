"""One follow-up line read by a positive grammar: a new term, a new rate, or nothing.

The server works two changes only, the two that are both common and safe: the live
"hmm what if i only do 3 years instead" and the app's own follow-up chips.

- A term: "3 years", "36 months", "over 4 years", "a 15 year mortgage", "pay it off in 2
  years" (and, for savings, "save for 20 years").
- A rate with its words: "at 6%", "6% apr", "6% interest", "the rate is 6%", "a 6% rate".

The line must ask for a change: it opens (after "hmm", "ok", "so") with "what if", "what
about", "how about", "and", "or", "make it", "try", "do", "go with" or "i only do", or it
ends with "instead" or "instead of N". Every other word must belong to a term or rate
phrase or be filler; any word left over means the line is about something else, and the
model answers it as before. Four reviews (2026-10-25) of wider readers found shapes they
misread into numbers the reply then called the answer: a model year as a price, a card
payment as an APR, "it's been 5 years" as a 5-year mortgage, "what's 7%?" as a new rate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import partial

from app.modules.money.read import DURATION, PERCENT

_MAX_CHARS = 200
_PCT = rf"(?<![\w.]){PERCENT}"
_TIME = rf"(?<![\w.]){DURATION}"
_RATE_WORD = r"(?:interest\s)?(?:rates?|aprs?|apy|interest)"
_FRAME_START = re.compile(
    r"^\W*(?:(?:hmm+|ok(?:ay)?|so)\W+)*"
    r"(?:what\sif|what\sabout|how\sabout|and|or|make\sit|try|do|go\swith|i\sonly\sdo)\b",
    re.I,
)
_FRAME_END = re.compile(
    r"\binstead(?:\sof\s(?:the\s)?\d[\d,.]*(?:\s?(?:%|percent|years?|yrs?|months?|mos?))?)?\W*$",
    re.I,
)
# "The rate is 6% for 10 years", "0% for 18 months": a rate for a while, not a loan's rate
# and term. "At 6% for 5 years" states the loan.
_RATE_FOR_A_WHILE = re.compile(
    r"(?<!\bat\s)(?<![\w.])\d{1,3}(?:\.\d{1,4})?\s?(?:%|percent)\s(?:\w+\s)?for\s\d", re.I
)
# Not a change of this loan: a person's age ("what if I'm 30 years"), time gone by ("it's
# been 5 years"), an interest-only loan (another kind of loan).
_NOT_A_CHANGE = re.compile(
    r"\b(?:i|we|he|she|they|you)(?:'m|'re|\s(?:am|are|was|were))\b|\b(?:im|age|aged|been)\b"
    r"|\binterest[\s-]only\b",
    re.I,
)
_TERM_PHRASES = [
    (rf"\bpay(?:ing)?\s(?:it\s)?off\s(?:in|within|over)\s{_TIME}", False),
    (rf"\b(?:keep\s)?(?:sav(?:e|ing)|invest(?:ing)?)\sfor\s{_TIME}", True),
    (rf"\b(?:(?:over|for|a|an|the|with|to)\s){{0,2}}{_TIME}(?:\s(?:term|loan|mortgage|plan))?",
     False),
]  # fmt: skip
_RATE_PHRASES = [
    rf"\b(?:(?:the|my|a|an)\s)?{_RATE_WORD}(?:\srate)?\s(?:is|was|were|be|of)\s{_PCT}",
    rf"\bat\s{_PCT}",
    rf"\b{_PCT}\s(?:apr|apy|interest(?:\srate)?|rate|fixed)\b",
]
_TERMS = [(re.compile(pattern, re.I), saving) for pattern, saving in _TERM_PHRASES]
_RATES = [re.compile(pattern, re.I) for pattern in _RATE_PHRASES]
# Words a change line may hold beside its frame and its phrases. "Payment", "monthly",
# "make", "paid", "been" and "then" are never filler.
_FILLER = frozenset(
    "i we it it's its is was were be the a an only do just with go please if what about "
    "and so ok okay hmm hmmm".split()
)
_WORDS = re.compile(r"[a-z0-9']+|[%$€£¥₹₦]")


@dataclass
class Change:
    """A new rate and a new term ("3", "years"), either or both."""

    rate: float | None = None
    term: tuple[float, str] | None = None
    # "Save for 20 years": a term only a savings plan takes.
    saving_term: bool = False
    clash: bool = False

    def take_rate(self, match: re.Match[str]) -> str:
        self.clash = self.clash or self.rate is not None
        self.rate = float(match["pct"])
        return " " * len(match.group(0))

    def take_term(self, match: re.Match[str], saving: bool) -> str:
        self.clash = self.clash or self.term is not None
        self.term = (float(match["n"]), match["unit"])
        self.saving_term = saving
        return " " * len(match.group(0))


def read_change(line: str) -> Change | None:
    """The new term and rate ``line`` asks for, or None when it asks for no such change."""
    text = " ".join(line.lower().replace("\u2019", "'").split())
    if not text or len(text) > _MAX_CHARS:
        return None
    if _RATE_FOR_A_WHILE.search(text) or _NOT_A_CHANGE.search(text):
        return None
    start, end = _FRAME_START.match(text), _FRAME_END.search(text)
    if start is None and end is None:
        return None
    if end is not None:
        text = text[: end.start()]
    if start is not None:
        text = text[start.end() :]
    change = Change()
    for pattern, saving in _TERMS:
        text = pattern.sub(partial(change.take_term, saving=saving), text)
    for pattern in _RATES:
        text = pattern.sub(change.take_rate, text)
    if change.rate is None and change.term is None:
        return None
    if change.clash or any(word not in _FILLER for word in _WORDS.findall(text)):
        return None
    return change

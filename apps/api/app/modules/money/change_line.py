"""One follow-up line read by a positive grammar: a new term, a new rate, or nothing.

The server works two changes only, the two that are both common and safe: the live
"hmm what if i only do 3 years instead" and the app's own follow-up chips.

- A term: "3 years", "36 months", "over 4 years", "a 15 year mortgage", "make it 4 years",
  "pay it off in 2 years" (and, for savings, "save for 20 years").
- A rate with its words: "at 6%", "the rate is 6%", "6% apr", "6% interest"; or a line
  that is only a percent beside question words ("7%", "what about 6.5%?").

Every word of the line must belong to one of those phrases or be filler ("what if",
"hmm", "and", "instead", "i only do"). Any other word left over means the line is about
something else, and the model answers it as before. Three reviews (2026-10-25) found
the wider readers this replaced turning other shapes into server numbers the reply
then called the answer: a model year as a price ("what about a 2019 model?"), a card
payment as an APR ("what if my payment is 3%"), "it's 40k miles" as a $40,000 loan.
Prices, down payments, card payments, deposits and kinds go to the model.
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
# "The rate is 6% for 10 years", "it's 5% for 7 years", "0% for 18 months": a rate for a
# while, not a loan's rate and term. "At 6% for 5 years" states the loan.
_RATE_FOR_A_WHILE = re.compile(
    r"(?<!\bat\s)(?<![\w.])\d{1,3}(?:\.\d{1,4})?\s?(?:%|percent)\s(?:\w+\s)?for\s\d", re.I
)
# A line about a person ("what if I'm 30 years", "I was 25") changes no loan.
_ABOUT_A_PERSON = re.compile(
    r"\b(?:i|we|he|she|they|you)(?:'m|'re|\s(?:am|are|was|were))\b|\b(?:im|age|aged)\b"
)
_TERM_PHRASES = [
    (rf"\bpay(?:ing)?\s(?:it\s)?off\s(?:in|within|over)\s{_TIME}", False),
    (rf"\b(?:keep\s)?(?:sav(?:e|ing)|invest(?:ing)?)\sfor\s{_TIME}", True),
    (rf"\b(?:make\sit\s)?(?:(?:over|for|on|to|a|an|the|with|at)\s){{0,2}}{_TIME}"
     r"(?:\s(?:term|loan|mortgage|plan))?", False),
]  # fmt: skip
_RATE_PHRASES = [
    rf"\b(?:(?:the|my|an?|your)\s)?{_RATE_WORD}(?:\srate)?\s(?:(?:is|are|was|were|be|of|at|to)\s)+"
    rf"{_PCT}",
    rf"\bat\s{_PCT}",
    rf"\b{_PCT}\s(?:apr|apy|rate|interest(?:\srate)?|fixed)\b",
]
_OLD_VALUE = re.compile(
    r"\b(?:instead\sof|rather\sthan)\s(?:the\s)?\d[\d,.]*"
    r"(?:\s?(?:%|percent|years?|yrs?|months?|mos?))?",
    re.I,
)
_TERMS = [(re.compile(pattern, re.I), saving) for pattern, saving in _TERM_PHRASES]
_RATES = [re.compile(pattern, re.I) for pattern in _RATE_PHRASES]
_BARE_PCT = re.compile(_PCT, re.I)
# Words a change line may hold beside its phrases. "Payment", "monthly", "make" and "paid"
# are never filler: "what if my payment is 3%" is a card payment, not its APR.
_FILLER = frozenset(
    "what if about how would it it's its is was were be been and so ok okay hmm hmmm well "
    "oh but then instead rather please maybe i only just do did does doing go going with "
    "try say let's lets suppose same thing the a an that this what's whats hey um uh "
    "actually though also too again like my change switch went take took choose chose "
    "pick picked".split()
)
# Beside a bare percent, only question words: "what if I only do 3%" on a card is its
# payment, not its APR.
_BARE_FILLER = frozenset(
    "what if about how and or so ok okay hmm hmmm but then instead it it's its is was were "
    "be would what's whats same thing the please maybe well oh hey".split()
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
    """The new term and rate ``line`` states, or None when any word of it is no change."""
    text = " ".join(line.lower().replace("\u2019", "'").split())
    if not text or len(text) > _MAX_CHARS:
        return None
    if _RATE_FOR_A_WHILE.search(text) or _ABOUT_A_PERSON.search(text):
        return None
    change = Change()
    text = _OLD_VALUE.sub(" ", text)
    for pattern, saving in _TERMS:
        text = pattern.sub(partial(change.take_term, saving=saving), text)
    for pattern in _RATES:
        text = pattern.sub(change.take_rate, text)
    words = _WORDS.findall(text)
    if change.rate is None and change.term is None:
        bare = _BARE_PCT.search(text)
        rest = _WORDS.findall(_BARE_PCT.sub(" ", text, count=1))
        if bare is None or any(word not in _BARE_FILLER for word in rest):
            return None
        change.rate = float(bare["pct"])
        words = rest
    if change.clash or any(word not in _FILLER for word in words):
        return None
    return change

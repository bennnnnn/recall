"""One follow-up line read by a positive grammar: the change it states, or nothing.

A change line is read only when every word of it belongs to a change phrase this
grammar knows ("3 years", "at 6%", "5000 down", "put 20% down", "a 30k car", "the house is
400k", "borrow 8000", "pay 300 a month", "save 500 a month", "used") or is filler ("what
if", "hmm", "and", "instead", "i only"). Any other word left over ("miles", "tax",
"leave", "then go up", "from", "fee") means the line is about something else, and the
model answers it as before.

Two reviews of the follow-up reader (2026-10-25) found words it skipped over turning into
server numbers: "it's 40k miles" became a $40,000 loan, "I get a 5% match from my
employer" a 5% rate, "rates are 5% for 2 years then go up" a 2-year mortgage at $13,161
a month. Deny-words kept missing the next one; this reads only what it recognises.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial

from app.modules.money.currencies import named_currency
from app.modules.money.kinds import describes
from app.modules.money.read import DURATION, MONTHLY, PERCENT, SUM, sum_value

_MAX_CHARS = 200
_CURRENCY = (
    r"(?:\s?(?:dollars?|bucks|usd|euros?|eur|pounds?|gbp|birr|etb|rupees?|inr|naira|ngn|"
    r"shillings?|kes|yen|jpy|cad|aud)\b)?"
)
# A sum is never the number of a percent or of a length of time ("9%", "3 years").
_MONEY = (
    rf"(?<![\w.,]){SUM}{_CURRENCY}"
    r"(?![\d.,]|\s?(?:%|percent\b|per\s?cent\b|pct\b)|\s?-?\s?(?:years?|yrs?|months?|mos?)\b)"
)
_PCT = rf"(?<![\w.]){PERCENT}"
_TIME = rf"(?<![\w.]){DURATION}"
_KIND = (
    r"(?:certified\s)?(?P<kind>brand[\s-]new|new|used|pre-?owned|pre\sowned|"
    r"second[\s-]?hand)"
)
_THING = r"(?:car|house|home|condo|truck|suv|vehicle|one|model)"
_LOAN = r"(?:(?:car|auto|home|student|personal)\s)?(?:loan|mortgage)"
_BUY = r"(?:(?:buy|bought|buying|get|got|getting)\s(?:it\s)?)?(?:(?:a|an|the)\s)?"
# Words a change line may hold beside its phrases.
_FILLER = frozenset(
    "what if about how would it it's its it'd is was were be been and so ok okay hmm hmmm "
    "well oh but then instead rather please maybe i i'm im we we're only just do did does "
    "doing make go going with try say let's lets suppose same thing the a an that this "
    "what's whats hey um uh actually though also too again like much would've change "
    "switch my payment monthly went take took choose chose pick picked".split()
)


@dataclass
class Change:
    """What one line changes. Each role is filled at most once."""

    rate: float | None = None
    # A length of time and its unit ("3", "years"); ``saving_term`` when said of saving
    # ("save for 20 years"), which only a savings plan takes.
    term: tuple[float, str] | None = None
    saving_term: bool = False
    # Role -> sum: "price", "borrowed", "down", "bare", "monthly", "pay", "start", "balance".
    sums: dict[str, float] = field(default_factory=dict)
    # How a monthly sum was said: "pay" (a card), "save" (savings) or "" (either).
    monthly_verb: str = ""
    down_share: float | None = None
    kind: str | None = None
    currencies: set[str] = field(default_factory=set)
    clash: bool = False
    # The line as read: a kind word is checked against it ("I used 5000" names no kind).
    text: str = ""

    def take_sum(self, role: str, match: re.Match[str]) -> None:
        if role in self.sums:
            self.clash = True
        self.sums[role] = sum_value(match)
        currency = named_currency(match.group(0))
        if currency:
            self.currencies.add(currency)

    def take_kind(self, match: re.Match[str]) -> None:
        word = match.groupdict().get("kind")
        if not word:
            return
        if not describes(self.text, match.start("kind"), match.end("kind")):
            self.clash = True
        elif self.kind is not None and self.kind != word:
            self.clash = True
        self.kind = word


Take = Callable[[Change, re.Match[str]], None]


def _rate(change: Change, match: re.Match[str]) -> None:
    if change.rate is not None:
        change.clash = True
    change.rate = float(match["pct"])


def _term(change: Change, match: re.Match[str]) -> None:
    if change.term is not None:
        change.term = (0.0, "")
        change.clash = True
        return
    change.term = (float(match["n"]), match["unit"])


def _saving_term(change: Change, match: re.Match[str]) -> None:
    _term(change, match)
    change.saving_term = True


def _share(change: Change, match: re.Match[str]) -> None:
    if change.down_share is not None or "down" in change.sums:
        change.clash = True
    change.down_share = float(match["pct"])


def _role(role: str) -> Take:
    def take(change: Change, match: re.Match[str]) -> None:
        change.take_sum(role, match)
        change.take_kind(match)

    return take


def _monthly(verb: str) -> Take:
    def take(change: Change, match: re.Match[str]) -> None:
        change.take_sum("monthly", match)
        change.monthly_verb = verb

    return take


def _kind_only(change: Change, match: re.Match[str]) -> None:
    change.take_kind(match)


def _old_value(change: Change, match: re.Match[str]) -> None:
    """ "3 years instead of 5": the old value names nothing new."""


_NOT_FROM = r"(?!\sfrom\b)"
# A card's "pay 300" ends the line or its clause; "pay 1000 now" is a lump sum.
_CLAUSE_END = r"(?=\s*(?:$|[?.!,;]|instead\b|then\b))"
# Phrases in the order they are taken; each one's words are used up.
_PHRASES: list[tuple[str, Take]] = [
    (
        r"\b(?:instead\sof|rather\sthan)\s(?:the\s)?(?:[$€£¥₹₦]\s?)?\d[\d,.]*"
        r"(?:\s?(?:%|percent|k|grand|years?|yrs?|months?|mos?))?",
        _old_value,
    ),
    # A share of the price put down: "put 20% down", "a down payment of 15%".
    (rf"\b(?:put(?:ting)?\s(?:down\s)?)?(?:a\s)?{_PCT}\sdown(?:\s?payment)?\b{_NOT_FROM}", _share),
    (rf"\b(?:(?:the|my|a)\s)?down\s?payment\s(?:(?:of|is|was|were|to)\s)?{_PCT}", _share),
    (rf"\bput(?:ting)?\sdown\s{_PCT}", _share),
    # A sum put down: "5000 down", "put down 5000", "pay 5000 upfront".
    (
        rf"\b(?:(?:put|putting|pay|paying|have|had)\s(?:down\s)?)?{_MONEY}\s(?:(?:in\s)?cash\s)?"
        rf"down(?:\s?payment)?\b{_NOT_FROM}",
        _role("down"),
    ),
    (rf"\b(?:(?:the|my|a)\s)?down\s?payment\s(?:(?:of|is|was|were|to)\s)?{_MONEY}", _role("down")),
    (rf"\bput(?:ting)?\sdown\s{_MONEY}", _role("down")),
    (rf"\b(?:put|putting|pay|paying)\s{_MONEY}\s(?:(?:in\s)?cash\s)?up\s?front\b", _role("down")),
    (rf"{_MONEY}\sas\s(?:(?:a|the|my)\s)?down\s?payment\b", _role("down")),
    # A monthly sum: "pay 300 a month", "save 500 a month", "300 a month".
    (rf"\b(?:pay(?:s|ing)?|paid)\s{_MONEY}(?:{MONTHLY})", _monthly("pay")),
    (
        rf"\b(?:sav(?:e|ing)|deposit(?:ing)?|invest(?:ing)?|add(?:ing)?|contribut(?:e|ing)|"
        rf"put(?:ting)?\s(?:in|away))\s{_MONEY}(?:{MONTHLY})",
        _monthly("save"),
    ),
    (rf"{_MONEY}(?:{MONTHLY})", _monthly("")),
    (rf"\b(?:the\s)?(?:monthly\s)?payment\s(?:is|was|of)\s{_MONEY}", _monthly("pay")),
    # A card: "pay 300" (its monthly payment), "owe 8000", "the balance was 8000".
    (rf"\b(?:pay(?:s|ing)?|paid)\s{_MONEY}{_CLAUSE_END}", _role("pay")),
    (rf"\b(?:owe[ds]?|owing)\s{_MONEY}", _role("balance")),
    (rf"\b(?:(?:the|my)\s)?balance\s(?:is|was|were|of)\s{_MONEY}", _role("balance")),
    # Savings already there: "start with 5000", "already have 5000".
    (
        rf"\b(?:start(?:ing)?\s(?:off\s)?with|already\shave|have|had)\s{_MONEY}"
        r"(?:\s(?:saved|already|in\ssavings))?",
        _role("start"),
    ),
    # The sum borrowed: "borrow 8000", "a 25000 car loan", "the loan is 250k".
    (rf"\b(?:borrow(?:ed|ing)?|financ(?:e|ed|ing)|need)\s{_MONEY}", _role("borrowed")),
    (
        rf"\b(?:(?:the|my)\s)?(?:loan|mortgage)(?:\samount)?\s(?:is|was|were|of)\s{_MONEY}",
        _role("borrowed"),
    ),
    (rf"\b(?:(?:get|take|got|took|need)\s)?(?:(?:a|an)\s)?{_MONEY}\s{_LOAN}\b", _role("borrowed")),
    # The price by what it buys: "a 30k car", "the house is 400k", "a new one for 30000".
    (
        rf"\b{_BUY}(?:{_KIND}\s)?{_THING}\s(?:is|was|were|costs?|for|at|priced\sat|listed\sat)"
        rf"\s{_MONEY}",
        _role("price"),
    ),
    (rf"\b{_BUY}{_KIND}\s(?:for|at)\s{_MONEY}", _role("price")),
    (rf"\b{_BUY}{_MONEY}\s(?:{_KIND}\s)?{_THING}\b", _role("price")),
    (rf"\b(?:(?:the|its)\s)?price\s(?:is|was|were|of)\s{_MONEY}", _role("price")),
    # A term: "3 years", "over 48 months", "a 15 year mortgage", "pay it off in 2 years".
    (rf"\bpay(?:ing)?\s(?:it\s)?off\s(?:in|within|over)\s{_TIME}", _term),
    (rf"\b(?:keep\s)?(?:sav(?:e|ing)|invest(?:ing)?)\sfor\s{_TIME}", _saving_term),
    (
        rf"\b(?:(?:over|for|on|to|a|an|the|with|at)\s){{0,2}}{_TIME}"
        r"(?:\s(?:term|loan|mortgage|plan))?",
        _term,
    ),
    # A rate by its words: "at 6%", "the rate is 6%", "6% apr", or a bare "6%".
    (
        rf"\b(?:(?:at|of|to|get|got|getting|is|are|was|were|be|the|my|an?|interest|rate|rates|"
        rf"apr|apy)\s){{0,4}}{_PCT}(?:\s(?:apr|apy|rate|interest(?:\srate)?|fixed|financing))?",
        _rate,
    ),
    # The kind alone: "bought used", "a new one", "it's second hand".
    (rf"\b{_BUY}{_KIND}(?:\s(?:{_THING}|instead))?\b", _kind_only),
    # A sum on its own ("what about 400k?"): a loan's price, if the slider can reach it.
    (_MONEY, _role("bare")),
]
_COMPILED = [(re.compile(pattern, re.I), take) for pattern, take in _PHRASES]
# Leftover content: words, numbers, and the signs a sum or a percent would have used.
_WORDS = re.compile(r"[a-z0-9']+|[%$€£¥₹₦]")


def read_change(line: str) -> Change | None:
    """The change ``line`` states, or None when any word of it is no change phrase."""
    text = " ".join(line.lower().replace("\u2019", "'").split())
    if not text or len(text) > _MAX_CHARS:
        return None
    change = Change(text=text)
    for pattern, take in _COMPILED:
        text = pattern.sub(partial(_used, change, take), text)
    if change.clash or any(word not in _FILLER for word in _WORDS.findall(text)):
        return None
    if change.rate is None and change.term is None and not change.sums:
        if change.down_share is None and change.kind is None:
            return None
    return change


def _used(change: Change, take: Take, match: re.Match[str]) -> str:
    """Record the phrase and blank it out, keeping every other word where it was."""
    take(change, match)
    return " " * len(match.group(0))

"""The term a money request gives: "for 5 years", "36 months", "48 monthly payments".

A term is read in the product's own unit (a car loan counts months). A length of time
that is no term is left out: an age, time gone by or a gap ("thirty years old", "ten years
ago", "five years apart", "been paying for three years"). Two terms ("15 or 30 years") give
none, and the model answers.

A count of payments is a term at the frequency they are paid (``periods``): "repay the loan
in 48 equal monthly payments" is 4 years, "8 equal quarterly payments" 2 (live 2026-11-14,
a grade 12 book: the 48 payments were left unread and a 5-year term assumed). Only in the
loan's own sentence, and only in one form: opened by "in", "with", "over", "by" or "for",
or as an item between commas ("car loan $30k, 72 monthly payments, 6.9% apr"). Any other
count there ("I'm three monthly payments behind", "I can afford 400 monthly payments",
"after 24 monthly payments") is no term: beside a term the user gives it changes nothing,
and with none it leaves the term unknown, so nothing is worked (2026-11-14 review: "three
monthly payments behind" was worked as a 3-month loan). A count no word says how often it
is paid ("60 payments") is unknown too.

A length in weeks or quarters is a term only after "for" or "over", as an item between
commas, or naming the loan ("a 26-week loan"): "for 26 weeks", "over 8 quarters". Any other
("in 3 weeks", "30 weeks pregnant", "a 2-week vacation", "200 quarters in a jar") is about
something else, and the term is read without it. A length in days is no term a product
works: said so, it works no numbers.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping

from app.modules.money.catalog import Product
from app.modules.money.periods import OTHER_DURATION, paid_by, payment_counts
from app.modules.money.phrases import TERM, count_value
from app.modules.money.schedule import sentence_kinds

# A count of payments or a length that is the loan's term: "repaid in 48 monthly payments",
# "with 60 monthly payments", "over 8 quarters", "for 26 weeks", "repay it in 90 days".
_OPENS_TERM = re.compile(r"\b(?:in|with|over|by|for)\s++$", re.I)
_LENGTH_OPENS = re.compile(r"\b(?:for|over)\s++$", re.I)
# Or the loan repaid in it: "repay a 2000 loan at 5% in 90 days", "pay it off within 26 weeks".
_IN = re.compile(r"\b(?:with)?in\s++$", re.I)
_REPAID = re.compile(
    r"\brepa(?:y|ys|id|ying|yable)\b|\bpa(?:y|ys|id|ying)\s++(?:\S++\s++){0,2}?(?:back|off)\b", re.I
)
# Or an item between commas: "car loan $30k, 72 monthly payments, 6.9% apr".
_ITEM_BEFORE = re.compile(r"(?:^|[,;:])\s*+$")
_ITEM_AFTER = re.compile(r"\s*+(?:$|[,;.!?])")
# A length naming the loan: "a 26-week loan", "a 90-day term".
_NAMES_LOAN = re.compile(r"[\s-]?(?:loan|term|mortgage|plan)\b", re.I)

_YEARS = {"year", "years", "yr", "yrs"}
# A length of time that is no term: an age, time gone by, a gap, payments already made
# ("ten years ago", "thirty years old", "five years apart", "been paying for three years",
# "twelve months of payments", "for the past 3 years", "every 3 months").
_SPAN_AFTER = re.compile(
    r"\s?(?:-\s?)?(?:ago|old|apart|of\sage|"
    r"of\s(?:payments?|paying|saving|savings|work|experience|service|marriage))\b",
    re.I,
)
# Another length offered beside a term: "15 or 30 years", "36 or 60 months", "15 vs 30 year".
_TERM_CHOICE = re.compile(
    r"(?<![\w.])\d{1,3}(?:\.\d+)?(?:[\s-]?(?:years?|yrs?|months?))?\s*(?:or|to|-|\u2013|/|vs\.?|versus)\s*$",
    re.I,
)
_SPAN_BEFORE = re.compile(
    r"\b(?:been\s(?:\w+\s){0,2}(?:for\s)?|(?:the|my|our)\s(?:past|last|previous)\s|made\s|"
    r"every\s|each\s|per\s|aged?\s)$",
    re.I,
)
# "for five years" in a clause about time already spent on a loan held ("I've been paying my
# mortgage at 4% for five years", "we have had our loan for 5 years") is time gone by, not
# the loan's term (2026-11-01: a 5-year mortgage worked from it). Only paying, owning or
# holding a loan counts, with the loan as the verb's object: "I've been looking at a car
# loan at 6% for 3 years", "I've had my eye on one", "I've paid $5k toward a down payment
# on a $300k mortgage at 6% for 15 years" and "we have had a mortgage offer of $300k … for
# 15 years" ask about a new loan's term.
_HELD = r"(?:mortgage|loan|card|balance|debt)s?"
# The held loan ends its noun phrase: a preposition, a conjunction, punctuation or a sum
# follows it. "a car loan quote at 7% for 6 years" and "a mortgage offer of $300k" are a new
# loan's quote and offer, never one held.
_HELD_ENDS = (
    r"\b(?=\s*(?:(?:at|for|of|with|on|since|from|in|and|but|so|or)\b|[,.;:!?)]|[$€£¥₹₦\d]|$))"
)
_SPENT_CLAUSE = re.compile(
    r"\b(?:been\s(?:paying|repaying|making\s(?:payments|repayments)|servicing|carrying)"
    r"|(?:have|has|'ve|\u2019ve|'s|\u2019s)\s(?:paid|repaid|owned|held|carried|had))"
    r"\s(?:(?:on|off|down)\s)?(?:it|(?:my|our|his|her|their|the|this|that|a|an)\s"
    rf"(?:\S+\s){{0,3}}?{_HELD}{_HELD_ENDS})\b.*\bfor\s$",
    re.I | re.S,
)
# Where a clause starts: a sentence's end (never a decimal point, "4.5%"), a comma before a
# space (never "250,000"), or a conjunction.
_CLAUSE_BREAK = re.compile(
    r"[.?!;](?=\s|$)|\n|,\s|\b(?:and|but|so|or|yet|then|because|while|although|though)\b",
    re.I,
)
# A count word right before a term the reader did not take in whole ("two thousand and
# twenty months"): the term is not read.
_SCALE_BEFORE = re.compile(r"\b(?:hundred|thousand)\s(?:and\s)?$", re.I)


def read_term(
    product: Product,
    text: str,
    paid: int | None,
    schedule: int = 12,
    names: tuple[str, ...] = (),
) -> dict[str, float] | None:
    """The term the message gives, in the product's own unit; {} for none, None for two
    ("15 or 30 years", "a 3 year or 5 year car loan") or for a length it cannot read and no
    other ("60 payments" that ``paid``, the message's frequency, does not say how often).

    A count of payments is paid as its own words say ("48 monthly payments"), else ``paid``
    times a year. One said by another frequency than the loan's ``schedule`` ("I can manage
    20 quarterly payments" on a loan read as monthly) is not this loan's count: no term.
    ``names`` are the words naming the request's product, which mark the loan's sentences."""
    terms: set[tuple[tuple[str, float], ...]] = set()
    loan, about = sentence_kinds(text, names)
    for match in TERM.finditer(text):
        before = text[max(0, match.start() - 30) : match.start()]
        if _SCALE_BEFORE.search(before):
            return None
        if _no_term(text, match):
            continue
        if _TERM_CHOICE.search(before):
            return None
        terms.add(tuple(term_in(product, count_value(match["n"]), match["unit"]).items()))
    unread = stray = False
    unframed: list[float] = []
    for match, count, own in payment_counts(text):
        sentence = _within(match.start(), loan)
        if sentence is None and _within(match.start(), about) is None:
            continue
        if (
            sentence is None
            or _no_term(text, match)
            or not _is_term(text, match, sentence, _OPENS_TERM)
        ):
            # Beside the loan, or in a sentence about payments ("It is repaid in 36 monthly
            # payments"), a count not said as the loan's term is none.
            stray = True
            continue
        per_year = own if own is not None else paid
        if own is not None and own != schedule:
            return None
        if per_year is None:
            # "for 3 years, 12 payments": the count must be the term's at the loan's schedule.
            unframed.append(count)
            continue
        if not paid_by(per_year):
            unread = True
            continue
        terms.add(tuple(_payments_term(product, count, per_year).items()))
    others: set[tuple[tuple[str, float], ...]] = set()
    for match in OTHER_DURATION.finditer(text):
        own_sentence = _within(match.start(), loan)
        sentence = own_sentence if own_sentence is not None else _within(match.start(), about)
        if sentence is None or _no_term(text, match):
            continue
        if not (
            _is_term(text, match, sentence, _LENGTH_OPENS) or _NAMES_LOAN.match(text, match.end())
        ):
            continue
        if own_sentence is None:
            stray = True
            continue
        if match["unit"].lower().startswith("d"):
            unread = True
            continue
        others.add(tuple(term_in(product, count_value(match["n"]), match["unit"]).items()))
    found = terms or others
    if len(found) > 1:
        return None
    if found:
        term = dict(found.pop())
        if any(count != _count_over(term, schedule) for count in unframed):
            return None
        return term
    return None if unread or stray or unframed else {}


def _count_over(term: Mapping[str, float], per_year: int) -> float:
    """The payments made over ``term`` at ``per_year`` a year."""
    if "years" in term:
        return term["years"] * per_year
    return term.get("months", 0.0) * per_year / 12


def _within(start: int, spans: list[tuple[int, int]]) -> int | None:
    """Where the sentence holding ``start`` begins, when it is one of ``spans``."""
    return next((begin for begin, end in spans if begin <= start < end), None)


def _is_term(text: str, match: re.Match[str], sentence: int, opens: re.Pattern[str]) -> bool:
    """The count or the length at ``match`` is said as the term: opened by ``opens``, or an
    item between commas."""
    before = text[sentence : match.start()]
    if opens.search(before[-30:]):
        return True
    if opens is _LENGTH_OPENS and _IN.search(before) and _REPAID.search(before):
        return True
    return bool(_ITEM_BEFORE.search(before) and _ITEM_AFTER.match(text, match.end()))


def whole_payments(
    product: Product, values: Mapping[str, float], settings: Mapping[str, float]
) -> bool:
    """A loan paid other than monthly runs over a whole number of its payments: 30 months
    paid yearly is 2.5 payments, which no loan makes, so it is not worked. A monthly loan
    keeps its term as said, as before."""
    payments = settings.get("payments", product.settings.get("payments", 12))
    if payments == 12:
        return True
    if "years" in values:
        count = values["years"] * payments
    elif "months" in values:
        count = values["months"] * payments / 12
    else:
        return True
    return math.isclose(count, round(count), abs_tol=1e-9)


def _no_term(text: str, match: re.Match[str]) -> bool:
    """The length at ``match`` is no term: an age, time gone by, a gap, payments made."""
    before = text[max(0, match.start() - 30) : match.start()]
    breaks = [end.end() for end in _CLAUSE_BREAK.finditer(text, 0, match.start())]
    clause = text[breaks[-1] if breaks else 0 : match.start()]
    return bool(
        _SPAN_AFTER.match(text, match.end())
        or _SPAN_BEFORE.search(before)
        or _SPENT_CLAUSE.search(clause[-200:])
    )


def _payments_term(product: Product, count: float, per_year: int) -> dict[str, float]:
    """``count`` payments made ``per_year`` times a year, as a term: 48 monthly is 4 years."""
    unit = {1: "years", 4: "quarters", 12: "months", 52: "weeks"}.get(per_year)
    if unit is None:
        return term_in(product, count * 12 / per_year, "months")
    return term_in(product, count, unit)


def term_in(product: Product, number: float, unit: str) -> dict[str, float]:
    """``number`` ``unit`` ("3 years", "8 quarters") in the product's own term unit (a car
    loan counts months)."""
    unit = unit.lower()
    if unit in _YEARS:
        years, months = number, number * 12
    elif unit.startswith("quarter"):
        years, months = number / 4, number * 3
    elif unit.startswith(("week", "wk")):
        years, months = number / 52, number * 12 / 52
    else:
        years, months = number / 12, number
    if product.input("years") is not None:
        return {"years": years}
    if product.input("months") is not None:
        return {"months": months}
    return {}

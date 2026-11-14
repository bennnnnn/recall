"""The term a money request gives: "for 5 years", "36 months", "48 monthly payments".

A term is read in the product's own unit (a car loan counts months). A length of time
that is no term is left out: an age, time gone by or a gap ("thirty years old", "ten years
ago", "five years apart", "been paying for three years"). Two terms ("15 or 30 years") give
none, and the model answers.

A count of payments is a term at the frequency they are paid (``periods``): "repay the loan
in 48 equal monthly payments" is 4 years, "8 equal quarterly payments" 2 (live 2026-11-14,
a grade 12 book: the 48 payments were left unread and a 5-year term assumed). A count no
word says how often it is paid ("60 payments"), or a length no product's term counts ("in
90 days"), is read as no term only when no other is given: the reply must never assume a
term beside a count the user stated. A length in quarters or weeks is a term when no year,
month or payment count is given ("over 8 quarters").
"""

from __future__ import annotations

import re

from app.modules.money.catalog import Product
from app.modules.money.periods import OTHER_DURATION, paid_by, payment_counts
from app.modules.money.phrases import TERM, count_value

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


def read_term(product: Product, text: str, paid: int | None) -> dict[str, float] | None:
    """The term the message gives, in the product's own unit; {} for none, None for two
    ("15 or 30 years", "a 3 year or 5 year car loan") or for a length it cannot read and no
    other ("60 payments" that ``paid``, the message's frequency, does not say how often).

    A count of payments is paid as its own words say ("48 monthly payments"), else ``paid``
    times a year."""
    terms: set[tuple[tuple[str, float], ...]] = set()
    for match in TERM.finditer(text):
        before = text[max(0, match.start() - 30) : match.start()]
        if _SCALE_BEFORE.search(before):
            return None
        if _no_term(text, match):
            continue
        if _TERM_CHOICE.search(before):
            return None
        terms.add(tuple(term_in(product, count_value(match["n"]), match["unit"]).items()))
    unread = False
    for match, count, own in payment_counts(text):
        per_year = own if own is not None else paid
        if _no_term(text, match):
            continue
        if per_year is None or not paid_by(per_year):
            unread = True
            continue
        terms.add(tuple(_payments_term(product, count, per_year).items()))
    others: set[tuple[tuple[str, float], ...]] = set()
    for match in OTHER_DURATION.finditer(text):
        if _no_term(text, match):
            continue
        if match["unit"].lower().startswith("d"):
            unread = True
            continue
        others.add(tuple(term_in(product, count_value(match["n"]), match["unit"]).items()))
    found = terms or others
    if len(found) > 1:
        return None
    if found:
        return dict(found.pop())
    return None if unread else {}


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

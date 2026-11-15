"""Whether what the reader found is one the product is worked at, or nothing is worked.

A review of the rate-period reader (2026-11-14) found readings each word rule allowed but
no product makes: a $300k mortgage over 0.0577 years from "in 3 weeks" (435,166.20 a
month), a car loan at 1.9% a month (22.8% a year, a promotional yearly rate said
casually), a loan "borrowed" from an uncle with no interest, and a 5-year term assumed for
"my payment is $100 a month. How long?". A first ask is held to what a follow-up already
was: the term on the product's slider and at least two payments, the rate one the product
is quoted at, the loan one lent at a rate.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from app.modules.money.catalog import PRODUCTS, Product, plausible_rates
from app.modules.money.periods import rate_spans
from app.modules.money.phrases import RATE, percent_value
from app.modules.money.schedule import names_payments, sentence_kinds
from app.modules.money.sums import Sum
from app.modules.money.terms import whole_payments

# A loan lent with no interest is no loan the catalog works: "interest-free", "no interest".
_INTEREST_FREE = re.compile(
    r"\binterest[\s-]free\b|\b(?:no|without|zero)\s+interest\b|\binterest\s+is\s+(?:zero|nil)\b",
    re.I,
)
# Borrowed from someone: only a lender lends at a rate the reader can work.
_FROM = re.compile(
    r"\bborrow\w*+\b[^.?!;]{0,60}?\bfrom\s++(?:(?:a|an|the|my|our|his|her|their|your)\s++)?"
    r"(?P<who>[a-z][\w'-]*+)",
    re.I,
)
_LENDERS = frozenset(
    "bank banks lender lenders credit microfinance building finance lending sacco".split()
)
# The fewest payments a loan or a deposit plan makes.
_FEWEST_PAYMENTS = 2
# A percent said "in" something is that thing's share, never the rate: "1% a month in
# fees", "3% in closing costs"; "6% in interest" and "6% in 5 years" stay the rate's.
_IN_SHARE = re.compile(r"\s++in\s++(?!interest\b|\d|a\s++year\b)[a-z]", re.I)


def naming_words(product: Product) -> tuple[str, ...]:
    """Every word that names ``product`` in a request, its plainer products' too ("loan"
    for a car loan): what marks the loan's own sentences."""
    return tuple(
        word
        for item in PRODUCTS
        if _plainer(item, product)
        for word in (*item.words, *item.asked_words)
    )


def own_names(product: Product, text: str) -> tuple[str, ...]:
    """The names of the request's own loan, in lower case: its product's words, its kinds'
    ("used") and a plainer product's ("the loan" after "a car loan"). None at all when
    another loan is named too ("a car loan … my mortgage payments are weekly"): payments
    said of a loan by name are then not certainly this one's."""
    lowered = text.lower()
    names = [word for item in PRODUCTS if _plainer(item, product) for word in item.words]
    names += [word for variant in product.variants for word in variant.words]
    for item in PRODUCTS:
        if item.family != product.family or _plainer(item, product):
            continue
        if any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in item.words):
            return ()
    return tuple(names)


def _plainer(item: Product, product: Product) -> bool:
    """``item`` is ``product`` or a plainer word for it: "loan" is inside "car loan"."""
    return item is product or any(
        re.search(rf"\b{re.escape(word)}\b", own) for word in item.words for own in product.words
    )


def said_by_period(product: Product, yearly: float) -> bool:
    """A rate said by a shorter period ("2% a month") that comes to ``yearly`` is one
    ``product`` is quoted at: never a mortgage, a car or a student loan's (2026-11-14: "a
    $25,000 car loan at 1.9% a month" is a promotional 1.9% said casually), and inside the
    yearly rates the product is plausibly charged ("a mortgage at 6% per month" is no 72%)."""
    if product.yearly_only:
        return False
    low, high = plausible_rates(product)
    return low <= yearly <= high


def term_fits(product: Product, term: Mapping[str, float], settings: Mapping[str, float]) -> bool:
    """The term the message gives lies on the product's term slider, holds at least two
    payments and a whole number of them ("in 3 weeks" read as a term made a mortgage of
    0.0577 years)."""
    payments = settings.get("payments", product.settings.get("payments", 12))
    for name, value in term.items():
        item = product.input(name)
        if item is None or not item.span.low <= value <= item.span.high:
            return False
        count = value * payments / (12 if name == "months" else 1)
        if count < _FEWEST_PAYMENTS:
            return False
    return whole_payments(product, term, settings)


def said_of_another(text: str, start: int, end: int, names: Sequence[str]) -> bool:
    """The percent at ``text[start:end]`` is another thing's, not the rate: said "in" a
    thing after it and its own period ("1% a month in fees"), or in a sentence about none
    of the loan's own things ("My salary is $60,000 a year at 3% raise; my car loan is
    $20,000": the loan, its payments, its rate or interest, "it")."""
    spans = rate_spans(text, start, end)
    after = max([end, *(stop for _, stop in spans)])
    if _IN_SHARE.match(text, after):
        return True
    loan, about = sentence_kinds(text, names, rates=False)
    return not any(begin <= start < stop for begin, stop in (*loan, *about))


def states_payment(sums: Sequence[Sum]) -> bool:
    """A sum the loan is paid by is stated: "my payment is $100 a month", "payments of
    $500". An income is none."""
    return any((item.monthly or item.payment) and not item.income for item in sums)


def lends(text: str) -> bool:
    """``text`` tells of a loan lent at a rate and repaid in payments, as "borrowed" names
    one: a rate above 0 and payments named, never interest-free, and from no one but a
    lender ("borrowed $50,000 from his uncle" is no loan the reader works)."""
    if not names_payments(text) or _INTEREST_FREE.search(text):
        return False
    if not any((percent_value(found["pct"]) or 0) > 0 for found in RATE.finditer(text)):
        return False
    return all(found["who"].lower() in _LENDERS for found in _FROM.finditer(text))

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
from app.modules.money.phrases import COUNT, RATE, percent_value
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
# The first payment timed: "the first one made today", "first payment due in 45 days", "the
# first due at the end of 2 years", "payments beginning now", "starting 6 months from now".
_FIRST = re.compile(
    r"\bfirst(?:\s++(?:monthly|annual|yearly|quarterly|weekly|equal|level))?"
    r"(?:\s++(?:(?:re)?payments?|instal+ments?|emis?|deposits?|one)\b"
    r"|(?=\s++(?:is|was|will|being|to|made|due|paid|payable|on|at|in|after)\b))"
    r"|\b(?:begin(?:s|ning)?|start(?:s|ing)?|commenc(?:e|es|ing))\s++"
    r"(?:(?:re)?pay(?:ments?|ing)\s++)?(?=(?:now|today|immediately|right|in|after|from|next|on"
    rf"|upon|when|once|at\s++the|{COUNT})\b)",
    re.I,
)
# The one timing worked: a period after the loan is made, by the payments' own period ("the
# first due one year from now", "at the end of the first month", "starting next month").
_ORDINARY = re.compile(
    r"\s*+(?:(?:is|was|will\s++be|being|to\s++be)\s++)?(?:(?:made|due|paid|payable)\s++)?"
    r"(?:at\s++the\s++end\s++of\s++the\s++first\s++(?P<a>[a-z-]+)"
    r"|(?:one|1|a)\s++(?P<b>[a-z-]+)\s++(?:from\s++now|after\b|later|hence)"
    r"|in\s++(?:one|1|a)\s++(?P<c>[a-z-]+)|at\s++the\s++end\s++of\s++(?P<d>[a-z-]+)\s++(?:one|1)\b"
    r"|next\s++(?P<e>[a-z-]+))\b",
    re.I,
)
_UNIT_TIMES = {"year": 1, "half-year": 2, "half": 2, "quarter": 4, "month": 12, "week": 52}
# Payments or deposits timed otherwise, or put off: "in advance", "at the beginning of each
# year", "after a 2 year deferment" ("tax-deferred" savings are none).
_TIMED = re.compile(
    r"\b(?:paid|payable|made|(?:re)?payments?|instal+ments?|deposits?|emis?)\s++in\s++advance\b"
    r"|\bat\s++the\s++(?:beginning|start)\s++of\s++(?:each|every)\b|\bannuity[\s-]due\b"
    r"|(?<!tax-)(?<!tax\s)\bdefer(?:s|red|ring|ral|ment)?\b",
    re.I,
)
# A loan's repaying put off, or its interest added on before it: "after graduation", "on
# signing", "interest accrues during my 4 years of school", "interest capitalized annually".
_DEFERRED = re.compile(
    r"\bforbearance\b|\bpayment\s++holiday\b|\bmoratorium\b|\binterest[\s-]only\b"
    r"|\bafter\s++(?:graduation|graduating|school|college)\b|\b(?:on|upon|at)\s++signing\b"
    r"|\baccru\w*+\s++(?:during|while|until|in\s++school)\b|\bcapitali[sz](?:e|es|ed|ing|ation)\b",
    re.I,
)
# Another sum put into the loan: "a $1,200 warranty rolled in", "fees added to the loan".
_ROLLED_IN = re.compile(
    r"\brolled\s++in(?:to)?\b|\badded\s++(?:on\s++)?to\s++the\s++(?:loan|balance|amount)\b"
    r"|\bfinanced\s++in(?:to)?\b|\bincluded\s++in\s++the\s++(?:loan|financing)\b",
    re.I,
)
# A grace period before repaying starts ("a 6-month grace period"); one of days or weeks is
# the window before a late fee ("a 2 week grace period" on a mortgage), no deferral.
_GRACE = re.compile(
    rf"(?:\b{COUNT}[\s-]?(?P<before>[a-z]+)\s++)?\bgrace\s++period\b"
    rf"(?:\s++of\s++{COUNT}[\s-]?(?P<after>[a-z]+))?",
    re.I,
)
# A part of the loan left to its end: no level loan the card works ("a $5,000 balloon", "a
# residual value", "$10,000 due at the end", "a guaranteed future value of $12,000").
_LEFT_TO_THE_END = re.compile(
    r"\bballoon\b|\bresidual\b|\bfinal\s++(?:(?:re)?payment|instal+ment)\b"
    r"|\blast\s++(?:re)?payment\s++of\b|\blump[\s-]?sum\b|\bfuture\s++value\b|\bbullet\b"
    r"|\b(?:due|owed|owing|payable|outstanding|remaining|left)\s++at\s++the\s++end"
    r"(?:\s++of\s++the\s++(?:loan|term|lease|contract|agreement)\b|(?!\s++of\b))",
    re.I,
)
# A word that names a loan by itself, not a thing bought with one ("car", "house").
_LOAN_NAME = re.compile(r"\b(?:loans?|mortgages?|payment)\b")
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


def names_another_loan(product: Product, text: str) -> bool:
    """Another loan than ``product`` is named by a loan's own words ("My car loan is $15,000
    at 5% and my student loan is $30,000", "a $25,000 car loan …; I also have a mortgage",
    "My savings account pays 0.5% per month. What's the payment on a $5,000 personal
    loan?"): the sums and the rate are then not certainly this one's (2026-11-14: a student
    loan of 15,000, savings worked for a loan's payment). A plainer word for it ("the loan")
    or a thing bought ("a car") is none."""
    lowered = text.lower()
    return any(
        item.family == "loan"
        and not _plainer(item, product)
        and not _plainer(product, item)
        and any(
            _LOAN_NAME.search(word) and re.search(rf"\b{re.escape(word)}\b", lowered)
            for word in item.words
        )
        for item in PRODUCTS
    )


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


def shaped_otherwise(product: Product, text: str, names: Sequence[str], per_year: int) -> bool:
    """The request's own sentences time its payments otherwise than one period after it
    starts, leave a part of a loan to its end or put another sum into it: none is the level
    loan or deposit plan the card works. 2026-11-14: "5 equal annual payments, the first
    one made today" was worked as 2,504.56 for 2,319.04, "a final balloon of $5,000" and "a
    $1,200 warranty rolled in" as an ordinary loan."""
    loan, about = sentence_kinds(text, names)
    is_loan = product.family == "loan"
    loan_only = (_DEFERRED, _LEFT_TO_THE_END, _ROLLED_IN) if is_loan else ()
    for begin, end in (*loan, *about):
        part = text[begin:end]
        if any(pattern.search(part) for pattern in (_TIMED, *loan_only)):
            return True
        if is_loan and any(_defers(found) for found in _GRACE.finditer(part)):
            return True
        if any(not _ordinary(part, found.end(), per_year) for found in _FIRST.finditer(part)):
            return True
    return False


def _ordinary(part: str, start: int, per_year: int) -> bool:
    found = _ORDINARY.match(part, start)
    if found is None:
        return False
    unit = next(word for word in found.groups() if word).lower().rstrip("s")
    return unit == "period" or _UNIT_TIMES.get(unit) == per_year


def _defers(grace: re.Match[str]) -> bool:
    unit = (grace["before"] or grace["after"] or "").lower()
    return not unit.startswith(("day", "week"))

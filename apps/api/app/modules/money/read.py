"""Read a money request from the user's words: which product, and the numbers they gave.

"what is my mortgage for 300k dollars house if mr rate is 1 percent" is a mortgage of
300 000 USD at 1 %, its term left to the product's default. The reader is word rules
only, no model call, and it reads nothing it cannot find: a missing number stays
missing for ``solve`` to fill from a default or today's average, or for the model to ask.

A product word alone is not a request ("I'm saving for a house", "credit card design"):
the message also needs a rate, an amount with a loan word, or a question about today's
rates. Yearly simple or compound interest ("compound interest on 1000 at 5% for 3
years") is maths homework and stays with maths.

The kind of the product is read by ``kinds`` ("buying a used car" is looked up at the
used-car average). The percent and the length of time are shared with ``change_line``,
which reads a follow-up ("what if i only do 3 years instead") by its own stricter grammar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.modules.money.catalog import PRODUCTS, Product
from app.modules.money.kinds import named_variant

# A percent and a length of time, as ``change_line`` reads them too.
PERCENT = r"(?P<pct>\d{1,3}(?:\.\d{1,4})?)\s?(?:%|percent\b|per\s?cent\b|pct\b)"
DURATION = r"(?P<n>\d{1,3}(?:\.\d{1,2})?)\s?-?\s?(?P<unit>years?|yrs?|months?|mos?)\b"
_RATE = re.compile(PERCENT, re.I)
_TERM = re.compile(rf"\b{DURATION}", re.I)
_AMOUNT = re.compile(
    r"(?P<sym>[$€£¥₹₦])?\s?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
    r"(?:\s?(?P<mult>k|m|thousand|million|mil|grand)\b)?",
    re.I,
)
_CURRENCY_WORD = re.compile(
    r"\s?(dollars?|bucks|usd|euros?|eur|pounds?|gbp|birr|etb|rupees?|inr|naira|ngn|"
    r"shillings?|kes|yen|jpy|cad|aud)\b",
    re.I,
)
_MONTHLY = re.compile(r"\s?(?:a|per|/|each|every)\s?(?:month|mo)\b|\s?monthly\b|\s?/\s?mo\b", re.I)
_DOWN = re.compile(r"\b(?:down\s?payment(?:\s(?:of|is))?|put(?:ting)?\s(?:down)?|down)\s?$", re.I)
_DOWN_AFTER = re.compile(r"\s?(?:down\b|as\s(?:a\s)?down\s?payment\b)", re.I)
# A bare number is money only after a word that says so ("borrow 25000", "balance is 4000");
# "rates in 2026" has no sum in it.
_MONEY_BEFORE = re.compile(
    r"\b(?:for|of|borrow(?:ing)?|owe|balance(?:\sis)?|loan|price(?:d)?|costs?|worth|save|"
    r"saving|deposit(?:ing)?|invest(?:ing)?|pay(?:ing)?|put|with|is)\s?$",
    re.I,
)
_START = re.compile(
    r"\b(?:start(?:ing)?\s(?:with|at)|have|initial(?:ly)?|already|lump\s?sum(?:\sof)?|"
    r"currently|right\snow)\s?$",
    re.I,
)
# Words that make a product word a money request ("car" alone is not; "car loan" at 6 % is).
_FINANCE = re.compile(
    r"\b(?:loan|loans|mortgage|payments?|pay|paying|apr|interest|rates?|finance|financing|"
    r"borrow(?:ing)?|owe|balance|monthly|deposit(?:ing)?|compounded|save\s\d)\b",
    re.I,
)
_RATES_QUESTION = re.compile(
    r"\b(?:current|today'?s|latest|average|typical|going)\b[^.?!\n]{0,40}\b(?:rates?|aprs?|apy)\b"
    r"|\b(?:rates?|aprs?|apy)\b[^.?!\n]{0,40}\b(?:now|today|currently|these\sdays|"
    r"this\s(?:week|month|year))\b",
    re.I,
)
# "a 250000 mortgage": a bare number right before what it buys is its price.
_PRODUCT_AFTER = re.compile(r"\s?(?:mortgage|house|home|condo|car|loan|balance)\b", re.I)
# Yearly simple or compound interest is a school exercise maths works (math.school).
_HOMEWORK_INTEREST = re.compile(
    r"\b(?:simple|compound)\s+interest\b|\bcompounded\s+(?:annually|yearly|every\s+year)\b",
    re.I,
)
_CURRENCIES = {
    "$": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "bucks": "USD",
    "usd": "USD",
    "€": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "pound": "GBP",
    "pounds": "GBP",
    "gbp": "GBP",
    "birr": "ETB",
    "etb": "ETB",
    "₹": "INR",
    "rupee": "INR",
    "rupees": "INR",
    "inr": "INR",
    "₦": "NGN",
    "naira": "NGN",
    "ngn": "NGN",
    "shilling": "KES",
    "shillings": "KES",
    "kes": "KES",
    "¥": "JPY",
    "yen": "JPY",
    "jpy": "JPY",
    "cad": "CAD",
    "aud": "AUD",
}
_MULTIPLIERS = {"k": 1e3, "thousand": 1e3, "grand": 1e3, "m": 1e6, "million": 1e6, "mil": 1e6}
_TERM_UNITS = {"year": "years", "years": "years", "yr": "years", "yrs": "years"}


@dataclass(frozen=True)
class MoneyRequest:
    """What the user asked: a product, the inputs they gave, and their currency."""

    product: Product
    values: dict[str, float] = field(default_factory=dict)
    # ISO code from a symbol or word in the message; "" when it names none.
    currency: str = ""
    # "What are mortgage rates now?": today's average is the answer, with no numbers to work.
    rates_only: bool = False
    # The kind of the product named (a catalog ``Variant`` key: "used"); "" for none.
    variant: str = ""
    # What a follow-up changed ("months", "rate"); empty for a first ask.
    changed: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Amount:
    value: float
    monthly: bool
    down: bool
    start: bool


def read_money_request(text: str) -> MoneyRequest | None:
    """The money request in ``text``, or None when it is not one."""
    if not text or len(text) > 600:
        return None
    found = named_product(text)
    if found is None or _HOMEWORK_INTEREST.search(text):
        return None
    rate = _rate(text)
    amounts = _amounts(text)
    currency = _currency(text)
    variant = named_variant(found, text)
    if rate is None and not amounts:
        if _RATES_QUESTION.search(text):
            return MoneyRequest(found, {}, currency, rates_only=True, variant=variant)
        return None
    if rate is None and not _FINANCE.search(text):
        return None
    values = _values(found, rate, amounts)
    values.update(_term(found, text))
    if not any(name in values for name in _principal_names(found)):
        return None
    return MoneyRequest(found, values, currency, variant=variant)


def named_product(text: str) -> Product | None:
    """The first product, most specific words first, that the message names."""
    lowered = text.lower()
    best: tuple[int, Product] | None = None
    for item in PRODUCTS:
        for word in item.words:
            match = re.search(rf"\b{re.escape(word)}\b", lowered)
            if match is None:
                continue
            # A longer phrase ("car loan") beats a word inside it ("loan").
            if best is None or len(word) > best[0]:
                best = (len(word), item)
    return best[1] if best is not None else None


def _rate(text: str) -> float | None:
    match = _RATE.search(text)
    return float(match.group(1)) if match is not None else None


def _amounts(text: str) -> list[_Amount]:
    """Every sum of money in the message, in order, with what its neighbours say it is."""
    found: list[_Amount] = []
    for match in _AMOUNT.finditer(text):
        after = text[match.end() : match.end() + 24]
        if _RATE.match(text, match.start("num")) or _TERM.match(text, match.start("num")):
            continue
        word = _CURRENCY_WORD.match(after)
        marked = bool(
            match.group("sym")
            or match.group("mult")
            or word
            or "," in match["num"]
            or _PRODUCT_AFTER.match(after)
        )
        at = match.start("sym") if match.group("sym") else match.start("num")
        before = text[max(0, at - 24) : at]
        if not marked and _MONEY_BEFORE.search(before) is None:
            continue
        number = float(match["num"].replace(",", ""))
        if match.group("mult"):
            number *= _MULTIPLIERS[match["mult"].lower()]
        rest = after[word.end() :] if word else after
        found.append(
            _Amount(
                value=number,
                monthly=_MONTHLY.match(rest) is not None,
                down=_DOWN.search(before) is not None or _DOWN_AFTER.match(rest) is not None,
                start=_START.search(before) is not None,
            )
        )
    return found


def _currency(text: str) -> str:
    symbol = re.search(r"[$€£¥₹₦]", text)
    if symbol is not None:
        return _CURRENCIES[symbol.group(0)]
    for match in _CURRENCY_WORD.finditer(text):
        return _CURRENCIES.get(match.group(1).lower(), "")
    return ""


def _principal_names(product: Product) -> tuple[str, ...]:
    """The inputs that size the problem: without one there is nothing to work."""
    return {"loan": ("amount",), "card_payoff": ("balance",), "savings": ("start", "deposit")}[
        product.family
    ]


def _values(product: Product, rate: float | None, amounts: list[_Amount]) -> dict[str, float]:
    values: dict[str, float] = {}
    if rate is not None:
        values["apr" if product.family == "card_payoff" else "rate"] = rate
    once = [item for item in amounts if not item.monthly]
    monthly = [item for item in amounts if item.monthly]
    if product.family == "loan":
        price = next((item.value for item in once if not item.down), None)
        down = next((item.value for item in once if item.down), 0.0)
        if price is not None and price > down:
            values["amount"] = price - down
    elif product.family == "card_payoff":
        if once:
            values["balance"] = once[0].value
        if monthly:
            values["payment"] = monthly[0].value
    else:
        start = next((item.value for item in once if item.start), None)
        if start is None and once:
            start = once[0].value
        if start is not None:
            values["start"] = start
        if monthly:
            values["deposit"] = monthly[0].value
    return values


def _term(product: Product, text: str) -> dict[str, float]:
    """The term the message gives, in the product's own unit (a car loan counts months)."""
    match = _TERM.search(text)
    return term_in(product, float(match["n"]), match["unit"]) if match is not None else {}


def term_in(product: Product, number: float, unit: str) -> dict[str, float]:
    """``number`` ``unit`` ("3 years") in the product's own term unit (a car loan counts months)."""
    in_years = _TERM_UNITS.get(unit.lower()) == "years"
    if product.input("years") is not None:
        return {"years": number if in_years else number / 12}
    if product.input("months") is not None:
        return {"months": number * 12 if in_years else number}
    return {}

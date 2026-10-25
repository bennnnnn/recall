"""Read a money request from the user's words: which product, and the numbers they gave.

"what is my mortgage for 300k dollars house if mr rate is 1 percent" is a mortgage of
300 000 USD at 1 %, its term left to the product's default. The reader is word rules
only, no model call, and it reads nothing it cannot find: a missing number stays
missing for ``solve`` to fill from a default or today's average, or for the model to ask.

A product word alone is not a request ("I'm saving for a house", "credit card design"):
the message also needs a rate, an amount with a loan word, or a question about today's
rates. Yearly simple or compound interest ("compound interest on 1000 at 5% for 3
years") is maths homework and stays with maths.

A kind of the product the catalog prices apart is read too: "a used car for 14000" is a
car loan looked up at the used-car average, where it once got the new-car one (live,
2026-10-25). The pieces (``stated_rate``, ``stated_term``, ``stated_amounts``) are also
how ``follow_up`` reads "what if i only do 3 years instead".
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from app.modules.money.catalog import PRODUCTS, Product
from app.modules.money.currencies import CURRENCY_WORD, named_currency

_RATE = re.compile(r"(\d{1,3}(?:\.\d{1,4})?)\s?(?:%|percent\b|per\s?cent\b|pct\b)", re.I)
_TERM = re.compile(r"\b(\d{1,3}(?:\.\d{1,2})?)\s?-?\s?(years?|yrs?|months?|mos?)\b", re.I)
# "Bought it 3 years ago", "20 years old", "sell after 5 years": when, not how long a loan runs.
_NOT_A_TERM_BEFORE = re.compile(r"\b(?:after|every|each|past|last|first)\s(?:the\s)?$", re.I)
_NOT_A_TERM_AFTER = re.compile(
    r"\s?(?:ago|old|older|younger|later|earlier|back|since|from\snow)\b", re.I
)
_AMOUNT = re.compile(
    r"(?P<sym>[$€£¥₹₦])?\s?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
    r"(?:\s?(?P<mult>k|m|thousand|million|mil|grand)\b)?",
    re.I,
)
_MONTHLY = re.compile(r"\s?(?:a|per|/|each|every)\s?(?:month|mo)\b|\s?monthly\b|\s?/\s?mo\b", re.I)
_DOWN = re.compile(r"\b(?:down\s?payment(?:\s(?:of|is))?|put(?:ting)?\s(?:down)?|down)\s?$", re.I)
_DOWN_AFTER = re.compile(r"\s?(?:down\b|as\s(?:a\s)?down\s?payment\b)", re.I)
# A bare number is money only after a word that says so ("borrow 25000", "balance is 4000");
# "rates in 2026" has no sum in it.
_MONEY_BEFORE = re.compile(
    r"\b(?:for|of|borrow(?:ed|ing)?|owe[ds]?|balance(?:\sis)?|loan|price(?:d)?|costs?|worth|save|"
    r"saving|deposit(?:ing)?|invest(?:ing)?|pay(?:ing)?|put|down|with|is)\s?$",
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
# A kind word that is a verb names no kind: "I used a calculator", "I'm used to paying 300",
# "the car I used to have", "what would I have used", "the rate used for car loans".
_VERB_BEFORE = re.compile(
    r"(?:\b(?:i|we|you|they|he|she|who|have|has|had|having|would|could|should|will|never|"
    r"just|already|also|once|ever|always|been|get|got)|'(?:ve|d|m|ll|re))\s$",
    re.I,
)
_VERB_AFTER = re.compile(
    r"\s(?:to|for|by|as|in|on|with|at|it|them|this|that|a|an|the|my|your|our|their)\b", re.I
)
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
    # A loan's down payment, already taken off the price in ``amount``.
    down: float = 0.0
    # The term today's average is looked up for, when not the request's own: a follow-up
    # that only shortens the term keeps the rate the last reply used (``follow_up``).
    rate_term: float | None = None
    # What a follow-up changed ("months", "down", "variant"); empty for a first ask.
    changed: tuple[str, ...] = ()


@dataclass(frozen=True)
class Amount:
    """A sum of money in the message, where it is, and what its neighbours say it is."""

    value: float
    monthly: bool
    down: bool
    start: bool
    # From its currency sign (or number) to the end of its multiplier ("$18k").
    span: tuple[int, int]


def read_money_request(text: str) -> MoneyRequest | None:
    """The money request in ``text``, or None when it is not one."""
    if not text or len(text) > 600:
        return None
    found = named_product(text)
    if found is None or _HOMEWORK_INTEREST.search(text):
        return None
    rate = stated_rate(text)
    amounts = stated_amounts(text)
    currency = named_currency(text)
    variant = named_variant(found, text)
    if rate is None and not amounts:
        if _RATES_QUESTION.search(text):
            return MoneyRequest(found, {}, currency, rates_only=True, variant=variant)
        return None
    if rate is None and not _FINANCE.search(text):
        return None
    values, down = _values(found, rate, amounts, stated_down_share(text))
    values.update(stated_term(found, text))
    if not any(name in values for name in _principal_names(found)):
        return None
    return MoneyRequest(found, values, currency, variant=variant, down=down)


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


def named_variant(product: Product, text: str) -> str:
    """The kind of ``product`` the message names ("a used car": "used"), or ""."""
    lowered = text.lower()
    for variant in product.variants:
        for word in variant.words:
            for match in re.finditer(rf"(?<![\w-]){re.escape(word)}(?!\w)", lowered):
                before = lowered[max(0, match.start() - 16) : match.start()]
                if _VERB_BEFORE.search(before) or _VERB_AFTER.match(lowered, match.end()):
                    continue
                return variant.key
    return ""


def stated_rate(text: str) -> float | None:
    """The yearly rate the message gives. "20% down" is a share of the price, not a rate."""
    return next(
        (float(match.group(1)) for match in _RATE.finditer(text) if not _down_share(text, match)),
        None,
    )


def stated_down_share(text: str) -> float | None:
    """The percent of the price put down ("with 20% down"), or None."""
    return next(
        (float(match.group(1)) for match in _RATE.finditer(text) if _down_share(text, match)),
        None,
    )


def _down_share(text: str, match: re.Match[str]) -> bool:
    before = text[max(0, match.start() - 24) : match.start()]
    return _DOWN.search(before) is not None or _DOWN_AFTER.match(text, match.end()) is not None


def stated_amounts(text: str) -> list[Amount]:
    """Every sum of money in the message, in order, with what its neighbours say it is."""
    found: list[Amount] = []
    for match in _AMOUNT.finditer(text):
        after = text[match.end() : match.end() + 24]
        if _RATE.match(text, match.start("num")) or _TERM.match(text, match.start("num")):
            continue
        word = CURRENCY_WORD.match(after)
        marked = bool(
            match.group("sym")
            or match.group("mult")
            or word
            or "," in match["num"]
            or _PRODUCT_AFTER.match(after)
            or _DOWN_AFTER.match(after)
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
            Amount(
                value=number,
                monthly=_MONTHLY.match(rest) is not None,
                down=_DOWN.search(before) is not None or _DOWN_AFTER.match(rest) is not None,
                start=_START.search(before) is not None,
                span=(at, match.end()),
            )
        )
    return found


def _principal_names(product: Product) -> tuple[str, ...]:
    """The inputs that size the problem: without one there is nothing to work."""
    return {"loan": ("amount",), "card_payoff": ("balance",), "savings": ("start", "deposit")}[
        product.family
    ]


def _values(
    product: Product, rate: float | None, amounts: list[Amount], share: float | None
) -> tuple[dict[str, float], float]:
    """The inputs the sums and the rate give, and a loan's down payment taken off its price."""
    values: dict[str, float] = {}
    taken = 0.0
    if rate is not None:
        values["apr" if product.family == "card_payoff" else "rate"] = rate
    once = [item for item in amounts if not item.monthly]
    monthly = [item for item in amounts if item.monthly]
    if product.family == "loan":
        price = next((item.value for item in once if not item.down), None)
        down = next((item.value for item in once if item.down), 0.0)
        if price is not None and not down and share:
            down = price * share / 100
        if price is not None and price > down:
            values["amount"] = price - down
            taken = down
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
    return values, taken


def stated_term(product: Product, text: str) -> dict[str, float]:
    """The term the message gives, in the product's own unit (a car loan counts months)."""
    match = next(term_matches(text), None)
    return term_value(product, match) if match is not None else {}


def term_matches(text: str) -> Iterator[re.Match[str]]:
    """Each length of time the message gives that could be a term; "3 years ago" is none."""
    for found in _TERM.finditer(text):
        before = text[max(0, found.start() - 16) : found.start()]
        if not _NOT_A_TERM_BEFORE.search(before) and not _NOT_A_TERM_AFTER.match(text, found.end()):
            yield found


def term_value(product: Product, match: re.Match[str]) -> dict[str, float]:
    """A ``term_matches`` match in the product's own term unit."""
    number = float(match.group(1))
    in_years = _TERM_UNITS.get(match.group(2).lower()) == "years"
    if product.input("years") is not None:
        return {"years": number if in_years else number / 12}
    if product.input("months") is not None:
        return {"months": number * 12 if in_years else number}
    return {}

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
from app.modules.money.compounding import UNKNOWN, compounding_per_year
from app.modules.money.kinds import named_variant
from app.modules.money.loan_sums import LoanSums, Sum, loan_sums, rest_is_borrowed
from app.services.number_text import NUMBER_WORDS, count_word_pattern

# A count in words, as a book writes a term: "seven", "twenty-five", "two and a half".
_TENS = "|".join(word for word, value in NUMBER_WORDS.items() if value >= 20)
_ONES = count_word_pattern(low=1, high=9)
_SPELLED = (
    rf"(?:(?:{_TENS})(?:[\s-](?:{_ONES}))?|{count_word_pattern(low=1, high=19)})"
    r"(?:\sand\sa\shalf)?"
)
# A percent and a length of time, as ``change_line`` and ``purchase`` read them too; the
# count of a length of time is ``count_value``'s.
PERCENT = r"(?P<pct>\d{1,3}(?:\.\d{1,4})?)\s?(?:%|percent\b|per\s?cent\b|pct\b)"
DURATION = (
    rf"(?P<n>\d{{1,3}}(?:\.\d{{1,2}})?|{_SPELLED})\s?-?\s?(?P<unit>years?|yrs?|months?|mos?)\b"
)
_RATE = re.compile(PERCENT, re.I)
_TERM = re.compile(rf"\b{DURATION}", re.I)
_AMOUNT = re.compile(
    r"(?P<sym>[$€£¥₹₦])?\s?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
    r"(?:\s?(?P<mult>k|m|thousand|million|mil|grand)\b)?",
    re.I,
)
# Currency words, as ``purchase`` reads a sum too.
CURRENCY_WORDS = (
    r"dollars?|bucks|usd|euros?|eur|pounds?|gbp|birr|etb|rupees?|inr|naira|ngn|"
    r"shillings?|kes|yen|jpy|cad|aud"
)
_CURRENCY_WORD = re.compile(rf"\s?({CURRENCY_WORDS})\b", re.I)
# A currency named before its sum, as many countries write it: "Birr 3,000", "USD 500".
_CURRENCY_BEFORE = re.compile(rf"\b(?:{CURRENCY_WORDS})\s?$", re.I)


def sum_phrase(name: str) -> str:
    """A sum as a phrase in a lower-cased line ("$20k", "3 grand"), read by ``read_sum``."""
    return (
        rf"(?P<{name}>[$€£¥₹₦]?\s?\d[\d,]*(?:\.\d{{1,2}})?"
        rf"(?:\s?(?:k|m|thousand|million|mil|grand))?(?:\s(?:{CURRENCY_WORDS}))?)"
    )


_MONTHLY = re.compile(r"\s?(?:a|per|/|each|every)\s?(?:month|mo)\b|\s?monthly\b|\s?/\s?mo\b", re.I)
_DOWN = re.compile(r"\b(?:down\s?payment(?:\s(?:of|is))?|put(?:ting)?\s(?:down)?|down)\s?$", re.I)
_DOWN_AFTER = re.compile(r"\s?(?:down\b|as\s(?:a\s)?down\s?payment\b)", re.I)
# A sum put toward the price in a clause after it: "50,000 which he will use as a deposit",
# "50k as the down payment". A loan's deposit is its down payment.
_DOWN_CLAUSE = re.compile(
    r"[^\d.;!?]{0,40}?\bas\s(?:a|an|the|his|her|their|my|our|your)\s(?:deposit|down\s?payment)\b",
    re.I,
)
_YEAR = re.compile(r"(?:19|20)\d{2}")
# A percent that is a share of the price put down: "20% down", "a down payment of 20%",
# "down payment 20%", "putting down 20%". Not a rate beside a sum down ("at 7% down
# payment of 5000", "100k down payment 6.25%"), "6% down payment 20%" (the 20% is the
# share), "rate is 6% down from 7%" or "at 6%".
_MONEY_NEXT = (
    r"\s?(?:[$€£¥₹₦]\s?\d|\d[\d,]*(?:\.\d+)?\s?(?:k|m|thousand|million|mil|grand)\b"
    r"|\d{1,3}(?:,\d{3})+|\d{4,})"
)
_PERCENT_NEXT = r"\s?\d{1,3}(?:\.\d+)?\s?(?:%|percent\b|per\s?cent\b|pct\b)"
_NOT_A_SHARE = r"(?!\s(?:from|to|by|on|of|is)\b)"
_SHARE_DOWN_AFTER = re.compile(
    rf"\s?down\s?payment\b{_NOT_A_SHARE}(?!{_MONEY_NEXT})(?!{_PERCENT_NEXT})"
    rf"|\s?(?:as\s(?:a\s)?down\s?payment|down(?!\s?payment))\b{_NOT_A_SHARE}(?!{_MONEY_NEXT})",
    re.I,
)
_SHARE_DOWN_BEFORE = re.compile(
    r"\bdown\s?payment(?:\s(?:of|is))?\s?$|\bput(?:ting)?\s(?:down\s)?$", re.I
)
# "100k down payment 6.25%": a sum is the down payment, so the percent is the rate.
_SUM_DOWN_BEFORE = re.compile(
    r"(?:[$€£¥₹₦]\s?)?\d[\d,.]*\s?(?:k|m|thousand|million|mil|grand)?\s"
    r"(?:as\s(?:a\s)?)?down\s?payment(?:\s(?:of|is))?\s?$",
    re.I,
)
_RATE_BEFORE = re.compile(r"\b(?:at|@)\s?$", re.I)
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
# What a sum is said to be: borrowed ("borrow 20k", "owe 250k", "a 200k loan"), or what the
# thing costs ("costs 250,000", "a 400k house").
_LOAN_BEFORE = re.compile(
    r"\b(?:borrow(?:s|ed|ing)?|owe[sd]?|owing|loan(?:\samount)?(?:\s(?:of|is))?|"
    r"financ(?:e|es|ed|ing))\s?$",
    re.I,
)
_LOAN_AFTER = re.compile(r"\s?(?:loan|mortgage)\b", re.I)
_PRICE_BEFORE = re.compile(
    r"\b(?:costs?|costing|priced\sat|price(?:\s(?:of|is|tag\sof))?|worth|sells?\sfor|"
    r"selling\sfor|valued\sat)\s?$",
    re.I,
)
_GOODS_AFTER = re.compile(r"\s?(?:house|home|condo|car|truck|suv|vehicle|apartment|flat)\b", re.I)
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
    # A loan for something bought with money down: its price and the down payment. A new
    # down payment is taken off this price, never off the loan ("follow_up").
    price: float | None = None
    down: float | None = None
    # A bare amount beside a price, read as the "down" payment or the "loan" (``purchase``).
    guessed: str = ""
    # How many rates the line gave: a down payment is worked after one only, so a line
    # read wrong ("20% down … 6%") never carries into a worked follow-up.
    rates_given: int = 0
    # Settings the request fixed (``Product.settings``): "compounded quarterly" is
    # ``per_year`` 4. One it left out takes the product's usual value.
    settings: dict[str, float] = field(default_factory=dict)


def count_value(text: str) -> float:
    """A duration's count, in digits or words: "3.5", "seven", "twenty-five", "two and a half"."""
    words = text.lower().replace("-", " ").split()
    if not words or words[0] not in NUMBER_WORDS:
        return float(text)
    half = words[-3:] == ["and", "a", "half"]
    return sum(NUMBER_WORDS[word] for word in words[: -3 if half else None]) + 0.5 * half


def bare_year(text: str) -> bool:
    """``text`` is a year written as a bare number ("2026"), not a sum."""
    return _YEAR.fullmatch(text.strip()) is not None


def read_money_request(text: str) -> MoneyRequest | None:
    """The money request in ``text``, or None when it is not one."""
    if not text or len(text) > 600:
        return None
    found = named_product(text)
    if found is None or _HOMEWORK_INTEREST.search(text) or measures_without_money(text):
        return None
    rate = _rate(text)
    share = _percent_down(text)
    amounts = _amounts(text)
    currency = _currency(text)
    variant = named_variant(found, text)
    if rate is None and not amounts:
        if _RATES_QUESTION.search(text):
            return MoneyRequest(found, {}, currency, rates_only=True, variant=variant)
        return None
    if rate is None and not _FINANCE.search(_RATE_OF_A_QUANTITY.sub(" ", text)):
        return None
    settings = _settings(found, text)
    if settings is None:
        return None
    loan = loan_sums(amounts, share, rest_is_borrowed(text)) if found.family == "loan" else None
    values = _values(found, rate, amounts, loan)
    values.update(_term(found, text))
    if not any(name in values for name in _principal_names(found)):
        return None
    return MoneyRequest(
        found,
        values,
        currency,
        variant=variant,
        price=loan.price if loan else None,
        down=loan.down if loan else None,
        rates_given=_rates_given(text),
        settings=settings,
    )


def _settings(product: Product, text: str) -> dict[str, float] | None:
    """The settings ``text`` fixes; None when it says one the product cannot work: savings
    "compounded continuously", or a loan compounded other than monthly."""
    per_year = compounding_per_year(text)
    if per_year is None:
        return {}
    if "per_year" in product.settings:
        return None if per_year == UNKNOWN else {"per_year": per_year}
    return {} if per_year == 12 else None


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
    """The first percent that is not a share down: "a 400k house with 20% down at 6%" is 6%."""
    for match in _RATE.finditer(text):
        if not _is_share_down(text, match):
            return float(match.group(1))
    return None


def _rates_given(text: str) -> int:
    return sum(1 for match in _RATE.finditer(text) if not _is_share_down(text, match))


def _percent_down(text: str) -> float | None:
    """The share of the price put down ("20% down", "a down payment of 20%"), or None."""
    for match in _RATE.finditer(text):
        if _is_share_down(text, match):
            share = float(match.group(1))
            return share if 0 < share < 100 else None
    return None


def _is_share_down(text: str, match: re.Match[str]) -> bool:
    before = text[max(0, match.start() - 24) : match.start()]
    if _RATE_BEFORE.search(before) or _SUM_DOWN_BEFORE.search(before):
        return False
    return bool(_SHARE_DOWN_AFTER.match(text, match.end()) or _SHARE_DOWN_BEFORE.search(before))


def _amounts(text: str) -> list[Sum]:
    """Every sum of money in the message, in order, with what its neighbours say it is."""
    found: list[Sum] = []
    for match in _AMOUNT.finditer(text):
        after = text[match.end() : match.end() + 24]
        if _RATE.match(text, match.start("num")) or _TERM.match(text, match.start("num")):
            continue
        word = _CURRENCY_WORD.match(after)
        at = match.start("sym") if match.group("sym") else match.start("num")
        lead = text[max(0, at - 40) : at]
        named = None if match.group("sym") else _CURRENCY_BEFORE.search(lead)
        before = (lead[: named.start()] if named else lead)[-24:]
        marked = bool(
            match.group("sym")
            or match.group("mult")
            or word
            or named
            or "," in match["num"]
            or _PRODUCT_AFTER.match(after)
        )
        if not marked and _MONEY_BEFORE.search(before) is None:
            continue
        if match.group("mult") and not _is_multiplier(text, match):
            # "6m/s2", "20 m/s": a measurement, never 6 million.
            continue
        number = float(match["num"].replace(",", ""))
        if match.group("mult"):
            number *= _MULTIPLIERS[match["mult"].lower()]
        rest = after[word.end() :] if word else after
        clause = text[match.end() + (word.end() if word else 0) : match.end() + 64]
        found.append(
            Sum(
                value=number,
                monthly=_MONTHLY.match(rest) is not None,
                down=_DOWN.search(before) is not None
                or _DOWN_AFTER.match(rest) is not None
                or _DOWN_CLAUSE.match(clause) is not None,
                start=_START.search(before) is not None,
                loan=_LOAN_BEFORE.search(before) is not None or _LOAN_AFTER.match(rest) is not None,
                price=_PRICE_BEFORE.search(before) is not None
                or _GOODS_AFTER.match(rest) is not None,
            )
        )
    return found


# What follows an "m" or "k" that makes it a unit: "6m/s2", "5 m²", "3 km".
_UNIT_AFTER_LETTER = re.compile(r"[/^²³\d]")
# A physical measurement: "1500 kg", "6 m/s2", "20 N". Units are case-sensitive.
# A bare "m" is metres only apart from its number: "1.2m" is a sum, "500 m" a distance.
_MEASUREMENT = re.compile(
    r"(?<![\w.])\d+(?:\.\d+)?(?:\s?(?:kg|mg|g|m/s(?:\^?2|²)?|km/h|kmh|mph|kN|N|kJ|J|kW|W|Pa|Hz|"
    r"cm|mm|km)|\s+m)(?![\w/])"
)
# Money named outright: a currency, a percent, or a word only money uses. "Rate" and
# "payment" are physics words too.
_SAYS_MONEY = re.compile(
    rf"[$€£¥₹₦%]|\b(?:{CURRENCY_WORDS}|percent|apr|loans?|mortgages?|borrow\w*|owe[sd]?|"
    r"balance|credit\s+card|deposit\w*|invest\w*)\b",
    re.I,
)
# "at the rate of 40 miles per hour", "a rate of 6 m/s2": a rate with no percent is no
# interest rate.
_RATE_OF_A_QUANTITY = re.compile(
    r"\brates?\s+of\s+\d[\d.,]*\s*(?!\d|%|per\s?cent|percent|pct)"
    r"|\b(?:constant|steady|uniform|same|average)\s+rates?\b",
    re.I,
)


def _is_multiplier(text: str, match: re.Match[str]) -> bool:
    """An "m" is millions written with the number ("$1.2 m", "a 1.2m house", "2 m birr"),
    not a unit: "6m/s2" and "500 m" are measurements. A "k" alone is never a unit."""
    if match["mult"].lower() != "m":
        return True
    if _UNIT_AFTER_LETTER.match(text, match.end("mult")):
        return False
    attached = match.start("mult") == match.end("num")
    return (
        attached
        or match.group("sym") is not None
        or _CURRENCY_WORD.match(text, match.end("mult")) is not None
        # "borrow 2 m for a house": a loan word, and no measurement beside it.
        or (
            _SAYS_MONEY.search(text) is not None
            and _MEASUREMENT.search(f"{text[: match.start()]} {text[match.end() :]}") is None
        )
    )


def measures_without_money(text: str) -> bool:
    """A physics or maths quantity ("a 1500 kg car at the rate of 6m/s2") and no money
    word, currency or percent: "car" and "rate" there are no car loan (2026-10-30)."""
    return _MEASUREMENT.search(text) is not None and _SAYS_MONEY.search(text) is None


def read_sum(text: str) -> tuple[float, str] | None:
    """The one sum ``text`` is, whole ("$20k", "20,000 dollars", "3 grand"), with the
    currency it names (""), or None. A bare number is a sum only from 1000 up: "20 at 6%"
    is no loan."""
    text = text.strip()
    word = re.search(rf"\s?\b(?:{CURRENCY_WORDS})$", text, re.I)
    match = _AMOUNT.fullmatch(text[: word.start()] if word else text)
    if match is None:
        return None
    number = float(match["num"].replace(",", ""))
    if match["mult"]:
        number *= _MULTIPLIERS[match["mult"].lower()]
    elif not (match["sym"] or word or "," in match["num"] or number >= 1000):
        return None
    return number, _currency(text)


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


def _values(
    product: Product, rate: float | None, amounts: list[Sum], loan: LoanSums | None
) -> dict[str, float]:
    values: dict[str, float] = {}
    if rate is not None:
        values["apr" if product.family == "card_payoff" else "rate"] = rate
    once = [item for item in amounts if not item.monthly]
    monthly = [item for item in amounts if item.monthly]
    if loan is not None:
        if loan.amount is not None:
            values["amount"] = loan.amount
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
    return term_in(product, count_value(match["n"]), match["unit"]) if match is not None else {}


def term_in(product: Product, number: float, unit: str) -> dict[str, float]:
    """``number`` ``unit`` ("3 years") in the product's own term unit (a car loan counts months)."""
    in_years = _TERM_UNITS.get(unit.lower()) == "years"
    if product.input("years") is not None:
        return {"years": number if in_years else number / 12}
    if product.input("months") is not None:
        return {"months": number * 12 if in_years else number}
    return {}

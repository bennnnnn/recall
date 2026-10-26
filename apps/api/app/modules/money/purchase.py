"""A loan told over two lines: what the user is buying, then its amount and rate.

Live (2026-10-25): "I am planing to buy a car", the reply asking new or used and the
budget, then "20k with 6 percent". Neither line is a request on its own (``read`` needs
the product, the amount and the rate in one line), so no card was built and the model's
own totals were off ($1,930 interest where 20k at 6% over 36 months is $1,904).

Both lines are read by a positive grammar: every word belongs to a known phrase, and any
other word means the line is not this, and the model answers it as before.

- The user's line before says they are buying what a loan product finances
  (``Product.goods``): "I am planning to buy a car", "we want to buy a used car", "buying
  a house for 400k", "House buying for 400k", "I'm getting a 30k truck next month". Not
  "I bought a car last week", "buy a house in minecraft" or "buying a car for my son".
- With no price there, this line is only an amount and a rate, and maybe a term: "20k
  with 6 percent", "$20,000 at 6% apr", "20k at 6% for 5 years". The amount is the loan's,
  as "car loan 20k at 6%" reads in one line.
- With a price there, a bare amount is not certain: "60k at 6 percent", after the reply
  asked for the down payment and the rate, may be either. Only an amount said to be down
  is read ("60k down at 6%", "with 60k down", "down payment of 60k at 6 percent"), and the
  loan is the price less it.

A down payment after a line with no price ("down payment 3k" after "20k with 6 percent")
stays with the model: whether the 20k was the price or the loan was never said.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache

from app.modules.money.catalog import PRODUCTS, Product
from app.modules.money.kinds import named_variant
from app.modules.money.read import (
    CURRENCY_WORDS,
    DURATION,
    PERCENT,
    MoneyRequest,
    read_sum,
    term_in,
)
from app.modules.money.solve import rate_name
from app.services.text_normalize import collapse_ws, straighten_apostrophes

_MAX_CHARS = 120


def _sum(name: str) -> str:
    """A sum as a phrase, its value read by ``read.read_sum``."""
    return (
        rf"(?P<{name}>[$€£¥₹₦]?\s?\d[\d,]*(?:\.\d{{1,2}})?"
        rf"(?:\s?(?:k|m|thousand|million|mil|grand))?(?:\s(?:{CURRENCY_WORDS}))?)"
    )


# --- The line before: what is being bought -------------------------------------------

_WHO = r"(?:i|we|i'm|im|we're|i\sam|we\sare|i'd|we'd|i'll|we'll)\s"
_INTENT = (
    r"(?:plan(?:ning|ing)?\s(?:to|on)|thinking\s(?:of|about)|looking\sto|going\sto|gonna|"
    r"about\sto|hoping\sto|want(?:ing)?\sto|wanna|would\slike\sto|like\sto|need\sto|"
    r"ready\sto|trying\sto)\s"
)
_VERB = r"(?:buy(?:ing)?|purchas(?:e|ing)|financ(?:e|ing)|get(?:ting)?)"
_ARTICLE = r"(?:(?:a|an|the|my|our)\s)?"
_PRICE_WORD = r"(?:for|at|worth|costing|priced\sat)"
_WHEN = r"(?:\s(?:soon|next\s(?:week|month|year)|this\s(?:week|month|year)))?"


@cache
def _purchase_lines(product_key: str) -> tuple[re.Pattern[str], ...]:
    item = next(row for row in PRODUCTS if row.key == product_key)
    used = "|".join(re.escape(word) for variant in item.variants for word in variant.words)
    kind = rf"(?:(?:(?:brand\s)?new|(?:certified\s)?(?:{used}))\s)?" if used else r"(?:new\s)?"
    good = "(?:" + "|".join(re.escape(word) for word in item.goods) + ")"
    price = rf"(?:\s{_PRICE_WORD}\s{_sum('price')})?{_WHEN}"
    return (
        re.compile(
            rf"(?:{_WHO})?(?:{_INTENT})?{_VERB}\s{_ARTICLE}(?:{_sum('price_before')}\s)?"
            rf"{kind}{good}{price}"
        ),
        # "House buying for 400k".
        re.compile(rf"{_ARTICLE}{kind}{good}\s(?:buying|purchase){price}"),
    )


@dataclass(frozen=True)
class _Purchase:
    product: Product
    # The price and its currency, when the line named one.
    price: tuple[float, str] | None


def _purchase(line: str) -> _Purchase | None:
    text = _normal(line)
    for item in PRODUCTS:
        if not item.goods:
            continue
        for pattern in _purchase_lines(item.key):
            match = pattern.fullmatch(text)
            if match is None:
                continue
            written = match.groupdict().get("price") or match.groupdict().get("price_before")
            price = read_sum(written) if written else None
            if written and price is None:
                return None
            return _Purchase(item, price)
    return None


# --- This line: the amount and the rate ----------------------------------------------

_RATE_WORDS = r"(?:\s(?:interest(?:\srate)?|apr|rate|fixed))?"
_TERM = rf"(?:\s(?:for|over)\s{DURATION})?"
_LOAN_LINE = re.compile(rf"{_sum('sum')}\s(?:with|at|@)\s{PERCENT}{_RATE_WORDS}{_TERM}")
_DOWN_RATE = rf"(?:,?\s(?:with|at|and)\s{PERCENT}{_RATE_WORDS})?{_TERM}"
_DOWN_LINES = (
    # "60k down at 6%", "with 60k down", "I can put 60k down".
    re.compile(
        rf"(?:with\s|(?:(?:i|we)\s(?:can|could|will)\s|i'll\s|we'll\s)?put(?:ting)?\s)?"
        rf"{_sum('sum')}\sdown(?:\s?payment)?{_DOWN_RATE}"
    ),
    # "Down payment of 60k at 6 percent".
    re.compile(rf"(?:(?:a|the|my)\s)?down\s?payment(?:\s(?:of|is))?\s{_sum('sum')}{_DOWN_RATE}"),
)


def purchase_request(line: str, before: Sequence[str]) -> MoneyRequest | None:
    """The loan ``line`` gives for what ``before`` says the user is buying, or None.

    ``before`` is the user's line before this one in the parts its turn read it in; it
    counts only as one part, a line about buying and nothing else.
    """
    if len(before) != 1 or len(line) > _MAX_CHARS:
        return None
    bought = _purchase(before[0])
    if bought is None:
        return None
    text = _normal(line)
    patterns = (_LOAN_LINE,) if bought.price is None else _DOWN_LINES
    match = next((found for pattern in patterns if (found := pattern.fullmatch(text))), None)
    said = read_sum(match["sum"]) if match is not None else None
    if match is None or said is None:
        return None
    amount, currency = said
    if bought.price is not None:
        price, priced_in = bought.price
        if (currency and priced_in and currency != priced_in) or not 0 < amount < price:
            return None
        amount, currency = price - amount, currency or priced_in
    product = bought.product
    values = {"amount": amount}
    if match["pct"] is not None:
        values[rate_name(product)] = float(match["pct"])
    if match["n"] is not None:
        values.update(term_in(product, float(match["n"]), match["unit"]))
    return MoneyRequest(product, values, currency, variant=named_variant(product, before[0]))


def _normal(line: str) -> str:
    return collapse_ws(straighten_apostrophes(line)).lower().strip(" .!?\u2026")

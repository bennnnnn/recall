"""A model's reading of the chat's money request, held to the chat's words and made a request.

The model says what the request is (``model_read``); every value it gives must stand in
the chat as it says: its quote is found in a user's line (or, for an amount the assistant
proposed, in a reply), and the quote holds that number ("40k" holds 40000, "The interest
is 6" holds 6). A value that fails, two values for one slot, a rate the product is never
charged, a share down that is no part of the price, or a term off the product's slider
leave no request: the reply's model answers as before. Nothing here calls a model.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.money.catalog import Product, plausible_rates, product
from app.modules.money.fits import term_fits
from app.modules.money.model_read import MoneyReading, StatedValue
from app.modules.money.phrases import AMOUNT, MULTIPLIERS, TERM, amount_value, count_value
from app.modules.money.read import MoneyRequest, named_currency

# What a reply may propose: the size of the request, never a rate or a term it assumed.
_PROPOSED = frozenset({"price", "amount", "balance", "start"})
# The values each family works from.
_USES = {
    "loan": frozenset({"price", "down", "down_percent", "amount", "rate", "years", "months"}),
    "card_payoff": frozenset({"balance", "apr", "rate", "payment"}),
    "savings": frozenset({"start", "deposit", "rate", "years", "months"}),
    "afford": frozenset({"income", "monthly_income", "debts", "price", "rate", "years", "months"}),
}
_MONTHLY = re.compile(r"\bmonth(?:ly)?\b|/\s?mo\b|\bpm\b")
_YEARLY = re.compile(r"\byear(?:ly)?\b|\bannual(?:ly)?\b|/\s?yr\b|\bp\.?a\b")
_A_SCALE = re.compile(r"\b(?:a|one)\s(thousand|million)\b", re.I)


@dataclass(frozen=True)
class Chat:
    """The lines a value may be quoted from: the user's (the last one included), and the
    reply a proposed amount may come from (the last one: an older reply's sum was another
    request's, "you borrow $32,000" for a car three turns before a mortgage)."""

    user_lines: Sequence[str]
    replies: Sequence[str]


def checked_request(reading: MoneyReading, chat: Chat) -> MoneyRequest | None:
    """The request ``reading`` describes, every value held to the chat; None when it is no
    request the server works, or a value does not stand."""
    if not reading.calculate or not reading.plain or reading.product == "none":
        return None
    found = product(reading.product)
    stated: dict[str, float] = {}
    proposed: list[str] = []
    for item in reading.values:
        if item.name not in _USES[found.family]:
            continue
        if item.said_by == "assistant" and item.name not in _PROPOSED:
            # A rate or a term a reply assumed is no value the user gave: the product's
            # default or today's average stands in, said as assumed.
            continue
        line = _quoted_in(item, chat)
        if line is None or not _holds(item.quote, item.value) or _other_period(item):
            return None
        if item.name in stated and not math.isclose(stated[item.name], item.value):
            return None  # two values for one slot: a comparison, never one of them
        stated[item.name] = item.value
        if item.said_by == "assistant":
            # A proposed price sizes the loan: the amount borrowed is the reply's too.
            proposed.append("amount" if item.name == "price" else item.name)
    if not stated:
        return None  # nothing the user said to work from: the reply's model answers
    return _request(found, stated, tuple(proposed), reading.used, chat)


def _quoted_in(item: StatedValue, chat: Chat) -> str | None:
    """The line the value's quote is in: a user's, or a reply's for a proposed amount."""
    quote = _plain(item.quote)
    if not quote:
        return None
    lines = chat.replies if item.said_by == "assistant" else chat.user_lines
    return next((line for line in lines if quote in _plain(line)), None)


def _other_period(item: StatedValue) -> bool:
    """An income said by the month read as a year's, or the other way round."""
    quote = item.quote.lower()
    if item.name == "income":
        return _MONTHLY.search(quote) is not None
    if item.name == "monthly_income":
        return _YEARLY.search(quote) is not None
    return False


def _plain(text: str) -> str:
    return " ".join(text.lower().split()).strip(" .,!?;:")


def _holds(quote: str, value: float) -> bool:
    """The quote states ``value``: a sum ("40k", "$1 million", "20,000"), a percent or a
    count ("6", "20 percent", "72 months", "five years")."""
    return any(math.isclose(value, number, rel_tol=1e-9) for number in _numbers(quote))


def _numbers(quote: str) -> set[float]:
    numbers: set[float] = set()
    for match in AMOUNT.finditer(quote):
        try:
            number = amount_value(match["num"])
        except ValueError:
            continue
        if match["mult"]:
            numbers.add(number * MULTIPLIERS[match["mult"].lower()])
        numbers.add(number)
    for match in TERM.finditer(quote):
        try:
            numbers.add(count_value(match["n"]))
        except (KeyError, ValueError):
            continue
    numbers.update(MULTIPLIERS[match[1].lower()] for match in _A_SCALE.finditer(quote))
    return numbers


def _request(
    found: Product,
    stated: dict[str, float],
    proposed: tuple[str, ...],
    used: bool,
    chat: Chat,
) -> MoneyRequest | None:
    """The request from the values that stood, as the word reader builds one."""
    values: dict[str, float] = {}
    price = down = None
    if found.family == "loan":
        sized = _loan_amount(stated)
        if sized is None:
            return _unsized(found, stated, used, chat)
        values["amount"], price, down = sized
    elif found.family == "card_payoff":
        for name in ("balance", "payment"):
            if name in stated:
                values[name] = stated[name]
        if "apr" in stated or "rate" in stated:
            values["apr"] = stated.get("apr", stated.get("rate", 0.0))
    elif found.family == "afford":
        income = _income(stated)
        # A home's price of 0 is no price ("0 debt" holds a 0 too).
        price = stated["price"] if stated.get("price", 0) > 0 else None
        if income is None:
            return _unsized(found, stated, used, chat, price)
        values["income"] = income
        if "debts" in stated:
            if stated["debts"] < 0:
                return None
            values["debts"] = stated["debts"]
    else:
        for name in ("start", "deposit"):
            if name in stated:
                values[name] = stated[name]
    if found.family != "card_payoff" and "rate" in stated:
        values["rate"] = stated["rate"]
    if not _rate_fits(found, values):
        return None
    found, term = _fitted(found, stated)
    if term is None:
        return None
    values.update(term)
    if not any(name in values for name in ("amount", "balance", "start", "deposit", "income")):
        return _unsized(found, stated, used, chat)
    return MoneyRequest(
        found,
        values,
        _currency(chat),
        variant=_variant(found, used, chat),
        price=price,
        down=down,
        rates_given=1 if "rate" in values or "apr" in values else 0,
        proposed=proposed,
    )


def _unsized(
    found: Product,
    stated: dict[str, float],
    used: bool,
    chat: Chat,
    price: float | None = None,
) -> MoneyRequest:
    """A request with nothing to size it yet: the block asks for what is missing (the
    amount, or for what an income affords the income), no card."""
    values: dict[str, float] = {name: stated[name] for name in ("rate", "apr") if name in stated}
    variant = _variant(found, used, chat)
    return MoneyRequest(found, values, _currency(chat), variant=variant, price=price)


def _income(stated: dict[str, float]) -> float | None:
    """The yearly gross income: said by the year, or a month's times 12."""
    if "income" in stated and "monthly_income" in stated:
        return None
    if "monthly_income" in stated:
        return stated["monthly_income"] * 12 if stated["monthly_income"] > 0 else None
    income = stated.get("income")
    return income if income is not None and income > 0 else None


def _loan_amount(stated: dict[str, float]) -> tuple[float, float | None, float | None] | None:
    """The sum borrowed, the price and the sum down: the loan named, else the price less
    the money put down (0% down is the whole price). A share down that is no part of the
    price works none."""
    if "amount" in stated:
        amount = stated["amount"]
        return (amount, None, None) if amount > 0 else None
    price = stated.get("price")
    if price is None or price <= 0:
        return None
    down = stated.get("down")
    if down is None and "down_percent" in stated:
        share = stated["down_percent"]
        if not 0 <= share < 100:
            return None
        down = round(price * share / 100, 2)
    if down is None:
        return price, None, None
    if not 0 <= down < price:
        return None
    return price - down, price, down


def _rate_fits(found: Product, values: dict[str, float]) -> bool:
    """A rate the product may be charged: 0 (a promotion) up to its plausible top."""
    rate = values.get("apr", values.get("rate"))
    return rate is None or 0 <= rate <= plausible_rates(found)[1]


def _fitted(found: Product, stated: dict[str, float]) -> tuple[Product, dict[str, float] | None]:
    """The product and the term in its unit, on its slider. A loan term off its own slider
    (a "mortgage" over 36 months) is the plain loan's, when that one runs it."""
    said: dict[str, float] = {name: stated[name] for name in ("years", "months") if name in stated}
    if len(said) > 1:
        return found, None
    if not said:
        return found, {}
    for candidate in (found, product("loan")) if found.family == "loan" else (found,):
        term = _in_unit(candidate, said)
        if term is not None and term_fits(candidate, term, {}):
            return candidate, term
    return found, None


def _in_unit(found: Product, said: dict[str, float]) -> dict[str, float] | None:
    """The term in the unit ``found``'s slider counts: "36 months" is 3 years."""
    ((name, value),) = said.items()
    unit = "months" if found.input("months") is not None else "years"
    if name == unit:
        return {unit: value}
    if unit == "months":
        return {"months": value * 12}
    years = value / 12
    return {"years": years} if float(years).is_integer() else None


def _currency(chat: Chat) -> str:
    """The currency the user's lines name, the latest first; "" when they name none."""
    for line in reversed(chat.user_lines):
        if code := named_currency(line):
            return code
    return ""


def _variant(found: Product, used: bool, chat: Chat) -> str:
    """The used-car kind, when the read says so and a user's line says it."""
    kind = found.variant("used") if used else None
    if kind is None:
        return ""
    lines = " ".join(chat.user_lines).lower()
    said = any(re.search(rf"\b{re.escape(word)}\b", lines) for word in kind.words)
    return kind.key if said else ""

"""A money reply's sums are the card's, or the server writes the reply.

Live (2026-10-26, free model): "House buying for 400k" then "60k at 6 percent". The card
and the note under the reply said 340,000 borrowed at $2,038.47 a month; the reply above
them worked 60,000 as the loan, $359.82 a month. A reply that contradicts its own card is
the worst a money turn can do.

So on a turn whose card the server built, every sum of money the reply states (a sum with
a currency sign, thousands separators, cents or a k/m) must be one of the server's own: an
input (the amount, the price, the down payment, a balance, a deposit) or a result, to the
cent, to the whole unit or in thousands ("$2,038.47", "$2,038", "$340k"), or a number the
user wrote ("I pay 1950 rent"). A reply with any
other sum is replaced by one the server writes from the worked request; the note and the
card still follow. No sum is ever rewritten by how near it is: a review (2026-10-26) found
that turned rent, budgets and totals with taxes into the loan's figures.
"""

from __future__ import annotations

import logging
import re

from app.modules.money.numbers import money_text, percent_text
from app.modules.money.read import MoneyRequest
from app.modules.money.solve import Worked, rate_name
from app.services.md_fence_scan import line_fences

logger = logging.getLogger(__name__)

_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "INR": "₹", "NGN": "₦"}
_KINDS = {
    "mortgage": "mortgage",
    "car": "car loan",
    "student": "student loan",
    "personal": "personal loan",
    "loan": "loan",
}
_SUM = re.compile(
    r"(?<![\d.,])(?P<sign>\\?[$€£¥₹₦])?\s?(?P<whole>\d{1,3}(?:(?:,|\{,\})\d{3})+|\d+)"
    r"(?:\.(?P<cents>\d{1,2})(?!\d))?(?:\s?(?P<scale>[km])\b)?(?!\s?(?:%|\\%|percent\b))",
    re.IGNORECASE,
)
_SCALES = {"k": 1_000, "m": 1_000_000}


def keep_to_the_card(text: str, request: MoneyRequest, worked: Worked, asked: str = "") -> str:
    """``text``, or the server's own reply when ``text`` states a sum the card does not."""
    if agrees_with_card(text, request, worked, asked):
        return text
    logger.info("money reply stated a sum its card does not; the server wrote it")
    return worked_reply(request, worked)


def agrees_with_card(text: str, request: MoneyRequest, worked: Worked, asked: str = "") -> bool:
    """Every sum ``text`` states is the card's, or one the user wrote in ``asked``."""
    figures = _server_sums(request, worked) + _user_sums(asked)
    owners = line_fences(text)
    for line, owner in zip(text.split("\n"), owners, strict=True):
        if owner is not None:
            continue
        for found in _SUM.finditer(line):
            value = _money(found)
            if value is not None and not any(_is(found, value, figure) for figure in figures):
                return False
    return True


def _money(found: re.Match[str]) -> float | None:
    """The sum a match states, or None when it is no sum of money (a bare "30" or "6")."""
    whole = found.group("whole")
    separated = "," in whole or "{,}" in whole
    if not (found.group("sign") or found.group("scale") or found.group("cents") or separated):
        return None
    number = float(whole.replace("{,}", "").replace(",", ""))
    if found.group("cents"):
        number += float("0." + found.group("cents"))
    return number * _SCALES.get((found.group("scale") or "").lower(), 1)


def _is(found: re.Match[str], value: float, figure: float) -> bool:
    """``value`` is ``figure`` as written: to the cent, to the whole unit or in thousands."""
    if found.group("cents"):
        return round(value, 2) == round(figure, 2)
    if found.group("scale"):
        unit = _SCALES[found.group("scale").lower()]
        return value == round(figure / unit, 1) * unit or value == round(figure)
    return value == round(figure)


def _user_sums(asked: str) -> list[float]:
    """The user's own numbers ("I pay 1950 rent"): a reply may repeat them."""
    sums = []
    for found in _SUM.finditer(asked or ""):
        number = float(found.group("whole").replace("{,}", "").replace(",", ""))
        if found.group("cents"):
            number += float("0." + found.group("cents"))
        sums.append(number * _SCALES.get((found.group("scale") or "").lower(), 1))
    return sums


def _server_sums(request: MoneyRequest, worked: Worked) -> list[float]:
    product = worked.product
    sums = [worked.values[item.name] for item in product.inputs if item.format == "money"]
    sums += [value for item in product.outputs if item.format == "money"
             if (value := worked.outputs.get(item.name)) is not None]  # fmt: skip
    sums += [value for value in (request.price, request.down) if value is not None]
    return sums


def worked_reply(request: MoneyRequest, worked: Worked) -> str:
    """The answer in the server's words, from the worked request."""
    symbol = _SYMBOLS.get(request.currency, "")

    def cash(value: float | None) -> str:
        return f"{symbol}{money_text(value or 0.0)}"

    values, outputs = worked.values, worked.outputs
    product = worked.product
    rate = percent_text(values[rate_name(product)])
    if product.family == "card_payoff":
        months = outputs.get("months")
        if months is None:
            return (
                f"Paying {cash(values['payment'])} a month on a {cash(values['balance'])} "
                f"balance at {rate} APR never clears it: the payment does not cover the interest."
            )
        return (
            f"Paying {cash(values['payment'])} a month on a {cash(values['balance'])} balance "
            f"at {rate} APR clears it in **{months:.0f} months**, with "
            f"{cash(outputs.get('interest'))} in interest."
        )
    if product.family == "savings":
        return (
            f"Saving {cash(values['deposit'])} a month from {cash(values['start'])} at {rate} "
            f"for {values['years']:g} years grows to **{cash(outputs.get('balance'))}**: "
            f"{cash(outputs.get('deposited'))} deposited and {cash(outputs.get('interest'))} "
            "in interest."
        )
    kind = " ".join(word for word in (request.variant, _KINDS.get(product.key, "loan")) if word)
    term_name = "years" if "years" in values else "months"
    lines = [
        f"For a {cash(values['amount'])} {kind} at {rate} over {values[term_name]:g} "
        f"{term_name}, the monthly payment is **{cash(outputs.get('payment'))}**. Total "
        f"interest is {cash(outputs.get('interest'))}, and the total paid is "
        f"{cash(outputs.get('total'))}."
    ]
    if term_name in worked.assumed:
        lines.append(f"No term was given, so it uses {values[term_name]:g} {term_name}.")
    if rate_name(product) in worked.assumed:
        lines.append("No rate was given, so it uses today's average.")
    return " ".join(lines)

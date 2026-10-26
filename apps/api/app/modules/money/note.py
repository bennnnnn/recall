"""The notes under a money reply: today's average beside the user's rate, and how a bare
amount beside a price was read.

The server writes it, so the average, its date and its source are exactly what the
checked lookup found (``rates.py``). A rate further than ``money_unrealistic_ratio``
from the average either way "is not realistic"; any other gets the average "for
reference"; a rate that is the average (the user gave none) says so. No average, no note.
An average standing in for the kind asked (the new-car one for a used car) says so, and
judges no rate unrealistic: a used-car rate far above the new-car average is ordinary.
"""

from __future__ import annotations

from app.modules.money.numbers import day_text, money_text, percent_text
from app.modules.money.rates import MarketRate
from app.modules.money.read import MoneyRequest
from app.modules.money.solve import Worked, rate_name


def reading_note(request: MoneyRequest) -> str | None:
    """How a bare amount beside a price was read, so a misread shows (``purchase``)."""
    amount, price = request.values.get("amount"), request.price
    if amount is None or price is None:
        return None
    if request.guessed == "down" and request.down is not None:
        down = money_text(request.down)
        return (
            f"**Read as:** {down} is the down payment on the {money_text(price)} price, so the "
            f"loan is {money_text(amount)}. If {down} is the loan, move the amount slider."
        )
    if request.guessed == "loan":
        return (
            f"**Read as:** {money_text(amount)} is the loan on the {money_text(price)} price. "
            "If it is the down payment, move the amount slider."
        )
    return None


def market_note(worked: Worked, average: MarketRate | None, ratio: float) -> str | None:
    if average is None:
        return None
    rate_input = rate_name(worked.product)
    rate = worked.values[rate_input]
    source = f"[{average.source_title}]({average.source_url})"
    when = day_text(average.as_of)
    level = percent_text(average.value)
    caveat = f" {average.caveat}" if average.caveat else ""
    if rate_input in worked.assumed:
        return (
            f"**Note:** this uses today's average {average.name} in {average.country}, "
            f"{level} as of {when} ({source}).{caveat}"
        )
    unrealistic = average.value <= 0 or not average.value / ratio <= rate <= average.value * ratio
    if unrealistic and not caveat:
        return (
            f"**Note:** {percent_text(rate)} is not a realistic {average.name}. As of {when}, "
            f"the average in {average.country} is {level} ({source})."
        )
    return (
        f"**Note:** for reference, the average {average.name} in {average.country} is "
        f"{level} as of {when} ({source}).{caveat}"
    )

"""The note under a money reply that compares the user's rate with today's average.

The server writes it, so the average, its date and its source are exactly what the
checked lookup found (``rates.py``). A rate further than ``money_unrealistic_ratio``
from the average either way "is not realistic"; any other gets the average "for
reference"; a rate that is the average (the user gave none) says so. No average, no note.
"""

from __future__ import annotations

from app.modules.money.numbers import day_text, percent_text
from app.modules.money.rates import MarketRate
from app.modules.money.solve import Worked, rate_name


def market_note(worked: Worked, average: MarketRate | None, ratio: float) -> str | None:
    if average is None:
        return None
    rate_input = rate_name(worked.product)
    rate = worked.values[rate_input]
    source = f"[{average.source_title}]({average.source_url})"
    when = day_text(average.as_of)
    level = percent_text(average.value)
    if rate_input in worked.assumed:
        return (
            f"**Note:** this uses today's average {average.name} in {average.country}, "
            f"{level} as of {when} ({source})."
        )
    if average.value <= 0 or not average.value / ratio <= rate <= average.value * ratio:
        return (
            f"**Note:** {percent_text(rate)} is not a realistic {average.name}. As of {when}, "
            f"the average in {average.country} is {level} ({source})."
        )
    return (
        f"**Note:** for reference, the average {average.name} in {average.country} is "
        f"{level} as of {when} ({source})."
    )

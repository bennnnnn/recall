"""The money block the model reads before the user's message: numbers to copy, never redo.

The model writes the answer's words; the app worked the numbers and adds the market note
and the calculator card under the reply, so the block tells it not to write either. A
follow-up ("what if i only do 3 years instead") gets the earlier request worked again with
its change, and is told those are the answer: the free model once redid the change from
the earlier reply's numbers and was off by dollars (live, 2026-10-25).
"""

from __future__ import annotations

from app.modules.money.catalog import Product
from app.modules.money.numbers import day_text, money_text, percent_text
from app.modules.money.rates import MarketRate
from app.modules.money.read import MoneyRequest
from app.modules.money.solve import Worked, rate_name

# Every money block opens with this: the turn's numbers are the app's.
MONEY_HEADER = "Money, worked by the app"
MONEY_REPLY_RULES = (
    "Answer in a few short lines: the main result first, then the other results, and say "
    "which values were assumed. Copy these numbers exactly; never recompute them. Under "
    "your reply the app adds a calculator card with sliders and, when it found one, a "
    "note with today's average rate: do not write your own calculator, scenario table, "
    "chart or market-rate note, and do not state any average or market rate yourself."
)
MONEY_FOLLOW_UP = (
    "This message changes the user's earlier request: {changes}. The inputs and results "
    "below already include the change and are this turn's answer; never work the change "
    "out yourself or carry numbers over from an earlier reply."
)
# The average stands in for the kind asked: "used car" for the new-car average.
MONEY_STAND_IN = (
    "Today's average {name} is not a {kind} rate: {caveat} Say so in the reply, and "
    "never call it a {kind} rate."
)
MONEY_RATE_MISSING = (
    "The user gave no interest rate and no current average was found. Ask one short "
    "question for the rate their lender or card quoted; do not guess one."
)
MONEY_RATES_FOUND = (
    "Answer with this rate, its date and its source link, in one or two lines; do not "
    "state any other rate as current."
)
MONEY_RATES_MISSING = (
    "No checked average was found for this. Give a current figure only from search "
    "results in this turn, with its date and source; otherwise say you could not find "
    "today's figure. Never estimate one."
)

_INPUT_WORDS = {
    "amount": "amount",
    "rate": "yearly rate",
    "apr": "APR",
    "years": "term in years",
    "months": "term in months",
    "balance": "balance",
    "payment": "monthly payment",
    "start": "starting amount",
    "deposit": "monthly deposit",
    "down": "down payment",
}
_OUTPUT_WORDS = {
    "payment": "monthly payment",
    "interest": "total interest",
    "total": "total paid",
    "months": "months to pay off",
    "balance": "final balance",
    "deposited": "total deposited",
}


def money_block(request: MoneyRequest, worked: Worked | None, average: MarketRate | None) -> str:
    product = request.product
    kind = " ".join(word for word in (request.variant, product.key.replace("_", " ")) if word)
    head = f"{MONEY_HEADER}: {kind}."
    if request.rates_only:
        return "\n".join((head, _rates_line(request, average)))
    if worked is None:
        return "\n".join((head, MONEY_RATE_MISSING))
    lines = [head]
    if request.changed:
        lines.append(MONEY_FOLLOW_UP.format(changes="; ".join(_changes(request, worked))))
    if request.currency:
        lines.append(f"Currency: {request.currency}.")
    lines.append("Inputs: " + "; ".join(_inputs(product, worked)) + ".")
    lines.append("Results: " + "; ".join(_outputs(product, worked)) + ".")
    stand_in = _stand_in(request, average)
    if stand_in and rate_name(product) in worked.assumed:
        lines.append(stand_in)
    lines.append(MONEY_REPLY_RULES)
    return "\n".join(lines)


def _changes(request: MoneyRequest, worked: Worked) -> list[str]:
    """What the follow-up changed, in the block's words ("term in months 36")."""
    product = request.product
    parts = []
    for name in request.changed:
        if name == "variant":
            parts.append(f"a {request.variant} {product.key.replace('_', ' ')}")
        elif name == "down":
            parts.append(f"{_INPUT_WORDS[name]} {money_text(request.down)}")
        elif name in worked.values:
            value = _value_text(name, worked.values[name], product)
            parts.append(f"{_INPUT_WORDS.get(name, name)} {value}")
    return parts


def _stand_in(request: MoneyRequest, average: MarketRate | None) -> str:
    if average is None or not average.caveat:
        return ""
    kind = " ".join((request.variant, request.product.key.replace("_", " ")))
    return MONEY_STAND_IN.format(name=average.name, kind=kind, caveat=average.caveat)


def _rates_line(request: MoneyRequest, average: MarketRate | None) -> str:
    if average is None:
        return MONEY_RATES_MISSING
    line = (
        f"Today's average {average.name} in {average.country}: {percent_text(average.value)} "
        f"as of {day_text(average.as_of)}, from {average.source_title} ({average.source_url}). "
        f"{MONEY_RATES_FOUND}"
    )
    stand_in = _stand_in(request, average)
    return f"{line} {stand_in}" if stand_in else line


def _value_text(name: str, value: float, product: Product) -> str:
    item = product.input(name)
    if item is not None and item.format == "percent":
        return percent_text(value)
    if item is not None and item.format in ("years", "months"):
        return f"{value:g}"
    return money_text(value)


def _inputs(product: Product, worked: Worked) -> list[str]:
    parts = []
    for item in product.inputs:
        value = _value_text(item.name, worked.values[item.name], product)
        text = f"{_INPUT_WORDS.get(item.name, item.name)} {value}"
        if item.name in worked.assumed:
            text += " (assumed: the user did not say)"
        parts.append(text)
    return parts


def _outputs(product: Product, worked: Worked) -> list[str]:
    parts = []
    for item in product.outputs:
        value = worked.outputs.get(item.name)
        words = _OUTPUT_WORDS.get(item.name, item.name)
        if value is None:
            parts.append(f"{words}: never, the payment does not cover the interest")
        elif item.format == "months":
            parts.append(f"{words} {value:.1f}")
        else:
            parts.append(f"{words} {money_text(value)}")
    return parts

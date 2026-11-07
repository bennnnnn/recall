"""A price changed by percents in turn: "costs 2400, 15% off, then 16% VAT on the sale price".

Each change is a discount (off, discount, markdown, reduction) or a charge (VAT, tax, tip,
service charge, markup) on the price the change before it left, so 2400 shillings with 15%
off and then 16% VAT is 2400 * 0.85 * 1.16 = 2366.40. Read as three numbers of a proportion
it was a checked 0.1. The changes are applied in turn only when the message says so ("then",
"after", "on the sale price"): a tax on the original price is another sum, and a message that
does not say which is left to the model. Money is kept in exact decimals, never floats.
"""

from __future__ import annotations

import re
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal

from app.modules.math.schemas import MathIntent
from app.modules.math.tools.block.canonical import finish_with_answer
from app.services.solving import VerifiedMathBlock
from app.services.workout import Workout, math_line, render_workout

_NUMBER = re.compile(r"(?<![\w.])\d{1,9}(?:,\d{3})*(?:\.\d+)?(?![\w.]*\d)")
_PERCENT = re.compile(r"(?P<rate>\d{1,3}(?:\.\d{1,2})?)\s*(?:%|\bper\s*cent\b|\bpercent\b)", re.I)
_DISCOUNT = re.compile(r"\b(?:off|discount(?:ed)?|markdown|reduction|reduced|cheaper)\b", re.I)
_CHARGE = re.compile(
    r"\b(?:vat|tax|gst|tip|gratuity|service\s+(?:charge|fee)|markup|marked\s+up|surcharge)\b",
    re.I,
)
# The second change is on what the first left: "then", "after the discount", "on the sale price".
_IN_TURN = re.compile(
    r"\bthen\b|\bafter(?:wards)?\b|\bon\s+top\b"
    r"|\b(?:on|of)\s+(?:the|that)\s+(?:sale|discounted|reduced|new|lower)\s+price\b",
    re.I,
)
# The question asks what is paid: "how much do I pay", "what's the final price", "total".
_ASKS_PAID = re.compile(
    r"\bhow\s+much\b[^.?!]{0,30}\b(?:pay|paid|cost|spend|owe)\b"
    r"|\b(?:final|total|new)\s+(?:price|cost|amount|bill)\b|\bwhat\s+do\s+i\s+pay\b",
    re.I,
)
_CURRENCY_WORD = re.compile(
    r"\s*(?P<word>shillings?|ksh|birr|dollars?|bucks|euros?|pounds?|rupees?|naira|rand|cedis?|"
    r"francs?|yen|pesos?)\b",
    re.I,
)
_SIGN_OF = {"dollar": "$", "buck": "$", "euro": "€", "pound": "£"}
_SIGN_BEFORE = re.compile(r"(?P<sign>[$€£])\s*$")
_CENT = Decimal("0.01")
_MAX_CHANGES = 4


# Where one change's clause ends: "15% off, and then 16% VAT on the sale price".
_CLAUSE_BREAK = re.compile(r"[,;.?!]|\b(?:and|then|after|plus)\b", re.I)
# "on the sale price" names the price a change is on, not a discount of its own.
_PRICE_NAMED = re.compile(r"\b(?:sale|discounted|reduced|new|lower)\s+price\b", re.I)


def _change_kind(text: str, rate: re.Match[str]) -> str | None:
    """ "-" for a discount, "+" for a charge: the one kind word in the rate's own clause."""
    breaks = [m for m in _CLAUSE_BREAK.finditer(text) if m.end() <= rate.start()]
    start = breaks[-1].end() if breaks else 0
    after = _CLAUSE_BREAK.search(text, rate.end())
    clause = _PRICE_NAMED.sub(" ", text[start : after.start() if after else len(text)])
    discount, charge = _DISCOUNT.search(clause), _CHARGE.search(clause)
    if (discount is None) == (charge is None):
        return None
    return "-" if discount else "+"


def extract_price_changes_intent(cleaned: str) -> MathIntent | None:
    """One price, two or more percent changes in turn, and a question about what is paid."""
    text = " ".join(cleaned.split())
    if len(text) > 400 or _ASKS_PAID.search(text) is None or _IN_TURN.search(text) is None:
        return None
    rates = list(_PERCENT.finditer(text))
    if not 2 <= len(rates) <= _MAX_CHANGES:
        return None
    spans = [rate.span("rate") for rate in rates]
    prices = [n for n in _NUMBER.finditer(text) if n.span() not in spans]
    if len(prices) != 1 or prices[0].start() > rates[0].start():
        return None  # the price comes first and is the only other number
    changes: list[str] = []
    for rate in rates:
        kind = _change_kind(text, rate)
        if kind is None or not 0 < Decimal(rate.group("rate")) <= 100:
            return None
        changes.append(f"{kind}{rate.group('rate')}")
    word = _CURRENCY_WORD.match(text, prices[0].end())
    sign = _SIGN_BEFORE.search(text, 0, prices[0].start())
    named = word.group("word").lower() if word else ""
    money = sign.group("sign") if sign else _SIGN_OF.get(named.rstrip("s"), named)
    return MathIntent(
        kind="arithmetic",
        school_op="price_changes",
        # The price, its money ("$", "shillings" or ""), then each change as "-15" or "+16".
        arithmetic_operands=[prices[0].group().replace(",", ""), money, *changes],
        operation="solve",
    )


def _amount(value: Decimal) -> str:
    """Cents when there are any ("2366.40"), else the whole amount ("2040")."""
    if value == value.to_integral_value():
        return f"{value.to_integral_value():f}"
    return f"{value.quantize(_CENT, rounding=ROUND_HALF_UP):f}"


def price_changes_block(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    operands = intent.arithmetic_operands or []
    if len(operands) < 4:
        return None
    price, money, changes = Decimal(operands[0]), operands[1], operands[2:]
    # The reading lost a written sign ("$80"); the request as typed still has it.
    written = re.search(rf"([$€£])\s*{re.escape(operands[0])}(?!\d)", intent._request_text or "")
    money = money or (written.group(1) if written else "")
    rows, given = [], [math_line(f"{_amount(price)}", "price")]
    value = price
    for change in changes:
        sign, rate = change[0], Decimal(change[1:])
        factor = 1 - rate / 100 if sign == "-" else 1 + rate / 100
        given.append(math_line(rf"{rate:f}\%", "discount" if sign == "-" else "added"))
        after = value * factor
        rows.append(
            math_line(rf"{_amount(value)} \times \left(1 {sign} {rate / 100:f}\right) "
                      rf"= {_amount(value)} \times {factor:f} = {_amount(after)}")
        )  # fmt: skip
        value = after
    unit = {"$": r"\$", "€": "€", "£": "£"}.get(money)
    shown = _amount(value)
    answer = f"{unit}{shown}" if unit else (rf"{shown}\ \text{{{money}}}" if money else shown)
    lines.append(f"Each change applied to the price before it: {shown}")
    worked = render_workout(
        Workout(
            given=tuple(given),
            find=(math_line(r"\text{amount paid}"),),
            substitution=tuple(rows),
        ),
        answer,
    )
    return replace(finish_with_answer(lines, answer), worked_reply=worked)

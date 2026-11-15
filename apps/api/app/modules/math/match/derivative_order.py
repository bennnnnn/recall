"""Which derivatives a question names, by order: the reading the extractor and the tool
check share.

"Find the 4th derivative of x^5" was a checked 5x⁴, "the fourth derivative" the same, and
"the nth derivative of e^(2x)" a checked 2e^(2x): the reader knew "second", "third" and
their digits, and read every other order as the first. "The 2ⁿᵈ derivative of eˣsin x" came
back as the first derivative too (2026-11-14); its raised suffix is the plain ordinal here
(``services/script_runs.py``). An ordinal, a Leibniz power (``d^2y/dx^2``) or Lagrange's
primes name an order; one no number gives ("the nth derivative", ``d^ny/dx^n``) is read as
``None``, and no reading answers it.
"""

from __future__ import annotations

import re

from app.modules.math.match.calculus import lagrange_prime_order

_ORDER_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}
# One ordinal: "2nd", "fourth", "nth", "n-th", "(n+1)th"; the letter's or the bracket's
# names no number.
_ORDINAL = (
    r"\b(?P<number>\d{1,3})(?:st|nd|rd|th)"
    rf"|\b(?P<word>{'|'.join(_ORDER_WORDS)})"
    r"|(?:\b[a-z]|\([^()]{1,20}\))-?th"
)
_ONE_ORDINAL = re.compile(_ORDINAL, re.IGNORECASE)
_ANY_ORDINAL = re.sub(r"\?P<\w+>", "", _ORDINAL)
# Ordinals before "derivative": "the 2nd derivative", "the fourth-order derivative", "the
# first and second derivatives".
_ORDINAL_DERIVATIVE = re.compile(
    rf"(?:{_ANY_ORDINAL})(?:(?:\s*,|,?\s+(?:and|or))\s+(?:{_ANY_ORDINAL}))*"
    r"(?:[-\s]+order)?\s+(?:partial\s+)?deriv[a-z]*",
    re.IGNORECASE,
)
# Leibniz's ``d^2y/dx^2``, ``d^2/dx^2``, ``d^(n)y/dx^(n)``: the power on the first d.
_LEIBNIZ_ORDER = re.compile(
    r"(?<![a-z])d\s*\^\s*[({]?\s*(?:(?P<digits>\d{1,2})|[a-z])\s*[)}]?\s*[a-z]?\s*/\s*d",
    re.IGNORECASE,
)


def derivative_orders(text: str) -> tuple[int | None, ...]:
    """Every order the text names, in its order; ``None`` for one no number gives, and
    nothing when it names none (a plain "derivative" is the first)."""
    orders: list[int | None] = []
    for listed in _ORDINAL_DERIVATIVE.finditer(text):
        for match in _ONE_ORDINAL.finditer(listed.group()):
            if match.group("number"):
                orders.append(int(match.group("number")))
            elif match.group("word"):
                orders.append(_ORDER_WORDS[match.group("word").lower()])
            else:
                orders.append(None)
    for match in _LEIBNIZ_ORDER.finditer(text):
        orders.append(int(match.group("digits")) if match.group("digits") else None)
    primes = lagrange_prime_order(text)
    if primes:
        orders.append(primes)
    return tuple(orders)


def asked_derivative_order(text: str) -> int | None:
    """The order a derivative question asks for: the highest it names, 1 when it names
    none, and ``None`` when one it names is no number."""
    orders = derivative_orders(text)
    if not orders:
        return 1
    if None in orders:
        return None
    return max(order for order in orders if order is not None)

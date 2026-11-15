"""A derivative as a message writes it: Leibniz's d^n y/dx^n, primes at a number, and the
point a value is asked at ("the gradient at x = 3", "f'(3)", "at (3, 4)").

One reading of the notation for every reader: the maths readers and the whole-question
gate kept a copy each. A value asked at a point is a number, so an answer with its
variable still in it (f'(x) = 2x - 1 for f'(3)) answers another question. "when" and
"where" also introduce the function a derivative is taken of ("dy/dx when y = 2x^3 -
5x"), whose formula is no point: that relation opens a formula, and its letter is the one
differentiated (2026-11-14).
"""

from __future__ import annotations

import re

from app.services.glyphs import fold_primes
from app.services.number_text import SIGNED_DECIMAL

_MAX_TEXT = 2000
# d/dx, dy/dx, d^2y/dx^2, d²y/dx², d^{2}y/dx^{2}: its order, the letter differentiated and
# the variable.
LEIBNIZ = re.compile(
    r"(?<![A-Za-z])d\s*(?:\^\s*\{?(?P<order>[2-4])\}?\s*|(?P<script>[²³⁴])\s*)?"
    r"(?:(?P<of>[a-zA-Z])\s*)?/\s*d\s*(?P<var>[a-zA-Z])(?:\s*\^\s*\{?[2-4]\}?|\s*[²³⁴])?"
    r"(?![A-Za-z])"
)
_SCRIPT_ORDERS = {"²": 2, "³": 3, "⁴": 4}
# f'(3), y''(0): a derivative written at a number.
PRIME_AT_NUMBER = re.compile(rf"(?<![A-Za-z])[a-zA-Z]'{{1,3}}\(\s*({SIGNED_DECIMAL})\s*\)")
_PRIMED = re.compile(r"(?<![A-Za-z])([a-zA-Z])'")
_AT = re.compile(
    r"\b(?:at|when|where)\s+(?:the\s+point\s+)?"
    r"(?:(?P<letter>[a-z])\s*=\s*-?(?P<number>\d+(?:\.\d+)?)|\(\s*-?\d)",
    re.IGNORECASE,
)
# A formula goes on after the number: "2x^3", "3 + x^2".
_FORMULA_ON = re.compile(r"[\w(^]|\.\d|\s*[-+*/^]")


def leibniz_order(match: re.Match[str]) -> int:
    """The order a ``LEIBNIZ`` match writes: 2 for d^2y/dx^2, 1 for dy/dx."""
    if match["order"]:
        return int(match["order"])
    return _SCRIPT_ORDERS.get(match["script"] or "", 1)


def higher_leibniz(text: str) -> re.Match[str] | None:
    """The first derivative of order two or more written in Leibniz's notation."""
    return next((m for m in LEIBNIZ.finditer(text) if leibniz_order(m) > 1), None)


def differentiated_letters(text: str) -> frozenset[str]:
    """The letters ``text`` writes a derivative of, lowercase: y for dy/dx or y'', f for
    f'(x); none for "the derivative of", d/dx."""
    text = fold_primes(text[:_MAX_TEXT])
    leibniz = {match["of"].lower() for match in LEIBNIZ.finditer(text) if match["of"]}
    return frozenset(leibniz | {match.group(1).lower() for match in _PRIMED.finditer(text)})


def asks_at_a_point(text: str) -> bool:
    """``text`` asks for a value at a point, not a function."""
    text = fold_primes(text[:_MAX_TEXT])
    if PRIME_AT_NUMBER.search(text):
        return True
    differentiated = differentiated_letters(text)
    for match in _AT.finditer(text):
        letter = match.group("letter")
        defines = (
            letter is not None
            and letter.lower() in differentiated
            and _FORMULA_ON.match(text, match.end("number")) is not None
        )
        if not defines:
            return True
    return False

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
# d/dx, dy/dx, d^2y/dx^2, d²y/dx², d^{2}y/dx^{2}, d3y/dx3, d^ny/dx^n: the order written on
# the first d (``match/derivative_order.py`` reads it), the letter differentiated and the
# variable. Each run of space is read once (possessive), so a run after "d^" costs its length.
LEIBNIZ = re.compile(
    r"(?<![A-Za-z])d\s*+(?:\^\s*+[({]?\s*+(?:(?P<order>\d{1,2})|(?P<letter>[a-zA-Z]))\s*+[)}]?\s*+"
    r"|(?P<script>[²³⁴])\s*+|(?P<plain>[2-4]))?"
    r"(?:(?P<of>[a-zA-Z])\s*+)?/\s*+d\s*+(?P<var>[a-zA-Z])"
    r"(?:\s*+\^\s*+(?:[({]\s*+(?:\d{1,2}|[a-zA-Z])\s*+[)}]|\d{1,2}|[a-zA-Z])|\s*+[²³⁴]"
    r"|[2-4](?![\d.]))?(?![A-Za-z])"
)
# A point a value is asked at: a number, a fraction, or a multiple of π (π/2, 2π, pi/4).
# Compiled, so no reader of the prompt's copy takes its pattern for a rule.
CONSTANT_POINT = re.compile(
    rf"(?:{SIGNED_DECIMAL}(?:\s*(?:\*\s*)?(?:π|pi)(?![a-z]))?|[+-]?(?:π|pi)(?![a-z]))"
    r"(?:\s*/\s*\d+(?:\.\d+)?)?"
)
# f'(3), y''(0), f'(π/2): a derivative written at a point.
PRIME_AT_NUMBER = re.compile(rf"(?<![A-Za-z])[a-zA-Z]'{{1,3}}\(\s*({CONSTANT_POINT.pattern})\s*\)")
_PRIMED = re.compile(r"(?<![A-Za-z])([a-zA-Z])'")
_AT = re.compile(
    r"\b(?:at|when|where)\s+(?:the\s+point\s+)?"
    rf"(?:(?P<letter>[a-z])\s*=\s*(?P<number>{CONSTANT_POINT.pattern})|\(\s*-?\d)",
    re.IGNORECASE,
)
# A formula goes on after the number: "2x^3", "3 + x^2".
_FORMULA_ON = re.compile(r"[\w(^]|\.\d|\s*[-+*/^]")


def point_value(written: str) -> str:
    """A ``CONSTANT_POINT`` as SymPy reads it: "π/2" is "pi/2", "2π" is "2*pi"."""
    compact = re.sub(r"\s+", "", written).replace("π", "pi")
    return re.sub(r"(?<=[\d.])\*?pi", "*pi", compact)


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

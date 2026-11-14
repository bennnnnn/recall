"""What a card's final value is: a value with no arithmetic left, named or not.

The card lander (``answer_fence.land_answer_card``) cards the last value under an Answer
heading and the final values just before it; a line with arithmetic left is working.
"""

from __future__ import annotations

import re

# The name a final value is set to: a symbol (``x_1``, ``f_{max}``), a word (``type``) or a
# command (``\gcd``, ``\operatorname{lcm}``).
_VALUE_NAME = re.compile(r"[A-Za-z]+(?:_\{?\w+\}?)?|\\[A-Za-z]+(?:\{[A-Za-z]+\})?")
# A note in words after a value: "(at x = -3)", "(radius)".
_VALUE_NOTE = re.compile(r"\s+\((?=[A-Za-z])[^()]*\)\s*$")
# A point or an interval is one value, not a difference: "(1,-2,3)", "(-\infty,-3) \cup (1,\infty)".
_GROUPED = re.compile(r"[(\[][^()\[\]]*[)\]]|\\cup")
_UNIT_TEXT = re.compile(r"\\(?:text|mathrm)\{[^}]*\}")
# Arithmetic still to do: a product, quotient, fraction, power, sum, or a minus
# after a term (a leading minus is the value's sign).
_ARITHMETIC = re.compile(r"\\(?:times|cdot|div|frac)|[\u00d7\u00b7*/\u00f7+^]|\S\s*[-\u2212]")
# An exact fraction is a value, not a division still to do: x = \frac{1}{2}.
_EXACT_FRACTION = re.compile(r"\\d?frac\{-?\d+\}\{-?\d+\}")


def is_final_value(value: str) -> bool:
    """``x = 2``, ``f_{max} = 15`` (at x = 3), ``C = (1,-2,3)``, ``\\gcd = 18``, a bare ``32``:
    a value, named or not, with no arithmetic left, unlike the working line ``v = 9.8 \\times
    2`` or ``2x = 4``. A part asking several values (a maximum and a minimum, a centre and a
    radius) carded the last alone, the others left above it as working (g12 S2, 2026-11-13)."""
    text = _VALUE_NOTE.sub("", value.replace("$", "").strip())
    left, equals, right = text.partition("=")
    if not equals:
        left, right = "", text
    right = _GROUPED.sub(" 1 ", _EXACT_FRACTION.sub("1", _UNIT_TEXT.sub("", right))).strip()
    named = not left.strip() or _VALUE_NAME.fullmatch(left.strip()) is not None
    return bool(right) and named and _ARITHMETIC.search(right) is None

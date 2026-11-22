"""What a card's final value is: a value with no arithmetic left, named or not.

The card lander (``answer_fence.land_answer_card``) cards the last value under an Answer
heading and the final values just before it; a line with arithmetic left is working.
"""

from __future__ import annotations

import math
import re

# The name a final value is set to: a symbol (``x_1``, ``f_{max}``), a word (``type``) or a
# command (``\gcd``, ``\operatorname{lcm}``).
_VALUE_NAME = re.compile(r"[A-Za-z]+(?:_\{?\w+\}?)?|\\[A-Za-z]+(?:\{[A-Za-z]+\})?")
# A note in words after a value: "(at x = -3)", "(radius)".
_VALUE_NOTE = re.compile(r"\s+\((?=[A-Za-z])[^()]*\)\s*$")
# A point or an interval (a comma inside) is one value, not a difference: "(1,-2,3)",
# "(-\infty,-3) \cup (1,\infty)"; "-(-2)" is arithmetic still to do.
_GROUPED = re.compile(r"[(\[][^()\[\],]*,[^()\[\]]*[)\]]|\\cup")
_UNIT_TEXT = re.compile(r"\\(?:text|mathrm)\{[^}]*\}")
# A degree sign after a number is its unit ("45^\\circ"); after a trig function's angle it is
# working still to evaluate ("\\sin 30^\\circ", Claude on #2509).
_DEGREES = re.compile(r"(?<=\d)[ \t]*\^[ \t]*\{?[ \t]*\\circ[ \t]*\}?")
_TRIG = re.compile(r"\\(?:sin|cos|tan|sec|csc|cot)\b")
# A unit vector: \hat{i}, \hat{\jmath}, \mathbf{k}. Its letter names a direction, no symbol.
UNIT_VECTOR = re.compile(r"\\(?:hat|mathbf|boldsymbol)[ \t]*\{[ \t]*\\?[ijk](?:math)?[ \t]*\}")
# A vector by its components, one value: "(0\hat{i} + 20\hat{j})", "-16\hat{i} + 4\hat{j}".
_TERM = r"\d+(?:\.\d+)?[ \t]*" + UNIT_VECTOR.pattern
_COMPONENTS = re.compile(
    rf"\(?(?:[-\u2212][ \t]*)?{_TERM}(?:[ \t]*[-+\u2212][ \t]*{_TERM})+[ \t]*\)?"
)
# A sizing command before a bracket: "\\left(0\\hat{i} + 20\\hat{j}\\right)" is "(…)".
_SIZED = re.compile(r"\\(?:left|right|[bB]igg?[lr]?)[ \t]*(?=[()\[\]])")
# Arithmetic still to do: a product, quotient, fraction, power, sum, or a minus
# after a term (a leading minus is the value's sign).
_ARITHMETIC = re.compile(r"\\(?:times|cdot|div|frac)|[\u00d7\u00b7*/\u00f7+^]|\S\s*[-\u2212]")
# An exact fraction is a value, not a division still to do: x = \frac{1}{2}.
_EXACT_FRACTION = re.compile(r"\\d?frac\{-?\d+\}\{-?\d+\}")
# A fraction on a line, "5/7": a value in its lowest terms, a division still to do otherwise
# ("100/5").
_SLASHED = re.compile(r"(-?\d+)\s*/\s*(\d+)")


def is_final_value(value: str) -> bool:
    """``x = 2``, ``f_{max} = 15`` (at x = 3), ``C = (1,-2,3)``, ``\\gcd = 18``, a bare ``32``:
    a value, named or not, with no arithmetic left, unlike the working line ``v = 9.8 \\times
    2`` or ``2x = 4``. A part asking several values (a maximum and a minimum, a centre and a
    radius) carded the last alone, the others left above it as working (g12 S2, 2026-11-13).
    A vector by its components, ``v_A = (0\\hat{i} + 20\\hat{j})``, is one value too, and a
    degree sign (``45^\\circ``) is a unit, no power."""
    text = _VALUE_NOTE.sub("", value.replace("$", "").strip())
    left, equals, right = text.partition("=")
    if not equals:
        left, right = "", text
    right = _GROUPED.sub(" 1 ", _EXACT_FRACTION.sub("1", _UNIT_TEXT.sub("", right)))
    if _TRIG.search(right) is None:
        right = _DEGREES.sub("", right)
    right = _COMPONENTS.sub(" 1 ", _SIZED.sub("", right)).strip()
    slashed = _SLASHED.fullmatch(right)
    if slashed is not None:
        top, bottom = abs(int(slashed.group(1))), int(slashed.group(2))
        # A ratio is its pair in lowest terms: "S = 5/7" (2026-11-21).
        right = "1" if bottom > 1 and math.gcd(top, bottom) == 1 else right
    named = not left.strip() or _VALUE_NAME.fullmatch(left.strip()) is not None
    return bool(right) and named and _ARITHMETIC.search(right) is None

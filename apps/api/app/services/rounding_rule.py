# ruff: noqa: RUF002, RUF003 -- the point of this module is × and superscripts.
"""How an answer card shows its number, for every subject: the one rule (owner, 2026-11-18).

- Two decimal places, zeros kept: 2.453 is 2.45, 2.4 is 2.40, 19394.567 is 19394.57. A whole
  result stays whole (1500). A value two places would round to fewer than three figures keeps
  three significant figures (0.455, 0.0567, 0.00123): a card is never more than 0.5% off.
- Written in full below 10⁹; a power of ten only from 10⁹, or below 0.001, to three
  significant figures (6.02 × 10²³, 1.60 × 10⁻¹⁹).
- No thousands separators: the card reads like the working above it.
- The precision the question asks for wins: decimal places, significant figures, or none.

A 5 rounds up (``school_rounding``). The working ends on the value unrounded; only the card
rounds, once. Cards had switched between 1.09 × 10⁵ and 109324 for one pressure, as the
model or a subject's own policy chose (the owner's chat, 2026-11-18).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from app.services.school_rounding import (
    MOST_DIGITS,
    asked_rounding,
    format_places,
    round_figures,
    trim_zeros,
)

PLACES = 2
SMALL_FIGURES = 3
POWER_FROM = 1e9
POWER_BELOW = 1e-3


@dataclass(frozen=True)
class Precision:
    """What the question asks its answer to: significant figures, decimal places, or no
    rounding at all; none of them is the rule's two places."""

    figures: int = 0
    places: int = -1
    unrounded: bool = False


RULE = Precision()

# "don't round", "without rounding", "no rounding", "unrounded", "the exact value".
_UNROUNDED = re.compile(
    r"\b(?:(?:do\s*n[o']?t|don't|no|without|not)\s+round(?:ing|ed)?|unrounded|"
    r"exact\s+(?:value|answer|number)|full\s+precision)\b",
    re.IGNORECASE,
)


def asked_precision(text: str) -> Precision:
    """The precision ``text`` asks for (``school_rounding.asked_rounding``, and no rounding)."""
    if _UNROUNDED.search(text):
        return Precision(unrounded=True)
    figures, places, _span = asked_rounding(text)
    return Precision(figures=min(figures, MOST_DIGITS), places=min(places, MOST_DIGITS))


def number_parts(value: float | Fraction, precision: Precision = RULE) -> tuple[str, int | None]:
    """The mantissa as written and its power of ten, None for a number written in full."""
    number = float(value)
    if not math.isfinite(number) or number == 0:
        return ("0" if number == 0 else str(number)), None
    huge_or_tiny = abs(number) >= POWER_FROM or abs(number) < POWER_BELOW
    if precision.unrounded:
        return _unrounded(number, huge_or_tiny)
    if precision.figures > 0:
        return _figures(number, precision.figures, huge_or_tiny)
    if precision.places >= 0:
        return format_places(number, precision.places), None
    if huge_or_tiny:
        return _figures(number, SMALL_FIGURES, True)
    if math.isclose(number, round(number), rel_tol=1e-12, abs_tol=1e-12):
        return str(round(number)), None
    shown = format_places(number, PLACES)
    lost = not math.isclose(float(shown), number, rel_tol=1e-12)
    if lost and len(shown.lstrip("-").replace(".", "").lstrip("0")) < SMALL_FIGURES:
        return _figures(number, SMALL_FIGURES, False)
    return shown, None


def _figures(number: float, figures: int, power: bool) -> tuple[str, int | None]:
    mantissa, exponent = round_figures(number, figures)
    if power:
        return f"{mantissa:.{figures - 1}f}", exponent
    decimals = max(figures - 1 - exponent, 0)
    return f"{float(mantissa.scaleb(exponent)):.{decimals}f}", None


def _unrounded(number: float, power: bool) -> tuple[str, int | None]:
    """Every digit the value has, as the shortest decimal that names it."""
    exact = Decimal(repr(number))
    if not power:
        return trim_zeros(format(exact, "f")), None
    exponent = exact.adjusted()
    return trim_zeros(format(exact.scaleb(-exponent), "f")), exponent


def number_latex(value: float | Fraction, precision: Precision = RULE) -> str:
    """``2.45``, ``6.02 \\times 10^{23}``."""
    mantissa, exponent = number_parts(value, precision)
    return mantissa if exponent is None else rf"{mantissa} \times 10^{{{exponent}}}"

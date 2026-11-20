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

from app.services.number_text import count_word_pattern, number_word_value
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


# A precision said on its own, as a reply to an answer: "1 digit", "2 dp", "3 sig figs",
# "to 2 decimals". A digit or a place is a decimal place (owner, 2026-11-20: "1 digit" after
# a card of 3.13 m/s is 3.1 m/s); a figure is a significant one.
_SAID_ALONE = re.compile(
    rf"(?<![\w.])(?:(?:to|in)[ \t]+)?(?P<count>\d{{1,2}}|{count_word_pattern(low=1, high=12)})"
    r"[ \t]*(?:(?P<figures>sig(?:nificant)?\.?[ \t]*(?:fig(?:ure)?s?|digits?)|s\.?[ \t]?f\.?)"
    r"|(?P<places>(?:decimal[ \t]+)?(?:places?|digits?)|decimals?|d\.?[ \t]?p\.?))(?![\w])",
    re.IGNORECASE,
)
# A message that asks a precision and nothing else: the precision, said with no more than the
# words a rounding request is made with ("round it to 1 dp please", "what about 2 dp?",
# "can you give it in 3 sig figs"). "Explain 2 sig figs", "why 1 digit?", "a 3 digit number"
# ask something else.
_REQUEST_WORDS = frozenset(
    "round rounded rounding it that this the answer value give make write show do "
    "now just only please pls can could you and what about then instead ok okay yes "
    "thanks thank".split()
)
# No rounding, as a reply to a card: "no rounding", "don't round it". "The exact answer" is
# no decimal at all (√2, 9π), so it is the model's to write.
_NOT_ROUNDED = re.compile(
    r"\b(?:(?:do\s*n[o']?t|don't|no|without|not)\s+round(?:ing|ed)?|unrounded|full\s+precision)\b",
    re.IGNORECASE,
)
_WORD = re.compile(r"[a-z']+", re.IGNORECASE)
_ALONE_WORDS = 8


def asked_precision(text: str) -> Precision:
    """The precision ``text`` asks for (``school_rounding.asked_rounding``, no rounding, or a
    precision said on its own, ``precision_only``)."""
    if _UNROUNDED.search(text):
        return Precision(unrounded=True)
    figures, places, _span = asked_rounding(text)
    if figures == 0 and places < 0:
        return precision_only(text) or RULE
    return Precision(figures=min(figures, MOST_DIGITS), places=min(places, MOST_DIGITS))


def precision_only(text: str) -> Precision | None:
    """The precision a message asks for when that is all it asks ("1 digit", "2 sig figs",
    "round it to 1 dp", "to the nearest whole number", "no rounding"): a reply to the answer
    before it. None for a message that asks anything else, or no precision."""
    if len(text.split()) > _ALONE_WORDS or (said := _precision_said(text)) is None:
        return None
    (start, end), precision = said
    around = f"{text[:start]} {text[end:]}"
    if any(character.isdigit() for character in around):
        return None
    words = {word.lower() for word in _WORD.findall(around)}
    return precision if words <= _REQUEST_WORDS else None


def _precision_said(text: str) -> tuple[tuple[int, int], Precision] | None:
    """Where ``text`` says a precision, and which."""
    if (unrounded := _NOT_ROUNDED.search(text)) is not None:
        return unrounded.span(), Precision(unrounded=True)
    figures, places, span = asked_rounding(text)
    if span is not None and (figures > 0 or places >= 0):
        return span, Precision(figures=min(figures, MOST_DIGITS), places=min(places, MOST_DIGITS))
    said = _SAID_ALONE.search(text)
    if said is None:
        return None
    count = int(said["count"]) if said["count"].isdigit() else number_word_value(said["count"])
    if count is None or (said["figures"] and count == 0):
        return None  # no significant figure at all is no precision
    count = min(count, MOST_DIGITS)
    precision = Precision(figures=count) if said["figures"] else Precision(places=count)
    return said.span(), precision


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

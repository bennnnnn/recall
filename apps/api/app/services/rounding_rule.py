# ruff: noqa: RUF001, RUF002, RUF003 -- the point of this module is × and superscripts.
"""How an answer card shows its number, for every subject: the one rule (owner, 2026-11-18).
A chemistry solver's checked card is the exception: it keeps the data's significant figures
(``card_precision_own``).

- Two decimal places, zeros kept: 2.453 is 2.45, 2.4 is 2.40, 19394.567 is 19394.57, and
  below 1 too: 0.577 is 0.58, 0.4551 is 0.46 (owner, 2026-11-25, replacing 2026-11-19's
  three figures under 1). A whole result stays whole (1500). Only a value below 0.1
  (``SMALL_BELOW``), which two places would show as next to nothing, keeps three
  significant figures (0.0649, 0.00123). A zero is added only to a value known to that
  place: the server's own, or one the working above a model's card works out
  (``card_numbers``); a card the model rounded with nothing to work it from keeps the figures
  it wrote (43.9°, never 43.90° for 43.877°).
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
# Below this a value keeps SMALL_FIGURES significant figures instead of PLACES places: the
# one line that says what a "small" value is.
SMALL_BELOW = 0.1
POWER_FROM = 1e9
POWER_BELOW = 1e-3


@dataclass(frozen=True)
class Precision:
    """What the question asks its answer to: significant figures, decimal places, or no
    rounding at all; none of them is the rule's two places."""

    figures: int = 0
    places: int = -1
    unrounded: bool = False
    # "To the correct number of significant figures": the data's own precision, which only
    # the values a solver read can say (``data_precision``); unresolved, it is the rule.
    data: bool = False


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


# "to the correct number of significant figures", "an appropriate number of sig figs": the
# precision of the question's own data, which a school class grades.
_DATA_FIGURES = re.compile(
    r"\b(?:correct|appropriate|right|proper|suitable|sensible|same)\s+number\s+of\s+"
    r"(?:significant\s+(?:figures?|digits?)|sig(?:nificant)?\.?\s*figs?|s\.\s?f\.?)",
    re.IGNORECASE,
)


def mantissa_figures(literal: str) -> int:
    """The figures a typed number's mantissa holds, its sign and exponent aside: "2.0e-6" is
    2, "-5.0" 2, "0.0050" 2, "200" 3 (chemistry's count, ``chemistry.sig_figs``)."""
    mantissa = re.split(r"[eE]", literal.strip().lstrip("+-−"))[0]
    return max(len(mantissa.replace(".", "").lstrip("0")), 1)


def written_figures(digits: str) -> int:
    """The significant figures a number is written to, 0 when it says none: "1.20" is 3,
    "0.050" 2, "12" 2, "2.0e-6" 2, "-5.0" 2; a whole number ending in zeros with no power of
    ten (3000, 10) may hold places only."""
    literal = digits.strip().lstrip("+-−")
    mantissa = re.split(r"[eE]", literal)[0]
    if "." not in mantissa and mantissa == literal and mantissa != mantissa.rstrip("0"):
        return 0
    return mantissa_figures(literal)


def data_precision(precision: Precision, figures: int) -> Precision:
    """``precision`` with the data's figures in place of its "the correct number of
    significant figures": ``figures`` from the values a solver read, 0 when no solver read
    any, and then the rule's places."""
    if not precision.data:
        return precision
    return Precision(figures=min(figures, MOST_DIGITS)) if figures > 0 else RULE


def asked_precision(text: str) -> Precision:
    """The precision ``text`` asks for (``school_rounding.asked_rounding``, no rounding, the
    data's own significant figures, or a precision said on its own, ``precision_only``).

    "Give the answer to the correct number of significant figures" asks the precision of the
    data: a trolley going 4.345 m in 1.2 s is 3.6 m/s, and its card read 3.62 m/s, verified
    (textbook round, 2026-11-26). Which figures those are is the solver's to say, from the
    values it read, never from any number written (a list's "1." is no datum):
    ``data_precision`` resolves it."""
    if _UNROUNDED.search(text):
        return Precision(unrounded=True)
    figures, places, _span = asked_rounding(text)
    if figures == 0 and places < 0 and _DATA_FIGURES.search(text):
        return Precision(data=True)
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
    # The rule's own rounding (never a precision asked for, which may want 15 digits: π to 15
    # places is 3.141592653589793): a float a hair under a tie is the tie, 0.0001 × 50² / 2
    # is 0.125 and 0.1 × 0.1235 is 0.01235, and their 5 rounds up (review, #2591).
    number = float(f"{number:.12g}")
    if huge_or_tiny:
        return _figures(number, SMALL_FIGURES, True)
    if math.isclose(number, round(number), rel_tol=1e-12, abs_tol=1e-12):
        return str(round(number)), None
    shown = format_places(number, PLACES)
    lost = not math.isclose(float(shown), number, rel_tol=1e-12)
    if lost and abs(number) < SMALL_BELOW:
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


# The most significant figures a line of working writes: the working ends on its value
# unrounded, as a person writes it, never a calculator's sixteen digits ("-9.043478260869565"
# is -9.04348), the figures physics' own working keeps (``display.GIVEN_FIGURES``).
WORKING_FIGURES = 6
# A decimal in working, with an ellipsis after it saying its digits go on.
_LONG_DECIMAL = re.compile(
    r"(?<![\w.^_{])(?P<digits>\d+\.\d+)(?P<dots>[ \t]*(?:…|\.\.\.|\\[lc]?dots(?![A-Za-z])))?"
)


# Places past the point that are a calculator's, not a person's: 0.357142857, never 16288.95.
_CALCULATOR_PLACES = 7


def working_figures(tex: str) -> str:
    """A line of working's calculator digits written to ``WORKING_FIGURES`` significant
    figures, its ellipsis dropped (``0.357142857\\ldots`` is 0.357143, -9.043478260869565 is
    -9.04348). A calculator's digits run seven places or more past the point, or say they go
    on; a person's decimal (16288.95, 12345.67), a whole number, a script and an exponent stay
    as written, and a digit before the point is never cut (owner, 2026-11-25). For a line
    of working only: a card and a given are the rule's and the user's."""

    def shorter(match: re.Match[str]) -> str:
        digits = match["digits"]
        whole, _point, places = digits.partition(".")
        figures = len(digits.replace(".", "").lstrip("0"))
        long_run = len(places) >= _CALCULATOR_PLACES or match["dots"] is not None
        if not long_run or figures <= WORKING_FIGURES:
            return match[0]
        kept = max(WORKING_FIGURES, len(whole.lstrip("0")))
        mantissa, exponent = round_figures(float(digits), kept)
        return trim_zeros(format(mantissa.scaleb(exponent), "f"))

    return _LONG_DECIMAL.sub(shorter, tex)

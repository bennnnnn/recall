"""Every number a physics question states, with its unit and dimension.

The extractors bind values by keyword. This scan is the independent record of
what the question actually supplied, so the request boundary can check that a
verified solve did not skip a stated quantity of the kind it used.

Units come from a closed table rather than free-form Pint parsing: Pint reads
prose as units ("at" is a technical atmosphere, "in" an inch, "a" a year).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from app.modules.physics.given_units import _SYMBOLS, _WORDS
from app.modules.physics.numbers import numeric_spans

# The dimension of an angle. Pint calls degrees dimensionless, which would let
# a 30° angle compete with a friction coefficient.
ANGLE = "[angle]"

_ANGLE_UNITS = frozenset({"degree", "radian"})


def _alternation(spellings: list[str]) -> str:
    return "|".join(re.escape(spelling) for spelling in sorted(spellings, key=len, reverse=True))


# A unit ends where the next character cannot continue it: "m" is not "mass",
# "s" is not "s.f.", and "m/s" is not the "m" of "m/s".
_END = r"(?![A-Za-z0-9/^²³µμΩ°]|\.[A-Za-z])"
_SYMBOL_RE = re.compile(rf"[ \t]?(?P<unit>{_alternation(list(_SYMBOLS))}){_END}")
_WORD_RE = re.compile(rf"[ \t]?(?P<unit>{_alternation(list(_WORDS))}){_END}", re.IGNORECASE)

# Not quantities: "to 3 s.f.", "2 decimal places", "the 2nd ball", "m/s^2".
_NOT_A_GIVEN_AFTER = re.compile(
    # "s.f." must end there: "in 5 s. Find" is five seconds, then a sentence.
    r"\s*(?:s\.?\s?f\.?(?![a-z])|sig(?:nificant)?\.?\s*fig(?:ure)?s?|d\.?\s?p\.?\b"
    r"|decimal\s+places?"
    r"|(?:st|nd|rd|th)\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Given:
    """One stated number. ``dimension`` is None when it carries no known unit."""

    start: int
    end: int
    value: float
    unit: str
    dimension: str | None
    si: float | None


@lru_cache(maxsize=256)
def unit_dimension(expression: str) -> tuple[str, float, float] | None:
    """(dimension, scale, offset) of one Pint expression, angles kept apart."""
    from app.services.units import get_unit_registry

    if expression in _ANGLE_UNITS:
        scale = 1.0 if expression == "radian" else 0.017453292519943295
        return ANGLE, scale, 0.0
    registry = get_unit_registry()
    try:
        if expression == "degC":
            return _canonical({"[temperature]": 1}), 1.0, 273.15
        quantity = registry.Quantity(1.0, expression).to_base_units()
    except Exception:
        return None
    dimensionality = quantity.dimensionality
    powers = {str(name): float(dimensionality[name]) for name in dimensionality}
    return _canonical(powers), float(quantity.magnitude), 0.0


def _canonical(powers: dict[str, float]) -> str:
    """One spelling per dimension; Pint's own order depends on how it was built."""
    if not powers:
        return "dimensionless"
    return " * ".join(f"{name}^{power:g}" for name, power in sorted(powers.items()))


def unit_expression(spelling: str) -> str | None:
    """The Pint expression of one spelling from the unit table."""
    if spelling == "c":
        return "speed_of_light"
    return _SYMBOLS.get(spelling) or _WORDS.get(spelling.lower())


# A speed written as a fraction of c. Written onto the number ("0.8c"), any
# number is one. With a space, only a decimal below 1 is ("0.8 c"): "question
# 2 c" and "part c)" label a part of the question, not a speed.
FRACTION_OF_C = re.compile(r"\dc(?![A-Za-z0-9])|(?<![\d.])0?\.\d+[ \t]c(?![A-Za-z0-9)])")
_LIGHT_SPEED_RE = re.compile(r"c(?![A-Za-z0-9])")
_SPACED_LIGHT_SPEED_RE = re.compile(r"[ \t]c(?![A-Za-z0-9)])")
_FRACTION_BEFORE_RE = re.compile(r"(?<![\d.])0?\.\d+\Z")


def _speed_of_light_at(text: str, end: int) -> bool:
    if _LIGHT_SPEED_RE.match(text, end):
        return True
    if not _SPACED_LIGHT_SPEED_RE.match(text, end):
        return False
    # A number is short; the window keeps this check constant-time.
    return _FRACTION_BEFORE_RE.search(text[max(0, end - 32) : end]) is not None


def unit_at(text: str, end: int) -> tuple[str, str] | None:
    """The unit written right after a number: (spelling, Pint expression)."""
    if _speed_of_light_at(text, end):
        return "c", "speed_of_light"
    word = _WORD_RE.match(text, end)
    symbol = _SYMBOL_RE.match(text, end)
    # The longer spelling wins: "m/s" over "m", "kg" over "g", "ms" over "m".
    if word is not None and (symbol is None or word.end() >= symbol.end()):
        spelling = word.group("unit")
        return spelling, _WORDS[spelling.lower()]
    if symbol is not None:
        spelling = symbol.group("unit")
        return spelling, _SYMBOLS[spelling]
    return None


def scan_givens(text: str) -> list[Given]:
    """Every stated number in normalized solver input, in written order."""
    givens: list[Given] = []
    for start, end in numeric_spans(text):
        if text[max(0, start - 1) : start] == "^" or text[max(0, start - 2) : start] == "**":
            continue
        if _NOT_A_GIVEN_AFTER.match(text, end):
            continue
        try:
            value = float(text[start:end])
        except ValueError:
            continue
        unit = unit_at(text, end)
        if unit is None:
            givens.append(Given(start, end, value, "", None, None))
            continue
        spelling, expression = unit
        reading = unit_dimension(expression)
        if reading is None:
            givens.append(Given(start, end, value, spelling, None, None))
            continue
        dimension, scale, offset = reading
        givens.append(Given(start, end, value, spelling, dimension, value * scale + offset))
    return givens

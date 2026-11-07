"""Every number a physics question states, with its unit and dimension.

The scan is shared (``services.law_binding.givens``); physics brings its unit table
(``given_units``) and one unit no table can list: a speed written as a fraction of c.
"""

from __future__ import annotations

import re
from functools import lru_cache
from itertools import product

from app.modules.physics.given_units import _LOWERCASE, _SYMBOLS, _WORDS
from app.modules.physics.set_aside import set_aside
from app.services.law_binding.givens import Given
from app.services.law_binding.givens import scan_givens as _scan_givens
from app.services.law_binding.units import ANGLE, UnitTable, keeps_prefix, unit_dimension

__all__ = [
    "ANGLE",
    "FRACTION_OF_C",
    "PHYSICS_UNITS",
    "Given",
    "scan_givens",
    "set_aside",
    "unit_at",
    "unit_dimension",
    "unit_expression",
    "unit_readings",
]

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


# "0.003 u of mass is lost": an atomic mass unit, written apart from its
# number and followed by "of" or the end of a sentence. Written onto the
# number ("2u") or inside an equation ("u + at") it is a velocity.
_ATOMIC_MASS_UNIT_RE = re.compile(r"[ \t]u(?=[ \t]+of\b|[ \t]*[.,;?!]|[ \t]*\Z)")


def _special_unit(text: str, end: int) -> tuple[str, str] | None:
    if _speed_of_light_at(text, end):
        return ("c", "speed_of_light")
    if _ATOMIC_MASS_UNIT_RE.match(text, end):
        return ("u", "dalton")
    return None


PHYSICS_UNITS = UnitTable(
    _SYMBOLS,
    _WORDS,
    special=_special_unit,
    exact={"c": "speed_of_light", "u": "dalton"},
    aside=set_aside,
)


def unit_expression(spelling: str) -> str | None:
    """The Pint expression of one spelling from the physics unit table."""
    return PHYSICS_UNITS.expression(spelling)


@lru_cache(maxsize=512)
def unit_readings(unit: str) -> tuple[str, ...]:
    """The Pint expressions a unit an extractor wrote may mean, the table's first.

    The table reads the unit as written; a key of the caseless list is the second
    reading, for an extractor that matched without case, unless that changes its SI
    prefix (``keeps_prefix``). A spelling the tables list only in another case has no
    reading: "Ms" matched as "ms" is a millisecond or a megasecond, and Pint read it as
    5e6 s; "Cal", a food Calorie, folded to a calorie (reviews 2026-11-07). The spelling
    itself is next, for Pint, then its factors one by one (``_product_readings``).
    ``to_si`` takes the first of the dimension it expects.
    """
    written = PHYSICS_UNITS.expression(unit)
    lower = unit.lower()
    folded = _LOWERCASE.get(lower)
    if folded is not None and not keeps_prefix(unit, folded):
        folded = None
        if written is None:
            return ()
    if written is None and folded is None and lower in _OTHER_CASES:
        return ()
    readings = (written, folded, unit, *_product_readings(unit))
    return tuple(dict.fromkeys(reading for reading in readings if reading))


# Every spelling the tables read, in lowercase: one written in a case they do not list
# names a unit they read only in another case.
_OTHER_CASES = frozenset(
    spelling.lower() for spelling in (*PHYSICS_UNITS.symbols, *PHYSICS_UNITS.words)
)


# One factor of a unit written as a product of powers: "/" or "per" divides by it, and its
# power is written "^-2", "-2", "2", "²" or "⁻²".
_FACTOR = re.compile(
    r"\s*(?P<op>/|per\s+|[·*.])?\s*(?P<letters>[A-Za-zµμΩÅ°]+)"
    r"(?P<power>\^-?\d+|-\d+|\d+|⁻?[¹²³])?"
)
_SUPERSCRIPTS = str.maketrans("⁻¹²³", "-123")
_MAX_READINGS = 8


def _factor_readings(letters: str, powered: bool) -> list[tuple[str, ...]]:
    """The table's readings of letters written together, each a tuple of Pint names.

    Read as two only when the table has no reading of them whole, or a power follows,
    which belongs to the last unit: "Nm^-1" is N·m⁻¹, "ms^-2" m·s⁻² or a millisecond⁻².
    """
    whole = PHYSICS_UNITS.expression(letters)
    readings: list[tuple[str, ...]] = [(whole,)] if whole else []
    if whole and not powered:
        return readings
    readings.extend(
        (head, tail)
        for cut in range(1, len(letters))
        if (head := PHYSICS_UNITS.expression(letters[:cut]))
        and (tail := PHYSICS_UNITS.expression(letters[cut:]))
    )
    return readings


def _product_readings(unit: str) -> list[str]:
    """``unit`` read factor by factor, each factor a table spelling or two written together.

    "Nm^-1" is N·m⁻¹, "ms^-2" m·s⁻² beside a millisecond⁻², "m s-2" m·s⁻² where Pint
    subtracts 2: a g written so was refused (review 2026-11-07).
    """
    factors: list[tuple[int, list[tuple[str, ...]], int]] = []
    at = 0
    while at < len(unit):
        part = _FACTOR.match(unit, at)
        if part is None or part.end() == at:
            return []
        options = _factor_readings(part.group("letters"), part.group("power") is not None)
        if not options:
            return []
        power = int((part.group("power") or "1").replace("^", "").translate(_SUPERSCRIPTS))
        factors.append(
            (-1 if (part.group("op") or "").strip() in {"/", "per"} else 1, options, power)
        )
        at = part.end()
    readings: list[str] = []
    # A power on the last of two units written together may have lost its sign or slash:
    # "g = 9.8 ms²" is m/s² (review 2026-11-07). Read last, only where no other reading
    # has the dimension the slot expects.
    for flipped in (False, True):
        for choice in product(*(options for _sign, options, _power in factors)):
            if flipped and not any(
                len(names) == 2 and power > 0
                for (_s, _o, power), names in zip(factors, choice, strict=True)
            ):
                continue
            terms = [
                f"({name}) ** {sign * _power_of(index, names, power, flipped)}"
                for (sign, _options, power), names in zip(factors, choice, strict=True)
                for index, name in enumerate(names)
            ]
            readings.append(" * ".join(terms))
            if len(readings) == _MAX_READINGS:
                return readings
    return readings


def _power_of(index: int, names: tuple[str, ...], power: int, flipped: bool) -> int:
    """The power of one unit of a factor: the written one on its last unit, negated on
    the second of two written together when ``flipped``."""
    if index != len(names) - 1:
        return 1
    return -power if flipped and len(names) == 2 and power > 0 else power


def unit_at(text: str, end: int) -> tuple[str, str] | None:
    """The unit written right after a number: (spelling, Pint expression)."""
    return PHYSICS_UNITS.at(text, end)


def scan_givens(text: str) -> list[Given]:
    """Every stated number in normalized physics input, in written order, but those the
    question sets aside (``set_aside``, the table's ``aside``)."""
    return _scan_givens(text, PHYSICS_UNITS)

"""Regex fragments for a number and its unit in a physics question."""

from __future__ import annotations

import re
from decimal import Decimal
from functools import lru_cache

from app.modules.physics.givens import PHYSICS_UNITS
from app.services.law_binding.units import SI_PREFIXES
from app.services.number_text import TEXT_DECIMAL, TEXT_NUMBER


@lru_cache(maxsize=256)
def with_prefixes(unit_pattern: str) -> str:
    """``unit_pattern`` and each prefixed unit the shared table lists on a unit it reads.

    An extractor's own short list missed "5 kN" and "50 µT", which the givens scan and
    the binder read (audit 2026-11-07). Each is the table's spelling in its own case, on
    a base the pattern reads in that case: r"N" also reads "kN" and "mN", while "h" (an
    hour) reads no "mH" (a millihenry). A reader that widens a pattern so must hand its
    value on in the base unit (``in_base_unit``).
    """
    plain = re.compile(unit_pattern)
    caseless = re.compile(unit_pattern, re.IGNORECASE)
    prefixed = sorted(
        (
            spelling
            for spelling, rest in PHYSICS_UNITS.prefixed.items()
            if plain.fullmatch(rest) and not caseless.fullmatch(spelling)
        ),
        key=len,
        reverse=True,
    )
    if not prefixed:
        return unit_pattern
    return "(?-i:" + "|".join(map(re.escape, prefixed)) + ")|" + unit_pattern


def in_base_unit(value: float, unit: str, unit_pattern: str) -> tuple[float, str]:
    """A value ``with_prefixes`` read in a prefixed unit, in the base unit the pattern reads.

    "2 kΩ" read by r"ohms?|Ω" is (2000.0, "Ω"), so a reader that writes its pattern's own
    unit, as many do ("ohm", "A", "N"), still reads it right. Handed on as "kΩ", the loop
    law took 2 kΩ for 2 Ω, and an inductor 20 mA for 20 A (review 2026-11-07). A unit the
    pattern reads itself is handed on as written. The prefix is raised to the power of the
    unit it is on: a cm² is 10⁻⁴ m².
    """
    base = PHYSICS_UNITS.prefixed.get(unit)
    if base is None or re.fullmatch(unit_pattern, unit, re.IGNORECASE):
        return value, unit
    _name, power = SI_PREFIXES[unit[: len(unit) - len(base)]]
    raised = _FIRST_POWER.match(base)
    written = raised.group("power") if raised is not None else None
    exponent = int((written or "1").replace("^", "").translate(_SUPERSCRIPTS))
    return float(Decimal(repr(value)).scaleb(power * exponent)), base


# The power on the first unit of a spelling: "m^2", "m²", "m3", or none ("m/s").
_FIRST_POWER = re.compile(r"[A-Za-zµμΩÅ°]+(?P<power>\^-?\d+|\d+|⁻?[¹²³])?")
_SUPERSCRIPTS = str.maketrans("⁻¹²³", "-123")


# The extractors' short names for the shared running-text number, and the same
# number without an exponent, as an angle or a reading is written.
NUMBER = TEXT_NUMBER


DECIMAL = TEXT_DECIMAL


# The unit after an angle in degrees.
DEGREE_WORD = r"(?:degrees?|deg|\u00b0)"


LENGTH_UNIT_PATTERN = (
    r"kilometers?|km|centimeters?|cm|millimeters?|mm|"
    r"nanometers?|nm|micrometers?|micrometres?|um|µm|"
    r"miles?|mi|meters?|metres?|m|feet|ft|yards?|yd|inches?|in"
)


VELOCITY_UNIT_PATTERN = r"m/s|km/h|mph|cm/s|mm/s|miles\s+per\s+hour"


AMP_PATTERN = r"A|amps?|amperes?"


OHM_PATTERN = r"ohms?|\u03a9"


TESLA_PATTERN = r"T|tesla|teslas|mT|millitesla"


MASS_UNITS = r"kg|mg|g|lb|lbs|oz"

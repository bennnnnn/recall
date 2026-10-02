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

from app.modules.physics.numbers import numeric_spans

# The dimension of an angle. Pint calls degrees dimensionless, which would let
# a 30° angle compete with a friction coefficient.
ANGLE = "[angle]"

# Spelling -> Pint expression. Single letters are case-sensitive SI symbols;
# a lowercase "a" is an article and "v" a variable. Longer spellings below are
# matched without case.
_SYMBOLS: dict[str, str] = {
    "m": "meter",
    "g": "gram",
    "s": "second",
    "h": "hour",
    "N": "newton",
    "J": "joule",
    "W": "watt",
    "A": "ampere",
    "V": "volt",
    "C": "coulomb",
    "F": "farad",
    "H": "henry",
    "T": "tesla",
    "K": "kelvin",
    "L": "liter",
    "Ω": "ohm",
    "°": "degree",
    "%": "percent",
    "mA": "milliampere",
    "MW": "megawatt",
    "mW": "milliwatt",
    "mV": "millivolt",
    "MV": "megavolt",
    "kV": "kilovolt",
    "mH": "millihenry",
    "mT": "millitesla",
    "uC": "microcoulomb",
    "µC": "microcoulomb",
    "μC": "microcoulomb",
    "nC": "nanocoulomb",
    "mC": "millicoulomb",
    "uF": "microfarad",
    "µF": "microfarad",
    "μF": "microfarad",
    "nF": "nanofarad",
    "pF": "picofarad",
    "mF": "millifarad",
    "kΩ": "kiloohm",
    "MΩ": "megaohm",
    "Pa": "pascal",
    "kPa": "kilopascal",
    "MPa": "megapascal",
    "GPa": "gigapascal",
    # Viscosity, not a pressure: "0.001 Pa*s" is one unit.
    "Pa*s": "pascal * second",
    "Pa·s": "pascal * second",
    "Pa s": "pascal * second",
    "Hz": "hertz",
    "kHz": "kilohertz",
    "MHz": "megahertz",
    "GHz": "gigahertz",
    "kJ": "kilojoule",
    "MJ": "megajoule",
    "kW": "kilowatt",
    "kN": "kilonewton",
    "eV": "electron_volt",
    "keV": "kiloelectron_volt",
    "MeV": "megaelectron_volt",
    "kWh": "kilowatt_hour",
    "mL": "milliliter",
    "ms": "millisecond",
    "mm": "millimeter",
    "Wb": "weber",
}

_WORDS: dict[str, str] = {
    "m/s^2": "meter / second ** 2",
    "m/s2": "meter / second ** 2",
    "m/s²": "meter / second ** 2",
    "m s^-2": "meter / second ** 2",
    "rad/s^2": "radian / second ** 2",
    "rad/s2": "radian / second ** 2",
    "m/s": "meter / second",
    "km/h": "kilometer / hour",
    "kmh": "kilometer / hour",
    "kph": "kilometer / hour",
    "km/s": "kilometer / second",
    "cm/s": "centimeter / second",
    "mm/s": "millimeter / second",
    "mph": "mile / hour",
    "miles per hour": "mile / hour",
    "rad/s": "radian / second",
    "rev/s": "revolution / second",
    "rpm": "revolution / minute",
    "n/m": "newton / meter",
    "kg/m^3": "kilogram / meter ** 3",
    "kg/m3": "kilogram / meter ** 3",
    "g/cm^3": "gram / centimeter ** 3",
    "g/cm3": "gram / centimeter ** 3",
    "kg m^2": "kilogram * meter ** 2",
    "kg·m^2": "kilogram * meter ** 2",
    "kg*m^2": "kilogram * meter ** 2",
    "kgm^2": "kilogram * meter ** 2",
    "kg m/s": "kilogram * meter / second",
    "kg·m/s": "kilogram * meter / second",
    "kg*m/s": "kilogram * meter / second",
    "n s": "newton * second",
    "n·s": "newton * second",
    "n*s": "newton * second",
    "n m": "newton * meter",
    "n·m": "newton * meter",
    "n*m": "newton * meter",
    "j/kg/k": "joule / kilogram / kelvin",
    "j/(kg k)": "joule / kilogram / kelvin",
    "j/(kg·k)": "joule / kilogram / kelvin",
    "j/kgk": "joule / kilogram / kelvin",
    "j/kg°c": "joule / kilogram / kelvin",
    "j/kg/°c": "joule / kilogram / kelvin",
    "j/(kg °c)": "joule / kilogram / kelvin",
    "j kg^-1 k^-1": "joule / kilogram / kelvin",
    "kj/kg": "kilojoule / kilogram",
    "j/kg": "joule / kilogram",
    "w/m^2": "watt / meter ** 2",
    "w/m/k": "watt / meter / kelvin",
    "ohm m": "ohm * meter",
    "ohm·m": "ohm * meter",
    "ω m": "ohm * meter",
    "ω·m": "ohm * meter",
    "m^2": "meter ** 2",
    "m2": "meter ** 2",
    "cm^2": "centimeter ** 2",
    "cm2": "centimeter ** 2",
    "mm^2": "millimeter ** 2",
    "mm2": "millimeter ** 2",
    "m^3": "meter ** 3",
    "m3": "meter ** 3",
    "cm^3": "centimeter ** 3",
    "cm3": "centimeter ** 3",
    "per k": "1 / kelvin",
    "/k": "1 / kelvin",
    "per °c": "1 / kelvin",
    "°c": "degC",
    "degc": "degC",
    "celsius": "degC",
    "degrees celsius": "degC",
    "kelvin": "kelvin",
    "kg": "kilogram",
    "mg": "milligram",
    "tonnes": "metric_ton",
    "tonne": "metric_ton",
    "km": "kilometer",
    "cm": "centimeter",
    "nm": "nanometer",
    "um": "micrometer",
    "µm": "micrometer",
    "μm": "micrometer",
    "mi": "mile",
    "miles": "mile",
    "mile": "mile",
    "ft": "foot",
    "feet": "foot",
    "inches": "inch",
    "inch": "inch",
    "metres": "meter",
    "meters": "meter",
    "metre": "meter",
    "meter": "meter",
    "seconds": "second",
    "second": "second",
    "secs": "second",
    "sec": "second",
    "milliseconds": "millisecond",
    "minutes": "minute",
    "minute": "minute",
    "mins": "minute",
    "min": "minute",
    "hours": "hour",
    "hour": "hour",
    "hrs": "hour",
    "hr": "hour",
    "days": "day",
    "day": "day",
    "years": "year",
    "year": "year",
    "newtons": "newton",
    "newton": "newton",
    "joules": "joule",
    "joule": "joule",
    "kilojoules": "kilojoule",
    "watts": "watt",
    "watt": "watt",
    "kilowatts": "kilowatt",
    "amperes": "ampere",
    "ampere": "ampere",
    "amps": "ampere",
    "amp": "ampere",
    "volts": "volt",
    "volt": "volt",
    "ohms": "ohm",
    "ohm": "ohm",
    "kohm": "kiloohm",
    "coulombs": "coulomb",
    "coulomb": "coulomb",
    "microcoulombs": "microcoulomb",
    "farads": "farad",
    "henry": "henry",
    "tesla": "tesla",
    "teslas": "tesla",
    "weber": "weber",
    "hertz": "hertz",
    "pascals": "pascal",
    "pascal": "pascal",
    "atm": "atmosphere",
    "bar": "bar",
    "litres": "liter",
    "litre": "liter",
    "liters": "liter",
    "liter": "liter",
    "ml": "milliliter",
    "moles": "mole",
    "mole": "mole",
    "mol": "mole",
    "degrees": "degree",
    "degree": "degree",
    "deg": "degree",
    "radians": "radian",
    "radian": "radian",
    "rad": "radian",
    "percent": "percent",
}

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
    r"\s*(?:s\.?\s?f\.?|sig(?:nificant)?\.?\s*fig(?:ure)?s?|d\.?\s?p\.?\b|decimal\s+places?"
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


def unit_at(text: str, end: int) -> tuple[str, str] | None:
    """The unit written right after a number: (spelling, Pint expression)."""
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

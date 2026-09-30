# ruff: noqa: RUF001, RUF002, RUF003 -- users type × and a true minus sign.
"""Shared text helpers for the extended chemistry extractors."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.chemistry.elements import BY_SYMBOL, ELEMENTS
from app.modules.chemistry.equations import balance_equation
from app.modules.chemistry.quantity import to_atm, to_kelvin, to_liters
from app.modules.chemistry.request import CHEMICAL_FORMULA, EQUATION_RE
from app.modules.chemistry.species import counts_in_mass_action

_N = r"-?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"

_SUPERSCRIPT_DIGITS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
_TIMES = r"(?:×|x|\*|·|⋅|\\times|\\cdot)"
# "1.8 × 10^-5", "1.8x10^{-5}", "1.8·10⁻⁵". A caret, a star pair or a superscript is
# required: "3 x 10" alone is multiplication, not an exponent.
_MANTISSA_TIMES_POWER = re.compile(
    rf"(?<![\w.])(?P<mantissa>-?(?:\d+(?:\.\d+)?|\.\d+))\s*{_TIMES}\s*10\s*"
    r"(?:(?:\^|\*\*)\s*\{?\s*(?P<sign>[-−+]?)\s*(?P<exp>\d+)\s*\}?"
    r"|(?P<sup>[⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+))"
)
_BARE_POWER_OF_TEN = re.compile(
    r"(?<![\w.^])10\s*(?:\^|\*\*)\s*\{?\s*(?P<sign>[-−+]?)\s*(?P<exp>\d+)\s*\}?(?![\w.])"
)


def _power_text(match: re.Match[str]) -> str:
    if match.groupdict().get("sup"):
        return match.group("sup").translate(_SUPERSCRIPT_DIGITS)
    sign = match.group("sign").replace("−", "-")
    return f"{'' if sign == '+' else sign}{match.group('exp')}"


def normalize_scientific_notation(text: str) -> str:
    """Rewrite ``1.8 × 10^-5`` as ``1.8e-5`` so ``_N`` cannot read only the mantissa."""
    text = _MANTISSA_TIMES_POWER.sub(
        lambda match: f"{match.group('mantissa')}e{_power_text(match)}", text
    )
    return _BARE_POWER_OF_TEN.sub(lambda match: f"1e{_power_text(match)}", text)


TIME_UNIT_PATTERN = r"(?:seconds?|minutes?|hours?|days?|years?|sec|min|hr|yr|h|d|s)"
# unit word -> (label used in answers, seconds per unit)
TIME_UNITS: dict[str, tuple[str, float]] = {
    "s": ("s", 1),
    "sec": ("s", 1),
    "second": ("s", 1),
    "seconds": ("s", 1),
    "min": ("min", 60),
    "minute": ("min", 60),
    "minutes": ("min", 60),
    "h": ("h", 3600),
    "hr": ("h", 3600),
    "hour": ("h", 3600),
    "hours": ("h", 3600),
    "d": ("days", 86400),
    "day": ("days", 86400),
    "days": ("days", 86400),
    "yr": ("years", 31557600),
    "year": ("years", 31557600),
    "years": ("years", 31557600),
}
# A trailing concentration unit means k belongs to another order ("M^-1 s^-1").
_FOREIGN_RATE_UNIT = re.compile(r"\s*(?:M\b|L\b|mol\b|/)")


def rate_constant(text: str, label: str = "k") -> tuple[float, str | None] | None:
    """``k = 0.05 min^-1`` as ``(0.05, "min")``; the unit is ``None`` when none is written.

    ``None`` when the label is absent or its unit is one this reader does not understand.
    """
    match = re.search(
        rf"\b(?-i:{label})\s*=\s*({_N})\s*(?:(?P<unit>{TIME_UNIT_PATTERN})\s*"
        rf"(?:\^\s*-\s*1|⁻¹)|/\s*(?P<per>{TIME_UNIT_PATTERN})\b)?",
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    word = match.group("unit") or match.group("per")
    if word is None:
        if _FOREIGN_RATE_UNIT.match(text[match.end() :]):
            return None
        return float(match.group(1)), None
    return float(match.group(1)), TIME_UNITS[word.lower()][0]


_TIME_TOKEN = re.compile(r"\b(?:min|minutes?|h|hr|hours?|d|days?|yr|years?)\b", re.IGNORECASE)


def k_time_unit_conflict(text: str) -> bool:
    """True when the phrase after ``k = …`` names a time unit other than seconds."""
    match = re.search(rf"\bk\s*=\s*{_N}([^,;]*)", text, re.IGNORECASE)
    return match is not None and _TIME_TOKEN.search(match.group(1)) is not None


def temperature_kelvin(text: str, label: str = "T") -> float | bool | None:
    """``T = 310 K`` or ``T = 37 °C`` in kelvin.

    ``None`` when there is no such label; ``False`` when a value is written without a
    usable unit, so the caller declines instead of assuming 25 °C or kelvin.
    """
    labelled = re.search(rf"\b(?-i:{label})\s*=\s*{_N}", text)
    if labelled is None:
        return None
    match = re.compile(
        rf"\b(?-i:{label})\s*=\s*({_N})\s*({_TEMPERATURE_UNIT})(?![A-Za-z])", re.IGNORECASE
    ).search(text)
    if match is None:
        return False
    return to_kelvin(float(match.group(1)), "celsius" if _celsius(match.group(2)) else "kelvin")


def timed(text: str, label: str) -> tuple[float, str] | None:
    """``t = 10 s`` / ``half-life 2 h`` as ``(10.0, "s")``; ``None`` without a time unit."""
    match = re.search(
        rf"{label}\s*(?:=|of|is)?\s*({_N})\s*({TIME_UNIT_PATTERN})\b", text, re.IGNORECASE
    )
    if match is None:
        return None
    return float(match.group(1)), TIME_UNITS[match.group(2).lower()][0]


def seconds_per(label: str) -> float:
    return next(scale for unit, scale in TIME_UNITS.values() if unit == label)


def _search(pattern: str, text: str, flags: int = re.IGNORECASE) -> float | None:
    match = re.search(pattern, text, flags)
    return float(match.group(1)) if match else None


def _floats(**values: float | None) -> dict[str, float] | None:
    """Return the mapping only when every value was found."""
    cleaned = {key: value for key, value in values.items() if value is not None}
    if len(cleaned) != len(values):
        return None
    return cleaned


def _equation(text: str) -> str | None:
    match = EQUATION_RE.search(text)
    return match.group(1).strip() if match else None


@dataclass(frozen=True)
class AskedQuantity:
    """What the question asks for: ``unit`` is g/mol/L/particles, ``species`` a formula."""

    unit: str | None
    species: str | None


_UNIT_WORDS = {
    "mole": "mol",
    "moles": "mol",
    "amount": "mol",
    "gram": "g",
    "grams": "g",
    "mass": "g",
    "liter": "L",
    "liters": "L",
    "litre": "L",
    "litres": "L",
    "volume": "L",
    "molecules": "particles",
    "particles": "particles",
    "atoms": "particles",
}
_ASKED = re.compile(
    r"\b(?:how\s+(?:many|much)|what(?:\s+is)?(?:\s+the)?|find|calculate|determine)\s+"
    r"(?:the\s+)?"
    r"(?:(?P<unit>moles?|amount|grams?|mass|liters?|litres?|volume|molecules|particles|atoms)"
    rf"\s+(?:of\s+)?)?(?:(?P<species>{CHEMICAL_FORMULA})(?![A-Za-z0-9]))?",
    re.IGNORECASE,
)


def asked_quantity(text: str) -> AskedQuantity | None:
    """Read the requested quantity from the question head, not from the given amounts.

    "How many moles of H2O from 10 grams of H2" asks for moles; the word "grams"
    belongs to the given. ``None`` when no question head names anything.
    """
    for match in _ASKED.finditer(text):
        unit_word = match.group("unit")
        species = match.group("species")
        if unit_word is None and species is None:
            continue
        unit = _UNIT_WORDS[unit_word.lower()] if unit_word else None
        return AskedQuantity(unit, species)
    return None


def _target(text: str, equation: str) -> str | None:
    """The product the question asks about, or None when it asks about anything else."""
    balanced = balance_equation(equation)
    if not balanced.balanced:
        return None
    asked = asked_quantity(text)
    if asked is not None and asked.species is not None:
        # Asking for a reactant ("moles of O2 needed") or a species that is not in
        # the equation is not a product yield, so it is not verified as one.
        return asked.species if asked.species in balanced.products else None
    outside = EQUATION_RE.sub(" ", text)
    mentioned = [
        product
        for product in balanced.products
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(product)}(?![A-Za-z0-9])", outside)
    ]
    if len(mentioned) == 1:
        return mentioned[0]
    if len(balanced.products) == 1:
        return next(iter(balanced.products))
    return None


def _find_unit(text: str) -> str | None:
    """Unit of the requested quantity; ``mol`` when only a species is named."""
    asked = asked_quantity(text)
    if asked is None:
        return None
    return asked.unit or "mol"


_ELEMENT_BY_NAME = {element.name.lower(): element.symbol for element in ELEMENTS}
_ELEMENT_BY_NAME.update({"aluminium": "Al", "caesium": "Cs", "sulphur": "S"})


def _percents(text: str) -> dict[str, float]:
    """``40% C`` or ``40% carbon`` by element. A word that is no element is skipped."""
    found: dict[str, float] = {}
    for match in re.finditer(rf"({_N})\s*%\s*([A-Za-z]+)(?![A-Za-z])", text):
        word = match.group(2)
        symbol = word if word in BY_SYMBOL else _ELEMENT_BY_NAME.get(word.lower())
        if symbol is not None:
            found[symbol] = float(match.group(1))
    return found


def _gram_amounts(text: str) -> dict[str, float]:
    return {
        match.group(2): float(match.group(1))
        for match in re.finditer(
            rf"({_N})\s*g(?:rams?)?(?:\s+of)?\s+({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
            text,
            re.IGNORECASE,
        )
    }


def _molar_formula(text: str) -> tuple[float, str] | None:
    match = re.search(rf"({_N})\s*M\s+({CHEMICAL_FORMULA})(?![A-Za-z0-9])", text)
    if match is None:
        return None
    return float(match.group(1)), match.group(2)


_PRESSURE_UNIT = r"(?:kPa|Pa|mmHg|torr|atm|bar)"
_VOLUME_UNIT = r"(?:mL|liters?|litres?|L)"
_TEMPERATURE_UNIT = r"(?:°\s*C|deg\s*C|celsius|(?-i:K)|(?-i:C))"
_CANONICAL_PRESSURE = {
    "kpa": "kPa",
    "pa": "Pa",
    "mmhg": "mmHg",
    "torr": "torr",
    "atm": "atm",
    "bar": "bar",
}


def _celsius(unit: str) -> bool:
    return unit.lower().replace(" ", "") in {"c", "°c", "degc", "celsius"}


def _gas_state(text: str, names: tuple[str, ...]) -> dict[str, float] | None:
    """``P1 = 760 mmHg`` style values in atm, L and K.

    ``None`` when a labelled value has no unit or an unsupported one: reading
    ``T1 = 25 °C`` as 25 K, or 760 mmHg as atm, would be a wrong verified answer.
    """
    found: dict[str, float] = {}
    for name in names:
        kind = name[0]
        unit_pattern = {"p": _PRESSURE_UNIT, "v": _VOLUME_UNIT, "t": _TEMPERATURE_UNIT}[kind]
        labelled = re.search(rf"\b{name}\s*=\s*({_N})", text, re.IGNORECASE)
        if labelled is None:
            continue
        match = re.compile(
            rf"\b{name}\s*=\s*({_N})\s*({unit_pattern})(?![A-Za-z])", re.IGNORECASE
        ).search(text)
        if match is None:
            return None
        value, unit = float(match.group(1)), match.group(2)
        if kind == "p":
            found[name] = to_atm(value, unit)
        elif kind == "v":
            found[name] = to_liters(value, unit)
        else:
            found[name] = to_kelvin(value, "celsius" if _celsius(unit) else "kelvin")
    return found


def _partial_pressures(text: str) -> tuple[dict[str, float], str] | None:
    """``P(N2) = 600 mmHg`` values with one shared unit (else all converted to atm)."""
    rows = [
        (match.group(1), float(match.group(2)), match.group(3))
        for match in re.finditer(
            rf"P\(({CHEMICAL_FORMULA})\)\s*=\s*({_N})\s*({_PRESSURE_UNIT})(?![A-Za-z])",
            text,
            re.IGNORECASE,
        )
    ]
    labelled = len(re.findall(rf"P\(({CHEMICAL_FORMULA})\)\s*=\s*{_N}", text))
    if not rows or len(rows) != labelled:
        return None
    units = {_CANONICAL_PRESSURE[unit.lower()] for _species, _value, unit in rows}
    if len(units) == 1:
        return {species: value for species, value, _unit in rows}, units.pop()
    return {species: to_atm(value, unit) for species, value, unit in rows}, "atm"


def _pressure_species(text: str, equation: str) -> dict[str, float]:
    """Partial pressures of the equation's gases in atm; empty when a unit is missing."""
    partials = _partial_pressures(text)
    if partials is None:
        return {}
    raw = {species: to_atm(value, partials[1]) for species, value in partials[0].items()}
    balanced = balance_equation(equation)
    if not balanced.balanced:
        return raw
    mapped: dict[str, float] = {}
    for species in (*balanced.reactants, *balanced.products):
        if not counts_in_mass_action(species):
            continue
        if species in raw:
            mapped[species] = raw[species]
            continue
        bare = species[: species.rfind("(")] if "(" in species else species
        if bare in raw:
            mapped[species] = raw[bare]
    return mapped

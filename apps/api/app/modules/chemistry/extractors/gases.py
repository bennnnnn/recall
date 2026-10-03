"""Gases: Dalton's law, partial pressures, a gas over water, and Graham's law."""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.extractors.parsing import (
    _CANONICAL_PRESSURE,
    _N,
    _PRESSURE_UNIT,
    _partial_pressures,
    _search,
)
from app.modules.chemistry.quantity import to_atm
from app.modules.chemistry.species_facts import (
    NAMED_COMPOUNDS,
    formula_spans,
    is_formula,
)
from app.modules.chemistry.stoichiometry import molar_mass

_PRESSURE = re.compile(rf"({_N})\s*({_PRESSURE_UNIT})(?![A-Za-z])", re.IGNORECASE)


_LISTED_PARTIALS = re.compile(r"\bpartial\s+pressures\b", re.IGNORECASE)


def _listed_partials(text: str) -> tuple[dict[str, float], str] | None:
    """ "The partial pressures are 0.3 atm, 0.5 atm and 0.2 atm": every pressure the question
    states is one gas's, numbered in order. A stated total would be a different question."""
    if not re.search(r"\btotal\s+pressure\b", text, re.IGNORECASE):
        return None
    rows = [(float(match.group(1)), match.group(2)) for match in _PRESSURE.finditer(text)]
    if len(rows) < 2 or re.search(rf"\btotal\s+pressure\s+(?:=|is|of)\s*{_N}", text, re.I):
        return None
    units = {_CANONICAL_PRESSURE[unit.lower()] for _value, unit in rows}
    if len(units) == 1:
        unit = units.pop()
        return {str(index): value for index, (value, _) in enumerate(rows, 1)}, unit
    return {str(index): to_atm(value, unit) for index, (value, unit) in enumerate(rows, 1)}, "atm"


def _extract_gas_laws(text: str) -> ChemistryIntent | None:
    # Boyle, Charles and the combined and ideal gas laws are physics' (physics/catalog/gas_laws.py),
    # answered in L and atm when the question is written in them.
    if _LISTED_PARTIALS.search(text) and not re.search(r"\bP\(", text):
        listed = _listed_partials(text)
        if listed is not None:
            return ChemistryIntent(
                kind="gases",
                chemistry_op="dalton",
                species=listed[0],
                units={"pressure": listed[1]},
            )
    if re.search(r"\bDalton\b", text, re.IGNORECASE):
        partials = _partial_pressures(text)
        if partials is not None and len(partials[0]) >= 2:
            return ChemistryIntent(
                kind="gases",
                chemistry_op="dalton",
                species=partials[0],
                units={"pressure": partials[1]},
            )
        return None
    if re.search(r"\bpartial pressure\b", text, re.IGNORECASE):
        fraction = _search(rf"mole fraction\s*=\s*({_N})", text)
        total = re.search(
            rf"total pressure\s*=\s*({_N})\s*({_PRESSURE_UNIT})(?![A-Za-z])", text, re.IGNORECASE
        )
        if fraction is not None and total is not None:
            return ChemistryIntent(
                kind="gases",
                chemistry_op="partial_pressure",
                params={"mole_fraction": fraction, "total_pressure": float(total.group(1))},
                units={"pressure": _CANONICAL_PRESSURE[total.group(2).lower()]},
            )
    if re.search(r"\bover water\b", text, re.IGNORECASE):
        wet = _search(rf"total pressure\s*=\s*({_N})\s*(mmHg|atm|torr|kPa|bar)", text)
        unit = re.search(r"total pressure\s*=\s*" + _N + r"\s*(mmHg|atm|torr|kPa|bar)", text)
        temperature = _search(rf"({_N})\s*(?:°\s*)?C\b", text)
        if wet is not None and temperature is not None and unit is not None:
            return ChemistryIntent(
                kind="gases",
                chemistry_op="gas_over_water",
                params={"total_pressure": wet, "temperature_c": temperature},
                units={"pressure": unit.group(1)},
            )
    return None


# Gases a Graham question names in words, as the molecules that effuse.
_GAS_NAMES: dict[str, str] = {
    "hydrogen": "H2",
    "oxygen": "O2",
    "nitrogen": "N2",
    "chlorine": "Cl2",
    "fluorine": "F2",
    "helium": "He",
    "neon": "Ne",
    "argon": "Ar",
    "krypton": "Kr",
    "xenon": "Xe",
    "radon": "Rn",
}


_NOBLE = frozenset({"He", "Ne", "Ar", "Kr", "Xe", "Rn"})


_EFFUSION = re.compile(r"\b(?:effus\w*|diffus\w*|graham'?s?\s+law)\b", re.IGNORECASE)


_RATE_ASK = re.compile(
    r"\b(?:rates?|faster|slower|how\s+many\s+times|compare|comparison|ratio)\b", re.IGNORECASE
)


# A rate "slower" than another is the other's ratio to it; a time ratio is not a rate ratio.
_SLOWER = re.compile(r"\bslower\b", re.IGNORECASE)


_FASTER = re.compile(r"\bfaster\b", re.IGNORECASE)


_TIME_ASK = re.compile(r"\b(?:longer|time|takes?|took|how\s+long)\b", re.IGNORECASE)


_GAS_WORDS = "|".join(sorted((*_GAS_NAMES, *NAMED_COMPOUNDS), key=len, reverse=True))


_GAS_TOKEN = re.compile(
    r"(?<![A-Za-z0-9])(?P<formula>(?-i:[A-Z][A-Za-z0-9()]*))(?![A-Za-z0-9(])"
    rf"|\b(?P<name>{_GAS_WORDS})\b",
    re.IGNORECASE,
)


def _gases(text: str) -> list[str]:
    """The gases a question names, as formulas, in the order it names them."""
    gases: list[str] = []
    for match in _GAS_TOKEN.finditer(text):
        token = match.group("formula")
        if token is not None:
            gas = token if is_formula(token) or token in _NOBLE else None
        else:
            name = match.group("name").lower()
            gas = _GAS_NAMES.get(name) or NAMED_COMPOUNDS.get(name)
        if gas is not None and gas not in gases:
            gases.append(gas)
    return gases


def _states_a_number(text: str) -> bool:
    """A digit outside the formulas: a rate, a time or a mass the reader does not take."""
    kept = list(text)
    for start, end in formula_spans(text):
        kept[start:end] = " " * (end - start)
    return re.search(r"\d", "".join(kept)) is not None


def _extract_graham(text: str) -> ChemistryIntent | None:
    """ "Compare the rates of effusion of H2 and O2": rate(H2) / rate(O2) = √(M(O2) / M(H2)).

    "How many times slower does O2 effuse than H2?" asks rate(H2) / rate(O2), so a "slower"
    question swaps the gases. A time asked, or both directions asked, declines.
    """
    if not _EFFUSION.search(text) or not _RATE_ASK.search(text) or _states_a_number(text):
        return None
    slower = _SLOWER.search(text) is not None
    if _TIME_ASK.search(text) or (slower and _FASTER.search(text)):
        return None
    gases = _gases(text)
    if len(gases) != 2:
        return None
    first, second = reversed(gases) if slower else gases
    return ChemistryIntent(
        kind="gases",
        chemistry_op="graham_ratio",
        formula=first,
        target=second,
        params={"molar_mass_a": molar_mass(first), "molar_mass_b": molar_mass(second)},
    )

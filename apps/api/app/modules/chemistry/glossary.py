# ruff: noqa: RUF001 -- symbols and units are read as written: ₐ, °, ⁻¹.
"""What a chemistry given stands for, for the line that closes **Given** (``where_line``).

A worked reply lists its givens as symbols (``m = 36 g``), then names them, as physics'
do: "where m = mass, M(H₂O) = molar mass". A letter means different things across
laws (``m`` is a mass in grams and a molality in mol/kg, ``M`` a molar mass and a
molarity), so a meaning is read from the symbol and the unit it is given in together; a
symbol with no entry for its unit is left unnamed, never guessed.
"""

from __future__ import annotations

import re

_MASS = ("g", "kg", "mg", "µg")
_VOLUME = ("L", "mL", "µL", "dL")
_CONCENTRATION = ("mol/L", "M")
_PRESSURE = ("atm", "kPa", "Pa", "mmHg", "torr", "Torr", "bar")
_TEMPERATURE = ("K", "°C")
_TIME = ("s", "min", "h")
_ENERGY = ("J", "kJ", "J/mol", "kJ/mol")
_ANY = None

# (symbol, units it is given in, meaning); the first match wins.
_MEANINGS: tuple[tuple[str, tuple[str, ...] | None, str], ...] = (
    ("n", ("mol",), "amount"),
    ("m", _MASS, "mass"),
    ("m", ("mol/kg",), "molality"),
    ("b", ("mol/kg",), "molality"),
    ("b", ("cm",), "path length"),
    ("M", ("g/mol",), "molar mass"),
    ("M", _CONCENTRATION, "molarity"),
    ("c", _CONCENTRATION, "concentration"),
    ("C", _CONCENTRATION, "concentration"),
    ("V", _VOLUME, "volume"),
    ("T", _TEMPERATURE, "temperature"),
    ("ΔT", _TEMPERATURE, "temperature change"),
    ("P", _PRESSURE, "pressure"),
    ("t", _TIME, "time"),
    ("k", ("s⁻¹",), "rate constant"),
    ("N", ("particles", "molecules", "atoms"), "number of particles"),
    ("Nₐ", ("mol⁻¹",), "Avogadro constant"),
    ("I", ("A",), "current"),
    ("ΔH", _ENERGY, "enthalpy change"),
    ("ΔS", ("J/(mol·K)", "J/K"), "entropy change"),
    ("ΔG", _ENERGY, "Gibbs energy change"),
    ("Eₐ", _ENERGY, "activation energy"),
    ("Ea", _ENERGY, "activation energy"),
    ("A", ("s⁻¹",), "frequency factor"),
    ("ε", ("L/(mol·cm)",), "molar absorptivity"),
    ("Ka", _ANY, "acid dissociation constant"),
    ("Kb", ("°C·kg/mol",), "boiling-point constant"),
    ("Kb", _ANY, "base dissociation constant"),
    ("Kf", ("°C·kg/mol",), "freezing-point constant"),
    ("Ksp", _ANY, "solubility product"),
)
# "M(H2O) = 18.015 g/mol": the symbol, what it is of, the unit after the first number.
_GIVEN = re.compile(
    r"^(?P<symbol>[^\s=()]+?)(?P<index>\d*)(?:\((?P<of>[^()]+(?:\([a-z]+\))?)\))?\s*=\s*"
    r"-?\d[\d.]*(?:\s*×\s*10\^-?\d+)?\s*(?P<unit>\S*)"
)


def given_meaning(row: str) -> str | None:
    """What the given ``row`` names (``n(H2) = 4 mol`` → "amount"), or None. What it is of
    is on the symbol already (``n(H₂)``)."""
    match = _GIVEN.match(row.strip())
    if match is None:
        return None
    symbol, unit = match.group("symbol"), match.group("unit")
    return next(
        (
            said
            for named, units, said in _MEANINGS
            if named == symbol and (units is None or unit in units)
        ),
        None,
    )

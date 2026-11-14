"""A formula typed in lowercase, read as the one formula it can be.

"co2" is CO2: cobalt is never written Co2, and a school formula's elements are the first six
periods and the common heavy metals. A token with a digit is read when exactly one of its
readings is a school substance (``lowercase_formula``). One with no digit is a word as often as a
formula, so it is read only where an amount names its substance ("0.01 M hcl",
``input_text``), when it has one reading in any element symbols and the tables name that
substance (``lowercase_substance``): "hcl" is HCl and "naoh" NaOH, while "co" (Co or CO), "hf"
(HF or hafnium) and a word ("gas" is GaS) stay as written.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from app.modules.chemistry.elements import BY_SYMBOL, DIATOMIC_ELEMENTS
from app.modules.chemistry.formula import parse_formula
from app.modules.chemistry.species_facts import KNOWN_SUBSTANCES

# Elements a school formula writes: the first six periods up to barium, and the common heavy
# metals. A lowercase reading through any other ("Nh3", "CUSO4" with uranium) is not meant.
_LAST_SCHOOL_NUMBER = 56
_SCHOOL_HEAVY_METALS = frozenset({"W", "Pt", "Au", "Hg", "Pb"})
# Elements that stand alone as molecules: "o2", "o3", "p4", "s8".
_MOLECULES = frozenset({*(f"{symbol}2" for symbol in DIATOMIC_ELEMENTS), "O3", "P4", "S8"})
# A school formula never writes a subscript 1: "h1n1" is a flu, not HN.
_SUBSCRIPT_ONE = re.compile(r"(?<!\d)1(?!\d)")
MAX_LOWERCASE = 12


def _school_symbol(symbol: str) -> bool:
    element = BY_SYMBOL.get(symbol)
    return element is not None and (
        element.number <= _LAST_SCHOOL_NUMBER or symbol in _SCHOOL_HEAVY_METALS
    )


def _readings(token: str, symbol: Callable[[str], bool] = _school_symbol) -> list[str]:
    """Every way to write a lowercase token in element symbols: "co2" is CO2 or Co2."""
    readings: list[str] = []

    def walk(index: int, written: str) -> None:
        if index == len(token):
            readings.append(written)
            return
        char = token[index]
        if not char.isalpha():
            walk(index + 1, written + char)
            return
        pair = token[index : index + 2].capitalize()
        if len(pair) == 2 and pair[1].isalpha() and symbol(pair):
            walk(index + 2, written + pair)
        if symbol(char.upper()):
            walk(index + 1, written + char.upper())

    walk(0, "")
    return readings


def lowercase_formula(token: str) -> str | None:
    """ "co2" → "CO2": the one school substance a lowercase token with a digit can be."""
    if len(token) > MAX_LOWERCASE or not any(char.isdigit() for char in token):
        return None
    substances = {
        reading
        for reading in _readings(token)
        if not _SUBSCRIPT_ONE.search(reading)
        and (atoms := parse_formula(reading))
        and (len(atoms) >= 2 or reading in _MOLECULES)
    }
    return substances.pop() if len(substances) == 1 else None


def lowercase_substance(token: str) -> str | None:
    """A lowercase token where a formula is expected: "h2o" by ``lowercase_formula``, and one
    with no digit ("hcl") only as the one substance every element reading of it agrees on."""
    if len(token) > MAX_LOWERCASE:
        return None
    if any(char.isdigit() for char in token):
        return lowercase_formula(token)
    readings = _readings(token, BY_SYMBOL.__contains__)
    return readings[0] if len(readings) == 1 and readings[0] in KNOWN_SUBSTANCES else None

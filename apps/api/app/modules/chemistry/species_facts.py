"""What a chemistry question means by the substances it names.

A question says "water", "table salt" or "HCl"; a law needs a formula, and some laws need
what the substance does in water: a strong acid gives up all its protons, a weak acid needs
its Ka stated, and a salt splits into i ions. These are school facts, not looked up.
"""

from __future__ import annotations

import re
from functools import lru_cache

from app.modules.chemistry.elements import BY_SYMBOL, ELEMENTS
from app.modules.chemistry.formula import parse_formula

# Common names a school question uses for a compound.
NAMED_COMPOUNDS: dict[str, str] = {
    "water": "H2O",
    "table salt": "NaCl",
    "sodium chloride": "NaCl",
    "potassium chloride": "KCl",
    "calcium chloride": "CaCl2",
    "magnesium chloride": "MgCl2",
    "ammonia": "NH3",
    "methane": "CH4",
    "ethanol": "C2H5OH",
    "glucose": "C6H12O6",
    "sucrose": "C12H22O11",
    "sugar": "C12H22O11",
    "urea": "CO(NH2)2",
    "carbon dioxide": "CO2",
    "hydrochloric acid": "HCl",
    "hydrobromic acid": "HBr",
    "hydroiodic acid": "HI",
    "nitric acid": "HNO3",
    "perchloric acid": "HClO4",
    "sulfuric acid": "H2SO4",
    "sulphuric acid": "H2SO4",
    "acetic acid": "CH3COOH",
    "ethanoic acid": "CH3COOH",
    "formic acid": "HCOOH",
    "hydrofluoric acid": "HF",
    "nitrous acid": "HNO2",
    "hydrocyanic acid": "HCN",
    "sodium hydroxide": "NaOH",
    "potassium hydroxide": "KOH",
    "lithium hydroxide": "LiOH",
    "calcium hydroxide": "Ca(OH)2",
    "barium hydroxide": "Ba(OH)2",
    "sodium acetate": "CH3COONa",
    "potassium acetate": "CH3COOK",
}

# Protons a strong acid gives up, and hydroxides a strong base releases, per formula unit.
STRONG_ACIDS: dict[str, int] = {
    "HCl": 1,
    "HBr": 1,
    "HI": 1,
    "HNO3": 1,
    "HClO4": 1,
    "HClO3": 1,
}
STRONG_BASES: dict[str, int] = {
    "LiOH": 1,
    "NaOH": 1,
    "KOH": 1,
    "RbOH": 1,
    "CsOH": 1,
    "Ca(OH)2": 2,
    "Sr(OH)2": 2,
    "Ba(OH)2": 2,
}
# Weak electrolytes: a pH needs the stated Ka or Kb.
WEAK_ACIDS = frozenset({"CH3COOH", "HCOOH", "HF", "HNO2", "HCN", "HClO", "C6H5COOH"})
WEAK_BASES = frozenset({"NH3", "CH3NH2", "C5H5N", "C6H5NH2"})
# The conjugate base of a weak acid, as the salt a buffer is made with.
CONJUGATE_SALTS = frozenset({"CH3COONa", "CH3COOK", "HCOONa", "NaF", "NaNO2", "NaCN"})
# Particles one dissolved formula unit gives, for an ideal colligative property.
VAN_T_HOFF: dict[str, int] = {
    "C6H12O6": 1,
    "C12H22O11": 1,
    "CO(NH2)2": 1,
    "C2H5OH": 1,
    "NaCl": 2,
    "KCl": 2,
    "KBr": 2,
    "NaBr": 2,
    "KNO3": 2,
    "NaNO3": 2,
    "CaCl2": 3,
    "MgCl2": 3,
    "Na2SO4": 3,
    "K2SO4": 3,
    "AlCl3": 4,
    "FeCl3": 4,
}

# An element named in words: "zinc", "copper" (and the American aluminum).
ELEMENT_NAMES: dict[str, str] = {
    **{element.name.lower(): element.symbol for element in ELEMENTS},
    "aluminum": "Al",
    "sulphur": "S",
}

# A formula as a question writes it: capitals, digits and brackets, nothing glued on.
_FORMULA_TOKEN = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Za-z0-9()]*)(?![A-Za-z0-9(])")
# An ion written with its charge: "Cu2+", "Fe3+".
_ION = re.compile(r"(?<![A-Za-z0-9])([A-Z][a-z]?)(\d?)\+")


@lru_cache(maxsize=1)
def _name_pattern() -> re.Pattern[str]:
    names = sorted(NAMED_COMPOUNDS, key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(name) for name in names) + r")\b", re.IGNORECASE)


def is_formula(token: str) -> bool:
    """A compound formula: two or more real elements ("HCl", "NH3"), never "Find" or "Kf"."""
    atoms = parse_formula(token)
    return len(atoms) >= 2 and all(symbol in BY_SYMBOL for symbol in atoms)


def named_species(text: str) -> tuple[str, ...]:
    """The compounds a question names, as formulas, in the order it names them."""
    found: list[tuple[int, str]] = []
    for match in _name_pattern().finditer(text):
        found.append((match.start(), NAMED_COMPOUNDS[match.group(1).lower()]))
    for match in _FORMULA_TOKEN.finditer(text):
        if is_formula(match.group(1)):
            found.append((match.start(), match.group(1)))
    ordered: list[str] = []
    for _, formula in sorted(found):
        if formula not in ordered:
            ordered.append(formula)
    return tuple(ordered)


def named_elements(text: str) -> tuple[str, ...]:
    """The elements a question names in words ("zinc and copper"), as symbols, in order."""
    words = re.findall(r"[a-z]+", text.lower())
    symbols: list[str] = []
    for word in words:
        symbol = ELEMENT_NAMES.get(word)
        if symbol is not None and symbol not in symbols:
            symbols.append(symbol)
    return tuple(symbols)


def ion_charge(text: str, symbol: str) -> int | None:
    """The charge of the named ion of one element ("from Cu2+" is 2), if the question writes it."""
    for match in _ION.finditer(text):
        if match.group(1) == symbol:
            return int(match.group(2) or 1)
    return None


def formula_spans(text: str) -> list[tuple[int, int]]:
    """Where formulas and charged ions are written, so their digits are not read as numbers."""
    spans = [match.span(1) for match in _FORMULA_TOKEN.finditer(text) if is_formula(match.group(1))]
    spans.extend(match.span() for match in _ION.finditer(text) if match.group(1) in BY_SYMBOL)
    return sorted(spans)

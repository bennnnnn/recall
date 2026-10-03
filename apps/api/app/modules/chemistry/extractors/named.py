# ruff: noqa: RUF002 -- docstrings write the formulas with a multiplication sign.
"""Readers for laws whose inputs are the substances a question names, not values it states.

Graham's law needs two gases, the mass of an element needs the element and its compound,
an average atomic mass needs the isotopes, and an electron configuration needs the element.
Their numbers come from the element and isotope tables; anything else stated declines.
"""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.elements import BY_SYMBOL
from app.modules.chemistry.extractors.parsing import _N
from app.modules.chemistry.formula import parse_formula
from app.modules.chemistry.isotopes import ISOTOPE_MASSES
from app.modules.chemistry.request import CHEMICAL_FORMULA
from app.modules.chemistry.species_facts import (
    ELEMENT_NAMES,
    NAMED_COMPOUNDS,
    formula_spans,
    is_formula,
)
from app.modules.chemistry.stoichiometry import molar_mass

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


_SPECIES = rf"(?:{'|'.join(re.escape(name) for name in NAMED_COMPOUNDS)}|{CHEMICAL_FORMULA})"
_ELEMENT_IN = re.compile(
    r"\b(?:how\s+many\s+grams\s+of|(?:what|find|calculate|determine)\s+(?:is\s+)?the\s+mass\s+of)"
    r"\s+(?P<element>[A-Za-z]+)\s+(?:(?:is|are)\s+)?(?:there\s+)?(?:present\s+|contained\s+)?"
    rf"in\s+(?:an?\s+)?(?P<mass>{_N})\s*(?:g|grams?)\s+(?:sample\s+)?of\s+(?:the\s+)?"
    rf"(?P<species>{_SPECIES})(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def _element(token: str) -> str | None:
    """An element named by symbol ("O", case as written) or in words ("oxygen")."""
    if token in BY_SYMBOL:
        return token
    return ELEMENT_NAMES.get(token.lower())


def _extract_element_mass(text: str) -> ChemistryIntent | None:
    """ "How many grams of oxygen are in 10 g of H2O?": m(O) = m × nA(O) / M(H2O)."""
    match = _ELEMENT_IN.search(text)
    if match is None:
        return None
    element = _element(match.group("element"))
    token = match.group("species")
    formula = NAMED_COMPOUNDS.get(token.lower()) or (token if is_formula(token) else None)
    if element is None or formula is None:
        return None
    count = parse_formula(formula).get(element, 0)
    if count == 0:
        return None
    return ChemistryIntent(
        kind="amounts",
        chemistry_op="element_mass",
        formula=formula,
        target=element,
        params={
            "sample_mass": float(match.group("mass")),
            "count": float(count),
            "atomic_mass": BY_SYMBOL[element].mass,
            "molar_mass": molar_mass(formula),
        },
    )


_AVERAGE_ASK = re.compile(
    r"\b(?:(?:average|relative|mean)\s+)?atomic\s+(?:mass|weight)\b", re.IGNORECASE
)
# "35Cl", "Cl-35" or "chlorine-35".
_ISOTOPE = re.compile(
    r"(?<![A-Za-z0-9.])(?P<before>\d{1,3})(?P<symbol>[A-Z][a-z]?)(?![a-z])"
    r"|\b(?P<element>[A-Z][a-z]?|[A-Za-z]{3,})-(?P<after>\d{1,3})\b"
)
_ABUNDANCE = re.compile(rf"({_N})\s*%")
_STATED_MASS = re.compile(rf"({_N})\s*(?:u|amu|Da)\b")


def _isotopes(text: str) -> list[tuple[str, int, int, int]]:
    """Each isotope written in the text: (symbol, mass number, start, end)."""
    found: list[tuple[str, int, int, int]] = []
    for match in _ISOTOPE.finditer(text):
        token = match.group("symbol") or match.group("element")
        symbol = token if token in BY_SYMBOL else ELEMENT_NAMES.get(token.lower())
        number = int(match.group("before") or match.group("after"))
        if symbol is None or number < BY_SYMBOL[symbol].number:
            return []
        found.append((symbol, number, match.start(), match.end()))
    return found


def _one(pattern: re.Pattern[str], segment: str) -> float | None:
    values = [float(match.group(1)) for match in pattern.finditer(segment)]
    return values[0] if len(values) == 1 else None


def _extract_average_atomic_mass(text: str) -> ChemistryIntent | None:
    """Isotopes with their abundances: Σ mass × abundance / 100.

    Each isotope's abundance (and its mass, if stated) is written after it, up to the next
    isotope: "35Cl (34.969 u, 75.77%) and 37Cl (36.966 u, 24.23%)". An unstated mass comes
    from the isotope table.
    """
    if not _AVERAGE_ASK.search(text):
        return None
    isotopes = _isotopes(text)
    if len(isotopes) < 2 or len({symbol for symbol, *_ in isotopes}) != 1:
        return None
    ends = [start for _, _, start, _ in isotopes[1:]] + [len(text)]
    abundances: dict[str, float] = {}
    masses: dict[str, float] = {}
    for (symbol, number, _start, end), stop in zip(isotopes, ends, strict=True):
        segment = text[end:stop]
        abundance = _one(_ABUNDANCE, segment)
        mass = _one(_STATED_MASS, segment)
        if mass is None:
            mass = ISOTOPE_MASSES.get((symbol, number))
        label = f"{symbol}-{number}"
        if abundance is None or mass is None or label in abundances:
            return None
        abundances[label] = abundance
        masses[label] = mass
    if abs(sum(abundances.values()) - 100) > 0.1:
        return None
    return ChemistryIntent(
        kind="amounts",
        chemistry_op="average_atomic_mass",
        target=isotopes[0][0],
        species=abundances,
        params=masses,
    )


_CONFIGURATION = re.compile(
    r"\belectron(?:ic)?\s+configuration\s+(?:of|for)\s+(?:an?\s+|the\s+)?(?:neutral\s+)?"
    r"(?:element\s+|atom\s+of\s+)?(?P<element>[A-Za-z]+)(?:\s+atom)?(?![A-Za-z0-9+\-^])",
    re.IGNORECASE,
)


def _extract_electron_configuration(text: str) -> ChemistryIntent | None:
    """ "What is the electron configuration of Fe?" from the element table (neutral atom)."""
    match = _CONFIGURATION.search(text)
    if match is None:
        return None
    element = _element(match.group("element"))
    if element is None:
        return None
    return ChemistryIntent(kind="structure", chemistry_op="electron_configuration", target=element)

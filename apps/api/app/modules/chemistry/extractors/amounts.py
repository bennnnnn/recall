# ruff: noqa: RUF002
"""Amounts: moles, mass and particles, formulas from composition, an element's share."""

from __future__ import annotations

import re

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.elements import BY_SYMBOL, ELEMENTS
from app.modules.chemistry.equations import written_is_balanced
from app.modules.chemistry.extractors.parsing import (
    _N,
    _element,
    _equation,
    _search,
)
from app.modules.chemistry.formula import parse_formula
from app.modules.chemistry.isotopes import ISOTOPE_MASSES
from app.modules.chemistry.request import CHEMICAL_FORMULA, EQUATION_RE
from app.modules.chemistry.species import parse_species
from app.modules.chemistry.species_facts import (
    ELEMENT_NAMES,
    NAMED_COMPOUNDS,
    is_formula,
)
from app.modules.chemistry.stoichiometry import molar_mass


def _bare_formula(label: str) -> str | None:
    """The formula without a phase, so ``CaO`` names the product ``CaO(s)``."""
    species = parse_species(label, coefficient_already_removed=True)
    if species is None or species.formula == label:
        return None
    return species.formula


def _named_outside(text: str, label: str) -> bool:
    outside = EQUATION_RE.sub(" ", text)
    tokens = [label]
    bare = _bare_formula(label)
    if bare is not None:
        tokens.append(bare)
    pattern = r"(?<![A-Za-z0-9]){}(?![A-Za-z0-9])"
    return any(re.search(pattern.format(re.escape(token)), outside) for token in tokens)


def _desired_product(text: str, products: dict[str, int]) -> str | None:
    """The one product the question names, or the only product when it names none.

    The returned label is the one written in the equation, phase included.
    """
    mentioned = [product for product in products if _named_outside(text, product)]
    if len(mentioned) == 1:
        return mentioned[0]
    if len(products) == 1:
        return next(iter(products))
    return None


def _extract_atom_economy(text: str) -> ChemistryIntent | None:
    if re.search(r"\batom economy\b", text, re.IGNORECASE) is None:
        return None
    equation = _equation(text)
    if equation is None or not written_is_balanced(equation):
        return None
    from app.modules.chemistry.species import parse_reaction

    reaction = parse_reaction(equation)
    if reaction is None:
        return None
    products = {term.species.label: term.coefficient for term in reaction.products}
    target = _desired_product(text, products)
    if target is None:
        return None
    return ChemistryIntent(
        kind="amounts", chemistry_op="atom_economy", equation=equation, target=target
    )


def _extract_amounts(text: str) -> ChemistryIntent | None:
    economy = _extract_atom_economy(text)
    if economy is not None:
        return economy
    mass_formula = re.search(
        rf"(?:molar\s+mass|molecular\s+weight)\s+(?:of\s+)?({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if mass_formula:
        return ChemistryIntent(
            kind="amounts", chemistry_op="molar_mass", formula=mass_formula.group(1)
        )

    percent_composition = re.search(
        rf"percent(?:age)?\s+(?:composition|by mass)\s+(?:of\s+)?"
        rf"([A-Z][a-z]?|[a-z]+)\s+(?:in|of)\s+({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    # The element may be named in words: "the percent composition of carbon in CO2".
    element = None if percent_composition is None else percent_composition.group(1).lower()
    symbol = ELEMENT_NAMES.get(element or "", (element or "").capitalize())
    if percent_composition and symbol in BY_SYMBOL:
        return ChemistryIntent(
            kind="amounts",
            chemistry_op="percent_composition",
            target=symbol,
            formula=percent_composition.group(2),
        )

    if re.search(r"\bpercent yield\b", text, re.IGNORECASE):
        actual = _search(rf"actual(?:\s+yield)?\s*(?:=|of)?\s*({_N})\s*g", text)
        theoretical = _search(rf"theoretical(?:\s+yield)?\s*(?:=|of)?\s*({_N})\s*g", text)
        if actual is not None and theoretical is not None:
            return ChemistryIntent(
                kind="amounts",
                chemistry_op="percent_yield",
                params={"actual": actual, "theoretical": theoretical},
            )

    mass_to_moles = re.search(
        rf"(?:how many|calculate|find|determine)?\s*(?:the\s+)?moles?\s+"
        rf"(?:are\s+)?(?:in|from|of)?\s*({_N})\s*g(?:rams?)?\s+(?:of\s+)?"
        rf"({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if mass_to_moles:
        return ChemistryIntent(
            kind="amounts",
            chemistry_op="mass_to_moles",
            params={"mass": float(mass_to_moles.group(1))},
            units={"mass": "g"},
            formula=mass_to_moles.group(2),
        )

    moles_to_mass = re.search(
        rf"(?:mass|grams?)\s+(?:of\s+)?({_N})\s*mol(?:e|es)?\s+(?:of\s+)?({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if moles_to_mass:
        return ChemistryIntent(
            kind="amounts",
            chemistry_op="moles_to_mass",
            params={"moles": float(moles_to_mass.group(1))},
            units={"moles": "mol"},
            formula=moles_to_mass.group(2),
        )

    moles_to_particles = re.search(
        rf"(?:how many|calculate|find)?\s*(?P<noun>molecules|particles|atoms|formula units)\s+"
        rf"(?:are\s+)?(?:in|from)?\s*(?P<moles>{_N})\s*mol(?:e|es)?\s+(?:of\s+)?"
        rf"(?P<formula>{CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if moles_to_particles:
        return ChemistryIntent(
            kind="amounts",
            chemistry_op="moles_to_particles",
            params={"moles": float(moles_to_particles.group("moles"))},
            units={"particle": moles_to_particles.group("noun").lower()},
            formula=moles_to_particles.group("formula"),
        )

    particles_to_moles = re.search(
        rf"(?:how many|calculate|find)?\s*moles?\s+(?:are\s+)?(?:in|from)?\s*"
        rf"({_N})\s*(?P<noun>molecules|particles|atoms|formula units)\s+(?:of\s+)?"
        rf"({CHEMICAL_FORMULA})(?![A-Za-z0-9])",
        text,
        re.IGNORECASE,
    )
    if particles_to_moles:
        return ChemistryIntent(
            kind="amounts",
            chemistry_op="particles_to_moles",
            params={"particles": float(particles_to_moles.group(1))},
            units={"particle": particles_to_moles.group("noun").lower()},
            formula=particles_to_moles.group(3),
        )
    return None


def _extract_empirical(text: str) -> ChemistryIntent | None:
    percents = _percents(text)
    if len(percents) < 2:
        return None
    if re.search(r"\bmolecular formula\b", text, re.IGNORECASE):
        molar = _search(rf"(?:molar mass|M)\s*=\s*({_N})", text)
        if molar is None:
            return None
        return ChemistryIntent(
            kind="amounts",
            chemistry_op="molecular_formula",
            params={"molar_mass": molar},
            species=percents,
        )
    if re.search(r"\bempirical formula\b", text, re.IGNORECASE):
        return ChemistryIntent(kind="amounts", chemistry_op="empirical_formula", species=percents)
    return None


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


_SPECIES = rf"(?:{'|'.join(re.escape(name) for name in NAMED_COMPOUNDS)}|{CHEMICAL_FORMULA})"


_ELEMENT_IN = re.compile(
    r"\b(?:how\s+many\s+grams\s+of|(?:what|find|calculate|determine)\s+(?:is\s+)?the\s+mass\s+of)"
    r"\s+(?P<element>[A-Za-z]+)\s+(?:(?:is|are)\s+)?(?:there\s+)?(?:present\s+|contained\s+)?"
    rf"in\s+(?:an?\s+)?(?P<mass>{_N})\s*(?:g|grams?)\s+(?:sample\s+)?of\s+(?:the\s+)?"
    rf"(?P<species>{_SPECIES})(?![A-Za-z0-9])",
    re.IGNORECASE,
)


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

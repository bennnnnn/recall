"""Empirical and molecular formulas from percent composition."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.elements import BY_SYMBOL
from app.modules.chemistry.formula import hill_formula
from app.modules.chemistry.solvers.common_chem import (
    atomic_mass,
    inp,
    molar_mass_working,
    num,
    verified,
)
from app.modules.chemistry.solvers.types import ChemistryResult
from app.modules.chemistry.stoichiometry import (
    formula_atoms,
    molar_mass,
)
from app.services.solving import SolveServiceError


def _formula_from_counts(counts: dict[str, int]) -> str:
    return hill_formula(counts)


def _integer_ratio(ratios: dict[str, float]) -> dict[str, int] | None:
    for multiplier in range(1, 9):
        scaled = {element: ratio * multiplier for element, ratio in ratios.items()}
        if all(abs(value - round(value)) <= 0.1 for value in scaled.values()):
            return {element: round(value) for element, value in scaled.items()}
    return None


def _empirical_counts(percents: dict[str, float]) -> tuple[dict[str, int], list[str]]:
    """Integer atom ratio and the per-element working (grams → moles → ratio)."""
    if not percents or any(value <= 0 for value in percents.values()):
        raise SolveServiceError("percent composition must be positive")
    if abs(sum(percents.values()) - 100) > 1.5:
        raise SolveServiceError("percentages must add to about 100")
    masses: dict[str, float] = {}
    moles: dict[str, float] = {}
    for element, percent in percents.items():
        info = BY_SYMBOL.get(element)
        if info is None:
            raise SolveServiceError(f"unknown element {element}")
        masses[element] = info.mass
        moles[element] = percent / masses[element]
    smallest = min(moles.values())
    ratios = {element: value / smallest for element, value in moles.items()}
    counts = _integer_ratio(ratios)
    if counts is None:
        raise SolveServiceError("percentages do not form a simple integer ratio")
    working = [
        f"{element}: {inp(percents[element])} g / {atomic_mass(masses[element])} g/mol = "
        f"{num(moles[element])} mol; / {num(smallest)} = {num(ratios[element])}"
        f" -> {counts[element]}"
        for element in percents
    ]
    return counts, working


def solve_empirical(intent: ChemistryIntent) -> ChemistryResult:
    counts, working = _empirical_counts(dict(intent.species))
    formula = _formula_from_counts(counts)
    given = tuple(f"{element} = {inp(percent)}%" for element, percent in intent.species.items())
    return verified(
        "Verified empirical formula",
        (*given, "assume a 100 g sample, so each percent is grams"),
        "Empirical formula",
        *stated("empirical_formula"),
        working,
        formula,
        formula,
    )


def solve_molecular(intent: ChemistryIntent) -> ChemistryResult:
    molar = intent.params.get("molar_mass")
    if molar is None or molar <= 0:
        raise SolveServiceError("molecular molar mass must be positive")
    if intent.species:
        counts, working = _empirical_counts(dict(intent.species))
        given = [f"{element} = {inp(percent)}%" for element, percent in intent.species.items()]
    elif intent.formula and (stated_counts := formula_atoms(intent.formula)):
        # The empirical formula may be given outright: "the empirical formula is CH2O".
        counts, working = dict(stated_counts), []
        given = [f"empirical formula = {intent.formula}"]
    else:
        raise SolveServiceError("a molecular formula needs a composition or an empirical formula")
    empirical = _formula_from_counts(counts)
    empirical_mass = molar_mass(empirical)
    multiple = molar / empirical_mass
    factor = round(multiple)
    if factor < 1 or abs(multiple - factor) > 0.05:
        raise SolveServiceError("molar mass is not an integer multiple of the empirical mass")
    molecular_counts = {element: count * factor for element, count in counts.items()}
    formula = _formula_from_counts(molecular_counts)
    return verified(
        "Verified molecular formula",
        (*given, f"M = {inp(molar)} g/mol"),
        "Molecular formula",
        *stated("molecular_formula"),
        (
            *working,
            f"empirical formula = {empirical}, M = {molar_mass_working(empirical_mass)} g/mol",
            f"n = {inp(molar)} / {molar_mass_working(empirical_mass)} = {factor}",
            f"molecular formula = ({empirical}){factor} = {formula}",
        ),
        formula,
        formula,
    )

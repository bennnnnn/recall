"""Answers read from the element and isotope tables: averages and configurations."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.elements import BY_SYMBOL
from app.modules.chemistry.solvers.common_chem import inp, num, verified
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError

# Rounded abundances may miss 100% by a hundredth or so; more is a different question.
_ABUNDANCE_TOLERANCE = 0.1


def solve_average_atomic_mass(intent: ChemistryIntent) -> ChemistryResult:
    abundances = intent.species
    masses = intent.params
    if len(abundances) < 2 or set(abundances) != set(masses):
        raise SolveServiceError("an average atomic mass needs each isotope's mass and abundance")
    if any(value <= 0 for value in (*abundances.values(), *masses.values())):
        raise SolveServiceError("isotope masses and abundances must be positive")
    if abs(sum(abundances.values()) - 100) > _ABUNDANCE_TOLERANCE:
        raise SolveServiceError("isotope abundances must add up to 100%")
    average = sum(masses[label] * abundances[label] / 100 for label in abundances)
    symbol = intent.target or ""
    shown = f"{num(average)} u"
    terms = " + ".join(
        f"({inp(masses[label])} u)({inp(abundances[label] / 100)})" for label in abundances
    )
    return verified(
        "Verified average atomic mass",
        tuple(
            f"{label}: {inp(masses[label])} u, {inp(abundances[label])}%" for label in abundances
        ),
        "Average atomic mass",
        *stated("average_atomic_mass"),
        (f"A({symbol}) = {terms}",),
        f"A({symbol}) = {shown}",
        shown,
    )


def solve_electron_configuration(intent: ChemistryIntent) -> ChemistryResult:
    element = BY_SYMBOL.get(intent.target or "")
    if element is None:
        raise SolveServiceError("an electron configuration needs an element")
    return verified(
        "Verified electron configuration",
        (f"{element.name} ({element.symbol})", f"Z = {element.number}"),
        "Ground-state electron configuration of the neutral atom",
        *stated("electron_configuration"),
        (f"{element.number} electrons",),
        f"{element.symbol}: {element.configuration}",
        element.configuration,
        verbatim=True,
    )

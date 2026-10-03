"""Decay constant, exponential decay, activity, and nuclear equations."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.catalog import stated
from app.modules.chemistry.nuclear import balance_nuclear, conservation_lines, format_nuclear
from app.modules.chemistry.solvers.common_chem import (
    verified,
)
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import SolveServiceError


def solve_nuclear_equation(intent: ChemistryIntent) -> ChemistryResult:
    if not intent.equation:
        raise SolveServiceError("a nuclear equation is required")
    balanced = balance_nuclear(intent.equation)
    if not balanced.balanced:
        raise SolveServiceError(balanced.error or "nuclear equation does not balance")
    shown = format_nuclear(balanced)
    return verified(
        "Verified nuclear equation",
        (intent.equation,),
        "Balanced nuclear equation",
        *stated("nuclear_equation"),
        conservation_lines(balanced),
        shown,
        shown,
    )

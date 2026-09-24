"""Stable dispatcher for typed chemistry calculations."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.solvers.amounts import (
    solve_amount,
    solve_equation,
    solve_molar_mass,
    solve_percent_composition,
    solve_percent_yield,
    solve_stoichiometry,
)
from app.modules.chemistry.solvers.physical import (
    solve_electrochemistry,
    solve_equilibrium,
    solve_kinetics,
    solve_nuclear,
    solve_thermochemistry,
)
from app.modules.chemistry.solvers.solutions import (
    solve_acid_base,
    solve_beer_lambert,
    solve_gas,
    solve_solution,
)
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import MathServiceError


def solve_chemistry(intent: ChemistryIntent) -> ChemistryResult:
    """Dispatch a validated intent to its subject-grouped pure solver."""
    op = intent.chemistry_op
    if op == "balance":
        return solve_equation(intent)
    if op == "molar_mass":
        return solve_molar_mass(intent)
    if op in {"mass_to_moles", "moles_to_mass", "moles_to_particles", "particles_to_moles"}:
        return solve_amount(intent)
    if op == "percent_composition":
        return solve_percent_composition(intent)
    if op == "percent_yield":
        return solve_percent_yield(intent)
    if op in {"stoichiometry", "limiting_reagent"}:
        return solve_stoichiometry(intent)
    if op in {"molarity", "dilution", "molality", "mass_percent"}:
        return solve_solution(intent)
    if op in {"ph_from_h", "ph_from_poh", "h_from_ph", "poh_from_oh", "buffer_ph"}:
        return solve_acid_base(intent)
    if op == "ideal_gas":
        return solve_gas(intent)
    if op in {"heat", "gibbs"}:
        return solve_thermochemistry(intent)
    if op in {"equilibrium_constant", "reaction_quotient"}:
        return solve_equilibrium(intent)
    if op in {"first_order_half_life", "first_order_concentration", "arrhenius"}:
        return solve_kinetics(intent)
    if op in {"cell_gibbs", "nernst", "electrolysis_mass"}:
        return solve_electrochemistry(intent)
    if op == "radioactive_decay":
        return solve_nuclear(intent)
    if op == "beer_lambert":
        return solve_beer_lambert(intent)
    raise MathServiceError(f"unsupported chemistry operation: {op}")

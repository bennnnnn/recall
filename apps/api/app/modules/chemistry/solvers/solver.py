"""Stable dispatcher for typed chemistry calculations."""

from __future__ import annotations

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.solvers.acid import (
    solve_buffer_addition,
    solve_ka_kb,
    solve_polyprotic,
    solve_strong_acid,
    solve_strong_base,
    solve_weak_acid,
    solve_weak_base,
)
from app.modules.chemistry.solvers.amounts import (
    solve_amount,
    solve_equation,
    solve_molar_mass,
    solve_percent_composition,
    solve_percent_yield,
    solve_stoichiometry,
)
from app.modules.chemistry.solvers.amounts_extended import (
    solve_empirical,
    solve_gas_stoichiometry,
    solve_limiting_mass,
    solve_limiting_solution,
    solve_mass_stoichiometry,
    solve_molecular,
    solve_solution_stoichiometry,
)
from app.modules.chemistry.solvers.cells_ext import solve_cell_potential, solve_galvanic_cell
from app.modules.chemistry.solvers.equilibrium_ext import (
    solve_common_ion,
    solve_ice,
    solve_kc_kp,
    solve_kp,
    solve_ksp,
    solve_precipitation,
)
from app.modules.chemistry.solvers.gases_ext import (
    solve_boyle,
    solve_charles,
    solve_combined_gas,
    solve_dalton,
    solve_gas_over_water,
    solve_partial_pressure,
)
from app.modules.chemistry.solvers.identity import (
    solve_boiling,
    solve_calibration,
    solve_coordination,
    solve_formal_charge,
    solve_freezing,
    solve_functional_groups,
    solve_gravimetric,
    solve_isomers,
    solve_osmotic,
    solve_oxidation_state,
    solve_raoult,
    solve_standard_addition,
    solve_stereochemistry,
    solve_vsepr,
)
from app.modules.chemistry.solvers.kinetics_ext import (
    solve_arrhenius_two_point,
    solve_rate_law,
    solve_second_half_life,
    solve_second_order,
    solve_zero_half_life,
    solve_zero_order,
)
from app.modules.chemistry.solvers.nuclear_ext import (
    solve_decay_constant,
    solve_exponential_decay,
    solve_nuclear_activity,
    solve_nuclear_equation,
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
from app.modules.chemistry.solvers.thermo_ext import (
    solve_bond_enthalpy,
    solve_calorimetry,
    solve_formation,
    solve_hess,
)
from app.modules.chemistry.solvers.titration import solve_titration_strong, solve_titration_weak
from app.modules.chemistry.solvers.types import ChemistryResult
from app.services.solving import MathServiceError

_EXTENDED = {
    "empirical_formula": solve_empirical,
    "molecular_formula": solve_molecular,
    "mass_stoichiometry": solve_mass_stoichiometry,
    "solution_stoichiometry": solve_solution_stoichiometry,
    "gas_stoichiometry": solve_gas_stoichiometry,
    "limiting_mass": solve_limiting_mass,
    "limiting_solution": solve_limiting_solution,
    "strong_acid_ph": solve_strong_acid,
    "strong_base_ph": solve_strong_base,
    "weak_acid_ph": solve_weak_acid,
    "weak_base_ph": solve_weak_base,
    "ka_kb": solve_ka_kb,
    "titration_strong": solve_titration_strong,
    "titration_weak": solve_titration_weak,
    "buffer_addition": solve_buffer_addition,
    "polyprotic_ph": solve_polyprotic,
    "combined_gas": solve_combined_gas,
    "boyle": solve_boyle,
    "charles": solve_charles,
    "dalton": solve_dalton,
    "partial_pressure": solve_partial_pressure,
    "gas_over_water": solve_gas_over_water,
    "calorimetry": solve_calorimetry,
    "hess": solve_hess,
    "formation_enthalpy": solve_formation,
    "bond_enthalpy": solve_bond_enthalpy,
    "ksp": solve_ksp,
    "precipitation": solve_precipitation,
    "common_ion": solve_common_ion,
    "kp": solve_kp,
    "kc_kp": solve_kc_kp,
    "ice_equilibrium": solve_ice,
    "zero_order": solve_zero_order,
    "second_order": solve_second_order,
    "zero_order_half_life": solve_zero_half_life,
    "second_order_half_life": solve_second_half_life,
    "rate_law": solve_rate_law,
    "arrhenius_two_point": solve_arrhenius_two_point,
    "cell_potential": solve_cell_potential,
    "galvanic_cell": solve_galvanic_cell,
    "decay_constant": solve_decay_constant,
    "exponential_decay": solve_exponential_decay,
    "nuclear_activity": solve_nuclear_activity,
    "nuclear_equation": solve_nuclear_equation,
    "oxidation_state": solve_oxidation_state,
    "vsepr": solve_vsepr,
    "formal_charge": solve_formal_charge,
    "functional_groups": solve_functional_groups,
    "stereochemistry": solve_stereochemistry,
    "isomers": solve_isomers,
    "coordination_complex": solve_coordination,
    "boiling_elevation": solve_boiling,
    "freezing_depression": solve_freezing,
    "osmotic_pressure": solve_osmotic,
    "raoult": solve_raoult,
    "calibration": solve_calibration,
    "gravimetric": solve_gravimetric,
    "standard_addition": solve_standard_addition,
}


def solve_chemistry(intent: ChemistryIntent) -> ChemistryResult:
    """Dispatch a validated intent to its subject-grouped pure solver."""
    extended = _EXTENDED.get(intent.chemistry_op)
    if extended is not None:
        return extended(intent)
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

"""Structured chemistry I/O validated before a deterministic solve.

Chemistry used to extract numbers and immediately format prompt prose in one
large context module.  Keeping the requested operation and its inputs in a
Pydantic model gives the subject the same boundary Physics has: extractors do
not calculate, solvers do not guess what the user asked for, and presentation
does not parse equations back out of prose.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

ChemistryKind = Literal[
    "equations",
    "amounts",
    "stoichiometry",
    "solutions",
    "acid_base",
    "gases",
    "thermochemistry",
    "equilibrium",
    "kinetics",
    "electrochemistry",
    "nuclear",
    "spectroscopy",
    "structure",
    "organic",
    "inorganic",
    "analytical",
]

ChemistryOp = Literal[
    "balance",
    "molar_mass",
    "mass_to_moles",
    "moles_to_mass",
    "moles_to_particles",
    "particles_to_moles",
    "percent_composition",
    "percent_yield",
    "stoichiometry",
    "limiting_reagent",
    "molarity",
    "dilution",
    "molality",
    "mass_percent",
    "ph_from_h",
    "ph_from_poh",
    "h_from_ph",
    "poh_from_oh",
    "buffer_ph",
    "ideal_gas",
    "heat",
    "gibbs",
    "equilibrium_constant",
    "reaction_quotient",
    "first_order_half_life",
    "first_order_concentration",
    "arrhenius",
    "cell_gibbs",
    "nernst",
    "electrolysis_mass",
    "radioactive_decay",
    "beer_lambert",
    "empirical_formula",
    "molecular_formula",
    "mass_stoichiometry",
    "solution_stoichiometry",
    "gas_stoichiometry",
    "limiting_mass",
    "limiting_solution",
    "strong_acid_ph",
    "strong_base_ph",
    "weak_acid_ph",
    "weak_base_ph",
    "ka_kb",
    "titration_strong",
    "titration_weak",
    "buffer_addition",
    "polyprotic_ph",
    "combined_gas",
    "boyle",
    "charles",
    "dalton",
    "partial_pressure",
    "gas_over_water",
    "calorimetry",
    "hess",
    "formation_enthalpy",
    "bond_enthalpy",
    "ksp",
    "precipitation",
    "common_ion",
    "kp",
    "kc_kp",
    "ice_equilibrium",
    "zero_order",
    "second_order",
    "zero_order_half_life",
    "second_order_half_life",
    "rate_law",
    "arrhenius_two_point",
    "cell_potential",
    "galvanic_cell",
    "decay_constant",
    "exponential_decay",
    "nuclear_activity",
    "nuclear_equation",
    "oxidation_state",
    "vsepr",
    "formal_charge",
    "functional_groups",
    "stereochemistry",
    "isomers",
    "coordination_complex",
    "boiling_elevation",
    "freezing_depression",
    "osmotic_pressure",
    "raoult",
    "calibration",
    "gravimetric",
    "standard_addition",
]

_OPS_BY_KIND: dict[ChemistryKind, frozenset[ChemistryOp]] = {
    "equations": frozenset({"balance"}),
    "amounts": frozenset(
        {
            "molar_mass",
            "mass_to_moles",
            "moles_to_mass",
            "moles_to_particles",
            "particles_to_moles",
            "percent_composition",
            "percent_yield",
            "empirical_formula",
            "molecular_formula",
        }
    ),
    "stoichiometry": frozenset(
        {
            "stoichiometry",
            "limiting_reagent",
            "mass_stoichiometry",
            "solution_stoichiometry",
            "gas_stoichiometry",
            "limiting_mass",
            "limiting_solution",
        }
    ),
    "solutions": frozenset(
        {
            "molarity",
            "dilution",
            "molality",
            "mass_percent",
            "boiling_elevation",
            "freezing_depression",
            "osmotic_pressure",
            "raoult",
        }
    ),
    "acid_base": frozenset(
        {
            "ph_from_h",
            "ph_from_poh",
            "h_from_ph",
            "poh_from_oh",
            "buffer_ph",
            "strong_acid_ph",
            "strong_base_ph",
            "weak_acid_ph",
            "weak_base_ph",
            "ka_kb",
            "titration_strong",
            "titration_weak",
            "buffer_addition",
            "polyprotic_ph",
        }
    ),
    "gases": frozenset(
        {
            "ideal_gas",
            "combined_gas",
            "boyle",
            "charles",
            "dalton",
            "partial_pressure",
            "gas_over_water",
        }
    ),
    "thermochemistry": frozenset(
        {"heat", "gibbs", "calorimetry", "hess", "formation_enthalpy", "bond_enthalpy"}
    ),
    "equilibrium": frozenset(
        {
            "equilibrium_constant",
            "reaction_quotient",
            "ksp",
            "precipitation",
            "common_ion",
            "kp",
            "kc_kp",
            "ice_equilibrium",
        }
    ),
    "kinetics": frozenset(
        {
            "first_order_half_life",
            "first_order_concentration",
            "arrhenius",
            "zero_order",
            "second_order",
            "zero_order_half_life",
            "second_order_half_life",
            "rate_law",
            "arrhenius_two_point",
        }
    ),
    "electrochemistry": frozenset(
        {"cell_gibbs", "nernst", "electrolysis_mass", "cell_potential", "galvanic_cell"}
    ),
    "nuclear": frozenset(
        {
            "radioactive_decay",
            "decay_constant",
            "exponential_decay",
            "nuclear_activity",
            "nuclear_equation",
        }
    ),
    "spectroscopy": frozenset({"beer_lambert"}),
    "structure": frozenset({"oxidation_state", "vsepr", "formal_charge"}),
    "organic": frozenset({"functional_groups", "stereochemistry", "isomers"}),
    "inorganic": frozenset({"coordination_complex"}),
    "analytical": frozenset({"calibration", "gravimetric", "standard_addition"}),
}


class ChemistryIntent(BaseModel):
    """One unambiguous chemistry calculation.

    ``params`` contains canonical numeric variables and ``units`` records how
    they were supplied for user-visible Given lines.  Textual chemistry data
    (formula, equation, target species) is explicit rather than hidden inside
    a generic params dictionary.
    """

    kind: ChemistryKind
    chemistry_op: ChemistryOp
    params: dict[str, float] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    formula: str | None = None
    equation: str | None = None
    target: str | None = None
    species: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def finite_values(self) -> ChemistryIntent:
        import math

        if self.chemistry_op not in _OPS_BY_KIND[self.kind]:
            raise ValueError(f"{self.chemistry_op!r} is not a {self.kind!r} chemistry operation")
        values = (*self.params.values(), *self.species.values())
        if any(not math.isfinite(value) for value in values):
            raise ValueError("chemistry values must be finite")
        return self

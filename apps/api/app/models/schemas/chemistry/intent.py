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
        }
    ),
    "stoichiometry": frozenset({"stoichiometry", "limiting_reagent"}),
    "solutions": frozenset({"molarity", "dilution", "molality", "mass_percent"}),
    "acid_base": frozenset({"ph_from_h", "ph_from_poh", "h_from_ph", "poh_from_oh", "buffer_ph"}),
    "gases": frozenset({"ideal_gas"}),
    "thermochemistry": frozenset({"heat", "gibbs"}),
    "equilibrium": frozenset({"equilibrium_constant", "reaction_quotient"}),
    "kinetics": frozenset({"first_order_half_life", "first_order_concentration", "arrhenius"}),
    "electrochemistry": frozenset({"cell_gibbs", "nernst", "electrolysis_mass"}),
    "nuclear": frozenset({"radioactive_decay"}),
    "spectroscopy": frozenset({"beer_lambert"}),
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

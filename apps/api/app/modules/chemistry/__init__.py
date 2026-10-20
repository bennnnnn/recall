"""Chemistry service package and stable public API."""

from app.modules.chemistry.equations import (
    balance_equation,
)
from app.modules.chemistry.smiles import (
    MoleculeProperties,
    compute_descriptors,
    generate_3d_coordinates,
    validate_smiles,
)
from app.modules.chemistry.solvers import ChemistryResult, solve_chemistry
from app.modules.chemistry.stoichiometry import (
    limiting_reagent,
    molar_mass,
    stoichiometry,
)

__all__ = [
    "ChemistryResult",
    "MoleculeProperties",
    "balance_equation",
    "compute_descriptors",
    "generate_3d_coordinates",
    "limiting_reagent",
    "molar_mass",
    "solve_chemistry",
    "stoichiometry",
    "validate_smiles",
]

# Seams the chat turn uses: question detection, follow-ups, and post-stream fences.
_MODULE_EXPORTS = ("context", "fence", "followup", "reply_policy", "request")

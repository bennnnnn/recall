"""Chemistry service package and stable public API."""

from app.modules.chemistry.elements import get_element_info
from app.modules.chemistry.equations import (
    BalancedEquation,
    balance_equation,
)
from app.modules.chemistry.smiles import (
    MolecularDescriptors,
    MoleculeCoordinates,
    MoleculeProperties,
    compute_descriptors,
    generate_3d_coordinates,
    normalize_smiles_input,
    validate_smiles,
)
from app.modules.chemistry.solvers import ChemistryResult, solve_chemistry
from app.modules.chemistry.stoichiometry import (
    LimitingReagentResult,
    StoichiometryResult,
    limiting_reagent,
    molar_mass,
    stoichiometry,
)

__all__ = [
    "BalancedEquation",
    "ChemistryResult",
    "LimitingReagentResult",
    "MolecularDescriptors",
    "MoleculeCoordinates",
    "MoleculeProperties",
    "StoichiometryResult",
    "balance_equation",
    "compute_descriptors",
    "generate_3d_coordinates",
    "get_element_info",
    "limiting_reagent",
    "molar_mass",
    "normalize_smiles_input",
    "solve_chemistry",
    "stoichiometry",
    "validate_smiles",
]

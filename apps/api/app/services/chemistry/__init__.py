"""Chemistry service package and stable public API."""

from app.services.chemistry.equations import (
    BalancedEquation,
    balance_equation,
)
from app.services.chemistry.smiles import (
    MolecularDescriptors,
    MoleculeCoordinates,
    MoleculeProperties,
    compute_descriptors,
    enrich_smiles_fence,
    generate_2d_coordinates,
    generate_3d_coordinates,
    normalize_smiles_input,
    validate_smiles,
)
from app.services.chemistry.solutions import (
    GasLawResult,
    SolutionResult,
    dilution,
    h_from_ph,
    ideal_gas_law,
    molarity,
    ph_from_concentration,
    ph_from_poh,
    pHResult,
)
from app.services.chemistry.stoichiometry import (
    PERIODIC_TABLE,
    LimitingReagentResult,
    StoichiometryResult,
    get_element_info,
    limiting_reagent,
    molar_mass,
    stoichiometry,
)

__all__ = [
    "PERIODIC_TABLE",
    "BalancedEquation",
    "GasLawResult",
    "LimitingReagentResult",
    "MolecularDescriptors",
    "MoleculeCoordinates",
    "MoleculeProperties",
    "SolutionResult",
    "StoichiometryResult",
    "balance_equation",
    "compute_descriptors",
    "dilution",
    "enrich_smiles_fence",
    "generate_2d_coordinates",
    "generate_3d_coordinates",
    "get_element_info",
    "h_from_ph",
    "ideal_gas_law",
    "limiting_reagent",
    "molar_mass",
    "molarity",
    "normalize_smiles_input",
    "pHResult",
    "ph_from_concentration",
    "ph_from_poh",
    "stoichiometry",
    "validate_smiles",
]

"""Compatibility alias for the packaged implementation."""

import sys

from app.services import chemistry as _impl
from app.services.chemistry import (
    PERIODIC_TABLE as PERIODIC_TABLE,
)
from app.services.chemistry import (
    BalancedEquation as BalancedEquation,
)
from app.services.chemistry import (
    GasLawResult as GasLawResult,
)
from app.services.chemistry import (
    LimitingReagentResult as LimitingReagentResult,
)
from app.services.chemistry import (
    MolecularDescriptors as MolecularDescriptors,
)
from app.services.chemistry import (
    MoleculeCoordinates as MoleculeCoordinates,
)
from app.services.chemistry import (
    MoleculeProperties as MoleculeProperties,
)
from app.services.chemistry import (
    SolutionResult as SolutionResult,
)
from app.services.chemistry import (
    StoichiometryResult as StoichiometryResult,
)
from app.services.chemistry import (
    balance_equation as balance_equation,
)
from app.services.chemistry import (
    compute_descriptors as compute_descriptors,
)
from app.services.chemistry import (
    dilution as dilution,
)
from app.services.chemistry import (
    enrich_smiles_fence as enrich_smiles_fence,
)
from app.services.chemistry import (
    generate_2d_coordinates as generate_2d_coordinates,
)
from app.services.chemistry import (
    generate_3d_coordinates as generate_3d_coordinates,
)
from app.services.chemistry import (
    get_element_info as get_element_info,
)
from app.services.chemistry import (
    h_from_ph as h_from_ph,
)
from app.services.chemistry import (
    ideal_gas_law as ideal_gas_law,
)
from app.services.chemistry import (
    limiting_reagent as limiting_reagent,
)
from app.services.chemistry import (
    molar_mass as molar_mass,
)
from app.services.chemistry import (
    molarity as molarity,
)
from app.services.chemistry import (
    normalize_smiles_input as normalize_smiles_input,
)
from app.services.chemistry import (
    ph_from_concentration as ph_from_concentration,
)
from app.services.chemistry import (
    ph_from_poh as ph_from_poh,
)
from app.services.chemistry import (
    pHResult as pHResult,
)
from app.services.chemistry import (
    stoichiometry as stoichiometry,
)
from app.services.chemistry import (
    validate_smiles as validate_smiles,
)

sys.modules[__name__] = _impl

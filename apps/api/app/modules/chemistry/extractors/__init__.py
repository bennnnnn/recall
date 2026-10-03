"""Extended extractors, in an order that does not steal the original 31 operations."""

from app.modules.chemistry.extractors.acid import (
    _extract_acid,
    _extract_buffer_addition,
    _extract_titration,
)
from app.modules.chemistry.extractors.formulas import _extract_formulas, _extract_mass_chain
from app.modules.chemistry.extractors.identity import (
    _extract_analytical,
    _extract_cells,
    _extract_colligative,
    _extract_identity,
    _extract_nuclear_ext,
)
from app.modules.chemistry.extractors.named import (
    _extract_average_atomic_mass,
    _extract_electron_configuration,
    _extract_element_mass,
    _extract_graham,
)
from app.modules.chemistry.extractors.physical import (
    _extract_equilibrium_ext,
    _extract_gas_laws,
    _extract_henry,
    _extract_kinetics_ext,
    _extract_thermo_ext,
)
from app.modules.chemistry.extractors.remaining import _extract_remaining

EXTENDED_EXTRACTORS = (
    _extract_remaining,
    _extract_formulas,
    _extract_mass_chain,
    _extract_acid,
    _extract_titration,
    _extract_buffer_addition,
    _extract_henry,
    _extract_gas_laws,
    _extract_thermo_ext,
    _extract_equilibrium_ext,
    _extract_kinetics_ext,
    _extract_cells,
    _extract_nuclear_ext,
    _extract_identity,
    _extract_colligative,
    _extract_analytical,
    _extract_graham,
    _extract_element_mass,
    _extract_average_atomic_mass,
    _extract_electron_configuration,
)

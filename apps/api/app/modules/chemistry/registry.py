"""The ordered chemistry extractor chain.

The first extractor that returns an intent wins, so the order is load-bearing. The labelled
templates of the original catalog read first. The closed calculations and the topic readers
added after them follow, in an order that never takes an operation the templates answer.
Readers of the substances a question names (Graham's law, an element's mass, isotopes,
an electron configuration) run last: they need no stated value, so they would otherwise claim
a question a value-reading template answers.
"""

from __future__ import annotations

from collections.abc import Callable

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.extractors.acid_base import _extract_acid_solution, _extract_ph
from app.modules.chemistry.extractors.amounts import (
    _extract_amounts,
    _extract_average_atomic_mass,
    _extract_element_mass,
    _extract_empirical,
)
from app.modules.chemistry.extractors.analytical import (
    _extract_analytical,
    _extract_statistics,
)
from app.modules.chemistry.extractors.electrochemistry import (
    _extract_cells,
    _extract_electrochem,
)
from app.modules.chemistry.extractors.equations import _extract_equations
from app.modules.chemistry.extractors.equilibrium import _extract_equilibrium
from app.modules.chemistry.extractors.gases import _extract_gas_laws, _extract_graham
from app.modules.chemistry.extractors.kinetics import (
    _extract_first_order,
    _extract_michaelis,
    _extract_rate_laws,
)
from app.modules.chemistry.extractors.nuclear import (
    _extract_mass_defect,
    _extract_nuclear_equation,
)
from app.modules.chemistry.extractors.organic import _extract_named_reaction, _extract_organic
from app.modules.chemistry.extractors.solutions import _extract_colligative, _extract_solutions
from app.modules.chemistry.extractors.spectroscopy import (
    _extract_beer_lambert,
    _extract_spectrum,
)
from app.modules.chemistry.extractors.stoichiometry import _extract_mass_chain
from app.modules.chemistry.extractors.structure import (
    _extract_coordination,
    _extract_crystal_field,
    _extract_electron_configuration,
    _extract_structure,
)
from app.modules.chemistry.extractors.thermochemistry import _extract_enthalpy, _extract_gibbs
from app.modules.chemistry.extractors.titration import (
    _extract_buffer_addition,
    _extract_titration,
)

Extractor = Callable[[str], ChemistryIntent | None]

CHEMISTRY_EXTRACTORS: tuple[Extractor, ...] = (
    # The labelled templates. A written equation reads first: its K, Q or mole question
    # names species the value templates below would read one at a time.
    _extract_equations,
    _extract_ph,
    _extract_gibbs,
    _extract_first_order,
    _extract_electrochem,
    _extract_beer_lambert,
    _extract_solutions,
    _extract_amounts,
    # Closed calculations with their own vocabulary, ahead of the topic readers.
    _extract_mass_defect,
    _extract_crystal_field,
    _extract_statistics,
    _extract_michaelis,
    _extract_named_reaction,
    _extract_spectrum,
    # Topic readers.
    _extract_empirical,
    _extract_mass_chain,
    _extract_acid_solution,
    _extract_titration,
    _extract_buffer_addition,
    _extract_gas_laws,
    _extract_enthalpy,
    _extract_equilibrium,
    _extract_rate_laws,
    _extract_cells,
    _extract_nuclear_equation,
    _extract_structure,
    _extract_organic,
    _extract_coordination,
    _extract_colligative,
    _extract_analytical,
    # Readers of named substances, last.
    _extract_graham,
    _extract_element_mass,
    _extract_average_atomic_mass,
    _extract_electron_configuration,
)
# A question written in mM, µM or kcal reaches only the readers that convert units.
UNIT_AWARE_EXTRACTORS: tuple[Extractor, ...] = (_extract_michaelis,)

"""Compatibility alias for the packaged implementation."""

import sys

from app.services.chemistry import context as _impl
from app.services.chemistry.context import (
    Settings as Settings,
)
from app.services.chemistry.context import (
    annotations as annotations,
)
from app.services.chemistry.context import (
    build_chemistry_context as build_chemistry_context,
)
from app.services.chemistry.context import (
    chemistry_service as chemistry_service,
)
from app.services.chemistry.context import (
    extract_compound_name as extract_compound_name,
)
from app.services.chemistry.context import (
    is_chemistry_question as is_chemistry_question,
)
from app.services.chemistry.context import (
    logger as logger,
)
from app.services.chemistry.context import (
    logging as logging,
)
from app.services.chemistry.context import (
    pubchem_gateway as pubchem_gateway,
)
from app.services.chemistry.context import (
    re as re,
)

sys.modules[__name__] = _impl

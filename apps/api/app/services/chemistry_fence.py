"""Compatibility alias for the packaged implementation."""

import sys

from app.services.chemistry import fence as _impl
from app.services.chemistry.fence import (
    enrich_chemistry_fences as enrich_chemistry_fences,
)
from app.services.chemistry.fence import (
    enrich_chemistry_fences_worker as enrich_chemistry_fences_worker,
)

sys.modules[__name__] = _impl

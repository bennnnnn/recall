"""Compatibility alias for the packaged implementation."""

import sys

from app.services.chemistry import fence as _impl
from app.services.chemistry.fence import (
    annotations as annotations,
)
from app.services.chemistry.fence import (
    chemistry_service as chemistry_service,
)
from app.services.chemistry.fence import (
    enrich_chemistry_fences as enrich_chemistry_fences,
)
from app.services.chemistry.fence import (
    enrich_chemistry_fences_worker as enrich_chemistry_fences_worker,
)
from app.services.chemistry.fence import (
    logger as logger,
)
from app.services.chemistry.fence import (
    logging as logging,
)
from app.services.chemistry.fence import (
    re as re,
)

sys.modules[__name__] = _impl

"""Compatibility alias for the packaged implementation."""

import sys

from app.services.learning import spaced_repetition as _impl
from app.services.learning.spaced_repetition import (
    UTC as UTC,
)
from app.services.learning.spaced_repetition import (
    Sm2State as Sm2State,
)
from app.services.learning.spaced_repetition import (
    annotations as annotations,
)
from app.services.learning.spaced_repetition import (
    apply_sm2 as apply_sm2,
)
from app.services.learning.spaced_repetition import (
    dataclass as dataclass,
)
from app.services.learning.spaced_repetition import (
    datetime as datetime,
)
from app.services.learning.spaced_repetition import (
    quality_for_status as quality_for_status,
)
from app.services.learning.spaced_repetition import (
    timedelta as timedelta,
)

sys.modules[__name__] = _impl

"""Compatibility alias for the packaged implementation."""

import sys

from app.services.learning import insights as _impl
from app.services.learning.insights import (
    LEARNING_PROJECT_KINDS as LEARNING_PROJECT_KINDS,
)
from app.services.learning.insights import (
    UUID as UUID,
)
from app.services.learning.insights import (
    Any as Any,
)
from app.services.learning.insights import (
    Literal as Literal,
)
from app.services.learning.insights import (
    NudgeType as NudgeType,
)
from app.services.learning.insights import (
    Project as Project,
)
from app.services.learning.insights import (
    ZoneInfo as ZoneInfo,
)
from app.services.learning.insights import (
    annotations as annotations,
)
from app.services.learning.insights import (
    best_learning_nudge_for_user as best_learning_nudge_for_user,
)
from app.services.learning.insights import (
    completed_today_count as completed_today_count,
)
from app.services.learning.insights import (
    compute_streak_days as compute_streak_days,
)
from app.services.learning.insights import (
    datetime as datetime,
)
from app.services.learning.insights import (
    days_since_last_study as days_since_last_study,
)
from app.services.learning.insights import (
    enrich_learning_stats as enrich_learning_stats,
)
from app.services.learning.insights import (
    is_learning_project_kind as is_learning_project_kind,
)
from app.services.learning.insights import (
    pick_learning_nudge as pick_learning_nudge,
)
from app.services.learning.insights import (
    quiz_accuracy_pct as quiz_accuracy_pct,
)

sys.modules[__name__] = _impl

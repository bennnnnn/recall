"""Compatibility alias for the packaged implementation."""

import sys

from app.services.learning import nudges as _impl
from app.services.learning.nudges import (
    UUID as UUID,
)
from app.services.learning.nudges import (
    Any as Any,
)
from app.services.learning.nudges import (
    AsyncSession as AsyncSession,
)
from app.services.learning.nudges import (
    LearningNudgePick as LearningNudgePick,
)
from app.services.learning.nudges import (
    Project as Project,
)
from app.services.learning.nudges import (
    Redis as Redis,
)
from app.services.learning.nudges import (
    User as User,
)
from app.services.learning.nudges import (
    annotations as annotations,
)
from app.services.learning.nudges import (
    claim_learning_candidates as claim_learning_candidates,
)
from app.services.learning.nudges import (
    collect_learning_nudge_picks as collect_learning_nudge_picks,
)
from app.services.learning.nudges import (
    daily_learning as daily_learning,
)
from app.services.learning.nudges import (
    dataclass as dataclass,
)
from app.services.learning.nudges import (
    datetime as datetime,
)
from app.services.learning.nudges import (
    learning_dedupe_key as learning_dedupe_key,
)
from app.services.learning.nudges import (
    learning_insights as learning_insights,
)
from app.services.learning.nudges import (
    load_learning_stats_for_candidates as load_learning_stats_for_candidates,
)
from app.services.learning.nudges import (
    logger as logger,
)
from app.services.learning.nudges import (
    logging as logging,
)
from app.services.learning.nudges import (
    project_stats as project_stats,
)
from app.services.learning.nudges import (
    projects_repo as projects_repo,
)
from app.services.learning.nudges import (
    user_day_key as user_day_key,
)
from app.services.learning.nudges import (
    user_local_hour as user_local_hour,
)

sys.modules[__name__] = _impl

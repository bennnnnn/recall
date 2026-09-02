"""Compatibility alias for the packaged implementation."""

import sys

from app.services.learning import daily as _impl
from app.services.learning.daily import (
    DEFAULT_DAILY_VOCAB_GOAL as DEFAULT_DAILY_VOCAB_GOAL,
)
from app.services.learning.daily import (
    STANDARD_DAILY_GOALS as STANDARD_DAILY_GOALS,
)
from app.services.learning.daily import (
    UTC as UTC,
)
from app.services.learning.daily import (
    Any as Any,
)
from app.services.learning.daily import (
    DailyHistoryStatus as DailyHistoryStatus,
)
from app.services.learning.daily import (
    HomeDailyCue as HomeDailyCue,
)
from app.services.learning.daily import (
    Literal as Literal,
)
from app.services.learning.daily import (
    ZoneInfo as ZoneInfo,
)
from app.services.learning.daily import (
    annotations as annotations,
)
from app.services.learning.daily import (
    append_daily_goal_history as append_daily_goal_history,
)
from app.services.learning.daily import (
    build_daily_history as build_daily_history,
)
from app.services.learning.daily import (
    completed_today_count as completed_today_count,
)
from app.services.learning.daily import (
    count_missed_by_date as count_missed_by_date,
)
from app.services.learning.daily import (
    count_today_vocab_stats as count_today_vocab_stats,
)
from app.services.learning.daily import (
    daily_home_cue as daily_home_cue,
)
from app.services.learning.daily import (
    date as date,
)
from app.services.learning.daily import (
    datetime as datetime,
)
from app.services.learning.daily import (
    day_bounds_utc as day_bounds_utc,
)
from app.services.learning.daily import (
    day_goal_for_history as day_goal_for_history,
)
from app.services.learning.daily import (
    ensure_daily_goal_history as ensure_daily_goal_history,
)
from app.services.learning.daily import (
    goal_effective_on_date as goal_effective_on_date,
)
from app.services.learning.daily import (
    group_mastered_items_by_date as group_mastered_items_by_date,
)
from app.services.learning.daily import (
    group_missed_items_by_date as group_missed_items_by_date,
)
from app.services.learning.daily import (
    infer_daily_goal_history as infer_daily_goal_history,
)
from app.services.learning.daily import (
    last_mastery_at as last_mastery_at,
)
from app.services.learning.daily import (
    parse_daily_goal_history as parse_daily_goal_history,
)
from app.services.learning.daily import (
    prior_standard_goal as prior_standard_goal,
)
from app.services.learning.daily import (
    resolve_daily_goal as resolve_daily_goal,
)
from app.services.learning.daily import (
    start_of_today_utc as start_of_today_utc,
)
from app.services.learning.daily import (
    timedelta as timedelta,
)

sys.modules[__name__] = _impl

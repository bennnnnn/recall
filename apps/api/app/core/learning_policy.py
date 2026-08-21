"""Dependency-neutral daily learning policy and calendar helpers."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

DEFAULT_DAILY_VOCAB_GOAL = 10
DEFAULT_DAILY_TRIVIA_GOAL = 10


def start_of_today_utc(timezone_name: str, *, now: datetime | None = None) -> datetime:
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    local_now = now.astimezone(tz) if now is not None else datetime.now(tz)
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(UTC)


def day_bounds_utc(activity_date: date, timezone_name: str) -> tuple[datetime, datetime]:
    """Return [start, end) UTC bounds for one local calendar day."""
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    local_start = datetime.combine(activity_date, datetime.min.time(), tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def resolve_daily_goal(project: object) -> int:
    goal = getattr(project, "daily_goal", None)
    if isinstance(goal, int) and goal >= 1:
        return goal
    if getattr(project, "kind", None) == "trivia":
        return DEFAULT_DAILY_TRIVIA_GOAL
    return DEFAULT_DAILY_VOCAB_GOAL

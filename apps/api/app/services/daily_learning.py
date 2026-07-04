"""Helpers for daily vocabulary / quiz pacing stats."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

DEFAULT_DAILY_VOCAB_GOAL = 10
DEFAULT_DAILY_TRIVIA_GOAL = 10

HomeDailyCue = Literal[
    "start",
    "continue",
    "not_started_today",
    "missed_yesterday",
    "finish_pending",
]

# Backward-compatible alias for older imports/tests.
HomeVocabCue = HomeDailyCue


def start_of_today_utc(timezone_name: str) -> datetime:
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    local_now = datetime.now(tz)
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def count_today_vocab_stats(
    items: list,
    *,
    timezone_name: str,
) -> tuple[int, int]:
    """Return (mastered_today, pending_today) for language project items."""
    start = start_of_today_utc(timezone_name)
    mastered_today = 0
    pending_today = 0
    for item in items:
        status = item.status or ("mastered" if item.mastered else "new")
        created = _as_utc(item.created_at)
        if status == "mastered":
            mastered_at = item.mastered_at
            if mastered_at is not None:
                if _as_utc(mastered_at) >= start:
                    mastered_today += 1
            elif created >= start:
                mastered_today += 1
        elif created >= start:
            pending_today += 1
    return mastered_today, pending_today


def resolve_daily_goal(project: object) -> int:
    goal = getattr(project, "daily_goal", None)
    if isinstance(goal, int) and goal >= 1:
        return goal
    kind = getattr(project, "kind", None)
    if kind == "trivia":
        return DEFAULT_DAILY_TRIVIA_GOAL
    return DEFAULT_DAILY_VOCAB_GOAL


def resolve_daily_vocab_goal(project: object) -> int:
    return resolve_daily_goal(project)


def last_mastery_at(items: list) -> datetime | None:
    latest: datetime | None = None
    for item in items:
        mastered_at = getattr(item, "mastered_at", None)
        if mastered_at is None:
            continue
        candidate = _as_utc(mastered_at)
        if latest is None or candidate > latest:
            latest = candidate
    return latest


def daily_home_cue(
    *,
    total: int,
    mastered_today: int,
    pending_today: int,
    learning_count: int,
    due_for_review: int,
    daily_goal: int,
    last_mastery: datetime | None,
    home_tz: ZoneInfo,
) -> HomeDailyCue | None:
    """Return a home-card cue, or None when today's daily goal is complete."""
    if mastered_today >= daily_goal:
        return None
    if total == 0:
        return "start"
    if mastered_today > 0:
        return "continue"
    if pending_today > 0 or learning_count > 0 or due_for_review > 0:
        return "finish_pending"
    today = datetime.now(home_tz).date()
    if last_mastery is not None:
        last_day = last_mastery.astimezone(home_tz).date()
        if last_day <= today - timedelta(days=2):
            return "missed_yesterday"
    return "not_started_today"


def daily_vocab_home_cue(**kwargs: object) -> HomeDailyCue | None:
    return daily_home_cue(**kwargs)  # type: ignore[arg-type]

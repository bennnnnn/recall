"""Helpers for daily vocabulary / quiz pacing stats."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
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

DailyHistoryStatus = Literal["complete", "partial", "skipped", "today", "inactive"]

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


def day_bounds_utc(activity_date: date, timezone_name: str) -> tuple[datetime, datetime]:
    """Return [start, end) UTC bounds for one local calendar day."""
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    local_start = datetime.combine(activity_date, datetime.min.time(), tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _optional_utc(value: object) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return _as_utc(value)


def count_today_vocab_stats(
    items: list,
    *,
    timezone_name: str,
) -> tuple[int, int, int]:
    """Return (mastered_today, missed_today, pending_today).

    missed_today = incorrect today and not currently mastered (session slots that
    finished without a correct answer). Correct + missed = daily progress.
    """
    start = start_of_today_utc(timezone_name)
    mastered_today = 0
    missed_today = 0
    pending_today = 0
    for item in items:
        status = item.status or ("mastered" if item.mastered else "new")
        created = _optional_utc(getattr(item, "created_at", None))
        if created is None:
            continue
        if status == "mastered":
            mastered_at = _optional_utc(getattr(item, "mastered_at", None))
            if mastered_at is not None:
                if mastered_at >= start:
                    mastered_today += 1
            elif created >= start:
                mastered_today += 1
        else:
            incorrect_at = _optional_utc(getattr(item, "last_incorrect_at", None))
            if incorrect_at is not None and incorrect_at >= start:
                missed_today += 1
            elif created >= start:
                pending_today += 1
    return mastered_today, missed_today, pending_today


def completed_today_count(mastered_today: int, missed_today: int) -> int:
    """Questions finished toward the daily goal (correct + open misses)."""
    return max(0, int(mastered_today) + int(missed_today))


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


STANDARD_DAILY_GOALS: tuple[int, ...] = (5, 10, 15)


def _timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return ZoneInfo("UTC")


def parse_daily_goal_history(project: object) -> list[dict[str, int | str]]:
    raw = getattr(project, "daily_goal_history", None)
    if not isinstance(raw, list):
        return []
    parsed: list[dict[str, int | str]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        effective_from = entry.get("effective_from")
        goal = entry.get("goal")
        if not isinstance(effective_from, str) or not isinstance(goal, int) or goal < 1:
            continue
        parsed.append({"effective_from": effective_from, "goal": goal})
    parsed.sort(key=lambda row: str(row["effective_from"]))
    return parsed


def prior_standard_goal(goal: int) -> int | None:
    lowers = [tier for tier in STANDARD_DAILY_GOALS if tier < goal]
    return lowers[-1] if lowers else None


def goal_effective_on_date(
    history: list[dict[str, int | str]],
    day: date,
    *,
    fallback: int,
) -> int:
    if not history:
        return fallback
    effective = max(1, fallback)
    for entry in history:
        try:
            entry_date = date.fromisoformat(str(entry["effective_from"]))
        except ValueError:
            continue
        if entry_date <= day:
            effective = max(1, int(entry["goal"]))
        else:
            break
    return effective


def day_goal_for_history(
    *,
    count: int,
    day: date,
    today: date,
    history: list[dict[str, int | str]],
    current_goal: int,
) -> int:
    """Resolve the goal that should judge one calendar day."""
    goal = goal_effective_on_date(history, day, fallback=current_goal)
    prior = prior_standard_goal(current_goal)
    # Past day hit exactly the prior tier (e.g. 5/5) before a goal increase was logged.
    if prior is not None and day < today and count == prior and goal > prior:
        return prior
    return goal


def append_daily_goal_history(
    existing: list[dict[str, int | str]] | None,
    *,
    old_goal: int | None,
    new_goal: int,
    project_created: datetime,
    effective_from: date,
    timezone_name: str,
) -> list[dict[str, int | str]]:
    tz = _timezone(timezone_name)
    created_local = _as_utc(project_created).astimezone(tz).date()
    history = list(existing or [])
    if not history:
        seed_goal = old_goal if isinstance(old_goal, int) and old_goal >= 1 else new_goal
        history = [{"effective_from": created_local.isoformat(), "goal": seed_goal}]
    today_key = effective_from.isoformat()
    history = [row for row in history if str(row["effective_from"]) != today_key]
    history.append({"effective_from": today_key, "goal": max(1, new_goal)})
    history.sort(key=lambda row: str(row["effective_from"]))
    return history


def infer_daily_goal_history(
    project: object,
    items: list,
    *,
    timezone_name: str,
) -> list[dict[str, int | str]]:
    """Best-effort backfill when goal changes were not logged."""
    current = resolve_daily_goal(project)
    tz = _timezone(timezone_name)
    created = _as_utc(getattr(project, "created_at", datetime.now(UTC))).astimezone(tz).date()
    today = datetime.now(tz).date()

    mastered_by_day: dict[date, int] = {}
    for item in items:
        day = _mastered_local_date(item, tz)
        if day is not None:
            mastered_by_day[day] = mastered_by_day.get(day, 0) + 1

    prior = prior_standard_goal(current)
    if prior is None:
        return [{"effective_from": created.isoformat(), "goal": current}]

    days_at_prior = [day for day, count in mastered_by_day.items() if count >= prior]
    if not days_at_prior:
        return [{"effective_from": created.isoformat(), "goal": current}]

    days_between = [day for day, count in mastered_by_day.items() if prior < count < current]
    if days_between:
        split = min(days_between)
        return [
            {"effective_from": created.isoformat(), "goal": prior},
            {"effective_from": split.isoformat(), "goal": current},
        ]

    last_prior_day = max(days_at_prior)
    split = min(last_prior_day + timedelta(days=1), today)
    if split <= created:
        split = min(created + timedelta(days=1), today)
    if split.isoformat() == created.isoformat():
        return [{"effective_from": created.isoformat(), "goal": current}]
    return [
        {"effective_from": created.isoformat(), "goal": prior},
        {"effective_from": split.isoformat(), "goal": current},
    ]


def ensure_daily_goal_history(
    project: object,
    items: list,
    *,
    timezone_name: str,
) -> list[dict[str, int | str]]:
    existing = parse_daily_goal_history(project)
    if len(existing) > 1:
        return existing
    return infer_daily_goal_history(project, items, timezone_name=timezone_name)


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
    missed_today: int = 0,
) -> HomeDailyCue | None:
    """Return a home-card cue, or None when today's daily goal is complete."""
    completed_today = max(0, int(mastered_today) + int(missed_today))
    if completed_today >= daily_goal:
        return None
    if total == 0:
        return "start"
    if completed_today > 0:
        return "continue"
    if pending_today > 0:
        return "finish_pending"
    today = datetime.now(home_tz).date()
    if last_mastery is not None:
        last_day = last_mastery.astimezone(home_tz).date()
        if last_day <= today - timedelta(days=2):
            return "missed_yesterday"
    return "not_started_today"


def daily_vocab_home_cue(**kwargs: object) -> HomeDailyCue | None:
    return daily_home_cue(**kwargs)  # type: ignore[arg-type]


def _mastered_local_date(item: object, tz: ZoneInfo) -> date | None:
    status = getattr(item, "status", None) or (
        "mastered" if getattr(item, "mastered", False) else "new"
    )
    if status != "mastered":
        return None
    mastered_at = getattr(item, "mastered_at", None)
    if mastered_at is not None:
        return _as_utc(mastered_at).astimezone(tz).date()
    created = getattr(item, "created_at", None)
    if created is None:
        return None
    return _as_utc(created).astimezone(tz).date()


def _item_activity_sort_key(item: object) -> tuple[datetime, datetime]:
    mastered_at = getattr(item, "mastered_at", None)
    created = getattr(item, "created_at", None)
    mastered = _as_utc(mastered_at) if mastered_at is not None else datetime.min.replace(tzinfo=UTC)
    created_at = _as_utc(created) if created is not None else datetime.min.replace(tzinfo=UTC)
    return mastered, created_at


def _incorrect_local_date(item: object, tz: ZoneInfo) -> date | None:
    incorrect_at = getattr(item, "last_incorrect_at", None)
    if incorrect_at is None:
        return None
    return _as_utc(incorrect_at).astimezone(tz).date()


def _item_missed_sort_key(item: object) -> datetime:
    incorrect_at = getattr(item, "last_incorrect_at", None)
    if incorrect_at is not None:
        return _as_utc(incorrect_at)
    created = getattr(item, "created_at", None)
    return _as_utc(created) if created is not None else datetime.min.replace(tzinfo=UTC)


def count_missed_by_date(
    items: list,
    *,
    timezone_name: str,
) -> dict[date, int]:
    """Open misses per local day (excludes items later mastered)."""
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    counts: dict[date, int] = {}
    for item in items:
        status = getattr(item, "status", None) or (
            "mastered" if getattr(item, "mastered", False) else "new"
        )
        if status == "mastered":
            continue
        day = _incorrect_local_date(item, tz)
        if day is None:
            continue
        counts[day] = counts.get(day, 0) + 1
    return counts


def group_missed_items_by_date(
    items: list,
    *,
    timezone_name: str,
    days: int = 14,
) -> dict[str, list]:
    """Still-missed items (not mastered), grouped by local miss date."""
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    today = datetime.now(tz).date()
    span = max(1, min(days, 60))
    valid_dates = {
        (today - timedelta(days=offset)).isoformat() for offset in range(span - 1, -1, -1)
    }
    grouped: dict[str, list] = {day_key: [] for day_key in valid_dates}
    for item in items:
        status = getattr(item, "status", None) or (
            "mastered" if getattr(item, "mastered", False) else "new"
        )
        if status == "mastered":
            continue
        day = _incorrect_local_date(item, tz)
        if day is None:
            continue
        key = day.isoformat()
        if key not in grouped:
            continue
        grouped[key].append(item)
    return {
        day_key: sorted(day_items, key=_item_missed_sort_key, reverse=True)
        for day_key, day_items in grouped.items()
        if day_items
    }


def group_mastered_items_by_date(
    items: list,
    *,
    timezone_name: str,
    days: int = 14,
) -> dict[str, list]:
    """Mastered items grouped by local activity date for the recent history window."""
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    today = datetime.now(tz).date()
    span = max(1, min(days, 60))
    valid_dates = {
        (today - timedelta(days=offset)).isoformat() for offset in range(span - 1, -1, -1)
    }
    grouped: dict[str, list] = {day_key: [] for day_key in valid_dates}
    for item in items:
        day = _mastered_local_date(item, tz)
        if day is None:
            continue
        key = day.isoformat()
        if key not in grouped:
            continue
        grouped[key].append(item)
    return {
        day_key: sorted(day_items, key=_item_activity_sort_key, reverse=True)
        for day_key, day_items in grouped.items()
        if day_items
    }


def build_daily_history(
    items: list,
    *,
    timezone_name: str,
    daily_goal: int,
    active_since: datetime,
    daily_goal_history: list[dict[str, int | str]] | None = None,
    days: int = 14,
) -> list[dict[str, object]]:
    """Per-calendar-day mastery counts for language/trivia projects."""
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    today = datetime.now(tz).date()
    active_since_date = _as_utc(active_since).astimezone(tz).date()
    fallback_goal = max(1, daily_goal)
    history = list(daily_goal_history or [])

    counts: dict[date, int] = {}
    for item in items:
        day = _mastered_local_date(item, tz)
        if day is None:
            continue
        counts[day] = counts.get(day, 0) + 1

    missed_counts = count_missed_by_date(items, timezone_name=timezone_name)

    history_rows: list[dict[str, object]] = []
    span = max(1, min(days, 60))
    for offset in range(span - 1, -1, -1):
        day = today - timedelta(days=offset)
        mastered = counts.get(day, 0)
        missed = missed_counts.get(day, 0)
        completed = mastered + missed
        goal = day_goal_for_history(
            count=completed,
            day=day,
            today=today,
            history=history,
            current_goal=fallback_goal,
        )
        goal_met = completed >= goal
        if day < active_since_date:
            status: DailyHistoryStatus = "inactive"
        elif day == today:
            status = "complete" if goal_met else "today"
        elif goal_met:
            status = "complete"
        elif completed > 0:
            status = "partial"
        else:
            status = "skipped"
        history_rows.append(
            {
                "date": day.isoformat(),
                "weekday": day.weekday(),
                "mastered_count": mastered,
                "missed_count": missed,
                "daily_goal": goal,
                "goal_met": goal_met,
                "status": status,
            }
        )
    return history_rows

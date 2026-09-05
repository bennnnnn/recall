"""Combine immutable lesson activity with pre-existing daily history."""

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from app.models.orm import LearningPracticeEvent, ProjectItem


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _local_day(value: datetime, timezone: ZoneInfo) -> str:
    return _utc(value).astimezone(timezone).date().isoformat()


def merge_practice_history(
    history: list[dict[str, Any]],
    items: list[ProjectItem],
    events: list[LearningPracticeEvent],
    *,
    timezone_name: str,
    now: datetime | None = None,
    miss_events_by_item: dict[UUID, list[datetime]] | None = None,
) -> list[dict[str, Any]]:
    timezone = _timezone(timezone_name)
    today = (now or datetime.now(UTC)).astimezone(timezone).date().isoformat()
    by_day: dict[str, list[LearningPracticeEvent]] = defaultdict(list)
    for event in events:
        by_day[_local_day(event.occurred_at, timezone)].append(event)
    for row in history:
        day = str(row["date"])
        activity = by_day.get(day, [])
        # Preserve older daily totals when the new event stream has no records.
        row["completed_count"] = int(row["mastered_count"]) + int(row["missed_count"])
        row["attempted_count"] = row["completed_count"]
        if not activity:
            continue
        practiced = {event.item_id for event in activity}
        completed = {event.item_id for event in activity if event.completes_word}
        incorrect = {event.item_id for event in activity if not event.was_correct}
        legacy_mastered: set[UUID] = set()
        legacy_missed: set[UUID] = set()
        for item in items:
            mastered = item.status == "mastered" or item.mastered
            mastery = item.mastered_at or (item.created_at if mastered else None)
            if mastered and mastery is not None and _local_day(mastery, timezone) == day:
                legacy_mastered.add(item.id)
            if item.id in practiced:
                continue
            misses = (miss_events_by_item or {}).get(item.id)
            if misses is None:
                misses = (
                    [item.last_incorrect_at]
                    if item.last_incorrect_at is not None and not mastered
                    else []
                )
            for missed in misses:
                if _local_day(missed, timezone) == day and (
                    not mastered or mastery is None or _utc(missed) < _utc(mastery)
                ):
                    legacy_missed.add(item.id)
        row["completed_count"] = len(completed | legacy_mastered | legacy_missed)
        row["attempted_count"] = len(practiced | legacy_mastered | legacy_missed)
        row["missed_count"] = len(incorrect | legacy_missed)
        row["goal_met"] = row["completed_count"] >= int(row["daily_goal"])
        if row["status"] != "inactive":
            row["status"] = (
                "complete" if row["goal_met"] else "today" if day == today else "partial"
            )
    return history


def merge_practice_items(
    grouped: dict[str, list[ProjectItem]],
    items: list[ProjectItem],
    events: list[LearningPracticeEvent],
    *,
    timezone_name: str,
    allowed_days: set[str],
    missed: bool = False,
) -> dict[str, list[ProjectItem]]:
    """Add completed reviews and actual wrong answers to their original day."""
    timezone = _timezone(timezone_name)
    by_id = {item.id: item for item in items}
    seen = {day: {item.id for item in rows} for day, rows in grouped.items()}
    for event in events:
        qualifies = not event.was_correct if missed else event.completes_word
        day = _local_day(event.occurred_at, timezone)
        if not qualifies or day not in allowed_days or event.item_id not in by_id:
            continue
        day_ids = seen.setdefault(day, set())
        if event.item_id not in day_ids:
            grouped.setdefault(day, []).append(by_id[event.item_id])
            day_ids.add(event.item_id)
    return grouped

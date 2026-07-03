"""Helpers for daily vocabulary / quiz pacing stats."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


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

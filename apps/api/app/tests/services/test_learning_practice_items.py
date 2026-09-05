from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.models.orm import LearningPracticeEvent
from app.services.learning import daily
from app.services.learning.daily import (
    group_mastered_items_by_date,
    group_missed_items_by_date,
)
from app.services.learning.practice_history import merge_practice_items

NOW = datetime(2026, 9, 6, 2, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def fixed_daily_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz)

    monkeypatch.setattr(daily, "datetime", Clock)


def mastered_word(now):
    return SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        status="mastered",
        mastered=True,
        mastered_at=now - timedelta(days=1),
        created_at=now - timedelta(days=10),
        last_incorrect_at=now,
    )


def practice(word, now, *, correct=True, complete=False):
    return LearningPracticeEvent(
        id=uuid4(),
        attempt_id=uuid4(),
        user_id=uuid4(),
        project_id=word.project_id,
        item_id=word.id,
        occurred_at=now,
        was_correct=correct,
        completes_word=complete,
    )


def test_completed_review_adds_day_missing_from_actual_mastery_groups():
    timezone = "America/Los_Angeles"
    now = NOW
    today = now.astimezone(ZoneInfo(timezone)).date().isoformat()
    word = mastered_word(now)
    grouped = group_mastered_items_by_date([word], timezone_name=timezone, days=14)
    assert today not in grouped

    merged = merge_practice_items(
        grouped,
        [word],
        [practice(word, now, complete=True)],
        timezone_name=timezone,
        allowed_days={today},
    )

    assert merged[today] == [word]
    assert sum(len(rows) for rows in merged.values()) == 2


def test_wrong_mastered_review_adds_day_missing_from_actual_miss_groups():
    now = NOW
    today = now.date().isoformat()
    word = mastered_word(now)
    grouped = group_missed_items_by_date(
        [word], timezone_name="UTC", days=14, miss_events_by_item={word.id: [now]}
    )
    assert grouped == {}

    merged = merge_practice_items(
        grouped,
        [word],
        [practice(word, now, correct=False)],
        timezone_name="UTC",
        allowed_days={today},
        missed=True,
    )

    assert merged[today] == [word]


@pytest.mark.parametrize("missed", [False, True])
def test_only_qualifying_known_items_in_requested_local_days_are_added_once(missed):
    timezone = "America/Los_Angeles"
    today = NOW.astimezone(ZoneInfo(timezone)).date().isoformat()
    word, unknown = mastered_word(NOW), mastered_word(NOW)
    outcome = {"correct": not missed, "complete": not missed}
    events = [
        practice(word, NOW, **outcome),
        practice(word, NOW + timedelta(minutes=1), **outcome),
        practice(word, NOW - timedelta(days=14), **outcome),
        practice(word, NOW + timedelta(days=1), **outcome),
        practice(unknown, NOW, **outcome),
        practice(word, NOW, correct=True),
    ]

    merged = merge_practice_items(
        {}, [word], events, timezone_name=timezone, allowed_days={today}, missed=missed
    )

    assert merged == {today: [word]}

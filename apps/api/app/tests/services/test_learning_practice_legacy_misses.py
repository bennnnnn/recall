"""Reconcile old and new wrong-answer records without losing either source."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.models.orm import LearningPracticeEvent
from app.services.learning.daily import count_missed_by_date
from app.services.learning.practice_history import merge_practice_history

WHEN = datetime(2026, 9, 6, 1, tzinfo=UTC)


def word(*, incorrect_at=None):
    return SimpleNamespace(
        id=uuid4(),
        status="learning",
        mastered=False,
        mastered_at=None,
        created_at=WHEN - timedelta(days=10),
        last_incorrect_at=incorrect_at,
    )


def practice(item, *, correct=True, when=WHEN):
    return LearningPracticeEvent(
        id=uuid4(),
        user_id=uuid4(),
        project_id=uuid4(),
        item_id=item.id,
        attempt_id=uuid4(),
        was_correct=correct,
        completes_word=False,
        occurred_at=when,
    )


def merged(items, events, misses=None, *, timezone="UTC"):
    day = WHEN.astimezone(ZoneInfo(timezone)).date()
    legacy_counts = count_missed_by_date(items, timezone_name=timezone, miss_events_by_item=misses)
    rows = [
        dict(
            date=day.isoformat(),
            mastered_count=0,
            missed_count=legacy_counts.get(day, 0),
            daily_goal=1,
            goal_met=False,
            status="partial",
        )
    ]
    return merge_practice_history(
        rows,
        items,
        events,
        timezone_name=timezone,
        now=WHEN + timedelta(days=1),
        miss_events_by_item=misses,
    )[0]


@pytest.mark.parametrize("source", ["ledger", "fallback"])
def test_correct_partial_practice_keeps_later_legacy_miss_without_completing_word(source):
    wrong_at = WHEN + timedelta(minutes=30)
    item = word(incorrect_at=wrong_at)
    misses = {item.id: [wrong_at]} if source == "ledger" else None
    result = merged([item], [practice(item)], misses)
    assert result["missed_count"] == 1
    assert result["attempted_count"] == 1
    assert result["completed_count"] == 0
    assert result["goal_met"] is False and result["status"] == "partial"


def test_mirrored_new_wrong_and_legacy_wrongs_count_one_missed_word():
    wrong_at = WHEN + timedelta(minutes=30)
    item = word(incorrect_at=wrong_at)
    result = merged([item], [practice(item, correct=False)], {item.id: [WHEN, wrong_at]})
    assert result["missed_count"] == result["attempted_count"] == 1
    assert result["completed_count"] == 0


def test_legacy_misses_are_deduplicated_in_the_users_local_day():
    same_local_day = WHEN + timedelta(hours=2)
    next_local_day = WHEN + timedelta(hours=8)
    item = word(incorrect_at=next_local_day)
    result = merged(
        [item],
        [practice(item)],
        {item.id: [same_local_day, next_local_day]},
        timezone="America/Los_Angeles",
    )
    assert result["date"] == "2026-09-05"
    assert result["missed_count"] == 1 and result["completed_count"] == 0
    next_day_only = merged(
        [item], [practice(item)], {item.id: [next_local_day]}, timezone="America/Los_Angeles"
    )
    assert next_day_only["missed_count"] == 0


def test_legacy_only_words_keep_historical_completion_compatibility():
    partial, legacy = word(), word(incorrect_at=WHEN)
    result = merged([partial, legacy], [practice(partial)], {legacy.id: [WHEN]})
    assert result["attempted_count"] == 2
    assert result["missed_count"] == result["completed_count"] == 1

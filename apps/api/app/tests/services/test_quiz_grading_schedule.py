"""SM-2 / remaster scheduling lives in quiz_grading, not the repository."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.projects import quiz_grading


def _item(*, status: str = "new", created_at: datetime | None = None):
    item = MagicMock()
    item.id = MagicMock()
    item.user_id = MagicMock()
    item.status = status
    item.mastered = status == "mastered"
    item.mastered_at = None
    item.last_incorrect_at = None
    item.created_at = created_at or datetime.now(UTC)
    item.quiz_attempts = 0
    item.quiz_correct = 0
    item.ease_factor = 2.5
    item.interval_days = 0
    item.review_count = 0
    item.due_at = None
    item.last_reviewed_at = None
    return item


def _frozen_datetime_cls(moment: datetime) -> type[datetime]:
    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment

    return _Frozen


@pytest.mark.asyncio
async def test_apply_quiz_result_remaster_after_demotion_refreshes_mastered_at(
    monkeypatch,
):
    """BUG FIX (was silent): mastered_at only backfilled when None, so an item mastered
    on Day 1, demoted by a later miss, then re-mastered on Day 10 kept mastered_at
    stuck at Day 1 — mastered_today/streaks/daily history all missed the remastery."""
    day1 = datetime(2026, 1, 1, 9, tzinfo=UTC)
    demotion_day = day1 + timedelta(days=5)
    day10 = datetime(2026, 1, 10, 15, tzinfo=UTC)

    item = _item(status="new", created_at=day1)
    fake_session = AsyncMock()

    async def _persist(session, item, **kwargs):
        from app.repositories.project_items import _sync_mastered_fields

        _sync_mastered_fields(
            item,
            kwargs["new_status"],
            prior_status=kwargs["prior_status"],
            now=kwargs["now"],
        )
        item.last_reviewed_at = kwargs["now"]
        item.review_count = kwargs["review_count"]
        item.ease_factor = kwargs["ease_factor"]
        item.interval_days = kwargs["interval_days"]
        item.due_at = kwargs["due_at"]
        if not kwargs["is_correct"]:
            item.last_incorrect_at = kwargs["now"]
        return item

    monkeypatch.setattr(quiz_grading.project_items_repo, "apply_quiz_result", _persist)

    monkeypatch.setattr(quiz_grading, "datetime", _frozen_datetime_cls(day1))
    await quiz_grading.apply_quiz_result(fake_session, item, is_correct=True, commit=False)
    assert item.status == "mastered"
    assert item.mastered_at == day1

    monkeypatch.setattr(quiz_grading, "datetime", _frozen_datetime_cls(demotion_day))
    await quiz_grading.apply_quiz_result(fake_session, item, is_correct=False, commit=False)
    assert item.status == "learning"
    assert item.mastered_at == day1

    monkeypatch.setattr(quiz_grading, "datetime", _frozen_datetime_cls(day10))
    await quiz_grading.apply_quiz_result(fake_session, item, is_correct=True, commit=False)
    assert item.status == "mastered"
    assert item.mastered_at == day10

    from app.services import daily_learning

    monkeypatch.setattr(
        daily_learning,
        "start_of_today_utc",
        lambda timezone_name: day10.replace(hour=0, minute=0, second=0, microsecond=0),
    )
    mastered_today, missed_today, _pending = daily_learning.count_today_vocab_stats(
        [item], timezone_name="UTC"
    )
    assert mastered_today == 1
    assert missed_today == 0

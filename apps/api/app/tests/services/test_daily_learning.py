from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.services.daily_learning import (
    build_daily_history,
    count_today_vocab_stats,
    daily_home_cue,
    group_mastered_items_by_date,
    start_of_today_utc,
)


def _item(
    *,
    status: str = "new",
    created_at: datetime,
    mastered_at: datetime | None = None,
    mastered: bool = False,
):
    return SimpleNamespace(
        status=status,
        mastered=mastered,
        created_at=created_at,
        mastered_at=mastered_at,
    )


def test_start_of_today_utc_uses_timezone():
    start = start_of_today_utc("UTC")
    now = datetime.now(UTC)
    assert start <= now
    assert (now - start).total_seconds() < 86400


def test_count_today_vocab_stats_mastered_and_pending():
    start = start_of_today_utc("UTC")
    items = [
        _item(
            status="mastered",
            mastered=True,
            created_at=start,
            mastered_at=start,
        ),
        _item(status="new", created_at=start),
        _item(
            status="learning",
            created_at=start,
        ),
        _item(
            status="mastered",
            mastered=True,
            created_at=start.replace(year=start.year - 1),
            mastered_at=start.replace(year=start.year - 1),
        ),
    ]
    mastered_today, pending_today = count_today_vocab_stats(items, timezone_name="UTC")
    assert mastered_today == 1
    assert pending_today == 2


def test_daily_home_cue_hides_when_goal_met():
    tz = ZoneInfo("UTC")
    assert (
        daily_home_cue(
            total=10,
            mastered_today=5,
            pending_today=0,
            learning_count=2,
            due_for_review=1,
            daily_goal=5,
            last_mastery=datetime.now(UTC),
            home_tz=tz,
        )
        is None
    )


def test_daily_home_cue_continue_and_missed():
    tz = ZoneInfo("UTC")
    assert (
        daily_home_cue(
            total=10,
            mastered_today=2,
            pending_today=0,
            learning_count=0,
            due_for_review=0,
            daily_goal=5,
            last_mastery=datetime.now(UTC),
            home_tz=tz,
        )
        == "continue"
    )
    old = datetime.now(tz) - timedelta(days=3)
    assert (
        daily_home_cue(
            total=10,
            mastered_today=0,
            pending_today=0,
            learning_count=0,
            due_for_review=0,
            daily_goal=5,
            last_mastery=old,
            home_tz=tz,
        )
        == "missed_yesterday"
    )


def test_daily_home_cue_continue_when_quiz_pending():
    tz = ZoneInfo("UTC")
    assert (
        daily_home_cue(
            total=10,
            mastered_today=0,
            pending_today=0,
            quiz_pending_today=3,
            learning_count=0,
            due_for_review=0,
            daily_goal=5,
            last_mastery=datetime.now(UTC),
            home_tz=tz,
        )
        == "continue"
    )


def test_daily_home_cue_not_started_when_due_words_but_zero_today():
    tz = ZoneInfo("UTC")
    assert (
        daily_home_cue(
            total=10,
            mastered_today=0,
            pending_today=0,
            learning_count=4,
            due_for_review=3,
            daily_goal=5,
            last_mastery=datetime.now(UTC),
            home_tz=tz,
        )
        == "not_started_today"
    )


def test_group_mastered_items_by_date():
    tz = ZoneInfo("UTC")
    today = datetime.now(tz).date()
    yesterday = today - timedelta(days=1)
    today_at = datetime.combine(today, datetime.min.time(), tzinfo=tz).astimezone(UTC)
    yesterday_at = datetime.combine(yesterday, datetime.min.time(), tzinfo=tz).astimezone(UTC)
    items = [
        _item(
            status="mastered",
            mastered=True,
            created_at=yesterday_at,
            mastered_at=yesterday_at,
        ),
        _item(
            status="mastered",
            mastered=True,
            created_at=today_at,
            mastered_at=today_at,
        ),
        _item(status="new", created_at=today_at),
    ]
    grouped = group_mastered_items_by_date(items, timezone_name="UTC", days=14)
    assert len(grouped[yesterday.isoformat()]) == 1
    assert len(grouped[today.isoformat()]) == 1


def test_build_daily_history_complete_partial_and_skipped():
    tz = ZoneInfo("UTC")
    today = datetime.now(tz).date()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    start = datetime.combine(two_days_ago, datetime.min.time(), tzinfo=tz).astimezone(UTC)
    items = [
        _item(
            status="mastered",
            mastered=True,
            created_at=start,
            mastered_at=datetime.combine(yesterday, datetime.min.time(), tzinfo=tz).astimezone(UTC),
        ),
        _item(
            status="mastered",
            mastered=True,
            created_at=start,
            mastered_at=datetime.combine(yesterday, datetime.min.time(), tzinfo=tz).astimezone(UTC),
        ),
        _item(
            status="mastered",
            mastered=True,
            created_at=start,
            mastered_at=datetime.combine(today, datetime.min.time(), tzinfo=tz).astimezone(UTC),
        ),
    ]
    history = build_daily_history(
        items,
        timezone_name="UTC",
        daily_goal=5,
        active_since=start,
        days=3,
    )
    assert len(history) == 3
    assert history[0]["status"] == "skipped"
    assert history[1]["status"] == "partial"
    assert history[1]["mastered_count"] == 2
    assert history[2]["status"] == "today"
    assert history[2]["mastered_count"] == 1

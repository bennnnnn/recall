from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.services.daily_learning import (
    append_daily_goal_history,
    build_daily_history,
    count_today_vocab_stats,
    daily_home_cue,
    day_goal_for_history,
    goal_effective_on_date,
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


def test_build_daily_history_includes_missed_counts():
    tz = ZoneInfo("UTC")
    today = datetime.now(tz).date()
    start = datetime.combine(today - timedelta(days=2), datetime.min.time(), tzinfo=tz).astimezone(
        UTC
    )
    wrong_at = (
        datetime.combine(today, datetime.min.time(), tzinfo=tz).replace(hour=12).astimezone(UTC)
    )

    class Item:
        status = "learning"
        mastered = False
        mastered_at = None
        created_at = start
        last_incorrect_at = wrong_at

    history = build_daily_history(
        [Item()],
        timezone_name="UTC",
        daily_goal=5,
        active_since=start,
        days=3,
    )
    assert history[-1]["missed_count"] == 1


def test_goal_effective_on_date_uses_history_segments():
    history = [
        {"effective_from": "2026-07-07", "goal": 5},
        {"effective_from": "2026-07-08", "goal": 10},
    ]
    assert goal_effective_on_date(history, date(2026, 7, 7), fallback=10) == 5
    assert goal_effective_on_date(history, date(2026, 7, 8), fallback=5) == 10
    assert goal_effective_on_date(history, date(2026, 7, 9), fallback=5) == 10


def test_build_daily_history_keeps_past_goal_after_increase():
    tz = ZoneInfo("UTC")
    today = datetime.now(tz).date()
    monday = today - timedelta(days=1)
    active = datetime.combine(
        monday - timedelta(days=1), datetime.min.time(), tzinfo=tz
    ).astimezone(UTC)
    monday_at = datetime.combine(monday, datetime.min.time(), tzinfo=tz).astimezone(UTC)
    items = [
        _item(
            status="mastered",
            mastered=True,
            created_at=active,
            mastered_at=monday_at,
        )
        for _ in range(5)
    ]
    history = [
        {"effective_from": monday.isoformat(), "goal": 5},
        {"effective_from": today.isoformat(), "goal": 10},
    ]
    rows = build_daily_history(
        items,
        timezone_name="UTC",
        daily_goal=10,
        active_since=active,
        daily_goal_history=history,
        days=2,
    )
    monday_row = rows[0]
    today_row = rows[1]
    assert monday_row["date"] == monday.isoformat()
    assert monday_row["daily_goal"] == 5
    assert monday_row["goal_met"] is True
    assert monday_row["status"] == "complete"
    assert today_row["daily_goal"] == 10
    assert today_row["goal_met"] is False


def test_append_daily_goal_history_records_change_from_today():
    created = datetime(2026, 7, 7, 12, tzinfo=UTC)
    history = append_daily_goal_history(
        [{"effective_from": "2026-07-07", "goal": 5}],
        old_goal=5,
        new_goal=10,
        project_created=created,
        effective_from=date(2026, 7, 8),
        timezone_name="UTC",
    )
    assert history == [
        {"effective_from": "2026-07-07", "goal": 5},
        {"effective_from": "2026-07-08", "goal": 10},
    ]


def test_day_goal_for_history_honors_exact_prior_tier_completion():
    tz = ZoneInfo("UTC")
    today = datetime.now(tz).date()
    monday = today - timedelta(days=2)
    history = [{"effective_from": monday.isoformat(), "goal": 10}]
    assert (
        day_goal_for_history(
            count=5,
            day=monday,
            today=today,
            history=history,
            current_goal=10,
        )
        == 5
    )
    assert (
        day_goal_for_history(
            count=8,
            day=monday,
            today=today,
            history=history,
            current_goal=10,
        )
        == 10
    )


def test_build_daily_history_marks_exact_prior_day_complete_without_logged_change():
    tz = ZoneInfo("UTC")
    today = datetime.now(tz).date()
    saturday = today - timedelta(days=6)
    active = datetime.combine(
        saturday - timedelta(days=1), datetime.min.time(), tzinfo=tz
    ).astimezone(UTC)
    saturday_at = datetime.combine(saturday, datetime.min.time(), tzinfo=tz).astimezone(UTC)
    items = [
        _item(
            status="mastered",
            mastered=True,
            created_at=active,
            mastered_at=saturday_at,
        )
        for _ in range(5)
    ]
    rows = build_daily_history(
        items,
        timezone_name="UTC",
        daily_goal=10,
        active_since=active,
        daily_goal_history=[{"effective_from": active.date().isoformat(), "goal": 10}],
        days=7,
    )
    saturday_row = next(row for row in rows if row["date"] == saturday.isoformat())
    assert saturday_row["daily_goal"] == 5
    assert saturday_row["goal_met"] is True
    assert saturday_row["status"] == "complete"

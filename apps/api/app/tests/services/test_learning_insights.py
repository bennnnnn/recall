from uuid import uuid4

from app.services import learning_insights


def test_compute_streak_counts_recent_goal_met_days():
    history = [
        {"status": "inactive", "goal_met": False},
        {"status": "skipped", "goal_met": False},
        {"status": "complete", "goal_met": True},
        {"status": "complete", "goal_met": True},
        {"status": "today", "goal_met": True},
    ]
    assert learning_insights.compute_streak_days(history) == 3


def test_compute_streak_stops_at_a_gap_two_days_back_even_when_today_is_in_progress():
    """BUG FIX (was silent): a `saw_today` flag that stayed True forever let unmet days
    past a real gap keep counting once today's (unmet, in-progress) entry was seen.
    Wed(complete) Thu(skipped) Fri(complete) Sat(complete) Sun=today(not yet met) must
    report streak=2 (Sat, Fri) — Thu's gap should break the walk, not just Sun's."""
    history = [
        {"status": "complete", "goal_met": True},  # Wed
        {"status": "skipped", "goal_met": False},  # Thu — real gap, two days before today
        {"status": "complete", "goal_met": True},  # Fri
        {"status": "complete", "goal_met": True},  # Sat
        {"status": "today", "goal_met": False},  # Sun — today, still in progress
    ]
    assert learning_insights.compute_streak_days(history) == 2


def test_pick_learning_nudge_prefers_incomplete_daily_goal():
    class P:
        kind = "language"
        title = "English"
        id = uuid4()

    stats = {
        "total": 20,
        "mastered_today": 2,
        "due_for_review": 5,
        "new_count": 3,
        "days_inactive": 3,
    }
    picked = learning_insights.pick_learning_nudge(P(), stats, daily_goal=10)
    assert picked is not None
    body, score, nudge_type, _payload = picked
    assert nudge_type == "learning_daily_goal"
    assert "2/10" in body
    assert "3 days" in body
    assert score > 10


def test_pick_learning_nudge_returns_none_when_fully_idle():
    """Goal met, nothing due for review, no new items — there is genuinely
    nothing to nudge about, so pick_learning_nudge must return None."""

    class P:
        kind = "language"
        title = "English"
        id = uuid4()

    stats = {
        "total": 20,
        "mastered_today": 10,
        "missed_today": 0,
        "due_for_review": 0,
        "new_count": 0,
        "days_inactive": 0,
    }
    assert learning_insights.pick_learning_nudge(P(), stats, daily_goal=10) is None


def test_pick_learning_nudge_stays_silent_once_goal_met_even_with_review_or_new_items():
    """Product decision: goal met means done for the day — pick_learning_nudge
    used to fall through past the goal-met check into a "N due for review" or
    "N new words" nudge; that fallthrough is gone, so a met goal must return
    None regardless of due_for_review/new_count."""

    class P:
        kind = "language"
        title = "English"
        id = uuid4()

    stats = {
        "total": 20,
        "mastered_today": 10,
        "missed_today": 0,
        "due_for_review": 5,
        "new_count": 3,
        "days_inactive": 0,
    }
    assert learning_insights.pick_learning_nudge(P(), stats, daily_goal=10) is None


def test_suggest_level_change_promotes_high_mastery():
    class P:
        kind = "language"
        level = "level2"

    stats = {
        "total": 40,
        "mastered_count": 36,
        "learning_count": 3,
        "new_count": 1,
        "quiz_accuracy_pct": 82,
    }
    assert learning_insights.suggest_level_change(P(), stats) == "up"

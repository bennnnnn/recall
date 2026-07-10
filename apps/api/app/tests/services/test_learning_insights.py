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

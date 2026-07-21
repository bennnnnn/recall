from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services import home as home_service


def _user(**kwargs):
    u = MagicMock()
    u.id = kwargs.get("id", uuid4())
    u.name = kwargs.get("name", "Alex")
    u.timezone = kwargs.get("timezone", "UTC")
    u.memory_enabled = kwargs.get("memory_enabled", True)
    return u


def _todo(content: str, *, minutes_from_now: int, topic: str = "Work"):
    item = MagicMock()
    item.id = uuid4()
    item.content = content
    item.topic = topic
    due = datetime.now(UTC) + timedelta(minutes=minutes_from_now)
    item.due_at = due
    item.checked = False
    return item


def _project(title: str = "Learning English", *, total: int = 5, daily_goal: int = 5):
    project = MagicMock()
    project.id = uuid4()
    project.title = title
    project.description = None
    project.kind = "language"
    project.level = "level2"
    project.daily_goal = daily_goal
    return project


def _general_project(title: str = "General knowledge"):
    project = MagicMock()
    project.id = uuid4()
    project.title = title
    project.description = None
    project.kind = "research"
    project.level = None
    return project


def _trivia_project(title: str = "General knowledge", *, daily_goal: int = 5):
    project = MagicMock()
    project.id = uuid4()
    project.title = title
    project.description = "history,science"
    project.kind = "trivia"
    project.level = "level1"
    project.daily_goal = daily_goal
    return project


def _fake_session_local():
    """Stand-in for home_service.SessionLocal: each call yields a fresh
    AsyncMock session, mirroring the real per-loader sessions without
    touching a database."""

    def _make():
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=AsyncMock())
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    return MagicMock(side_effect=_make)


@contextmanager
def _home_patches(**overrides):
    defaults = {
        "list_due_soon": [],
        "list_for_user_chats": [],
        "list_active_suggestions": [],
        "load_relevant_memories": [],
        "list_projects": [],
        # Unpatched calendar/gmail AsyncMocks look "connected" and emit chips,
        # which incorrectly marks a cold account as warm.
        "integration_starters": [],
        "count_project_stats": {
            "total": 0,
            "new_count": 0,
            "learning_count": 0,
            "mastered_count": 0,
            "added_this_week": 0,
            "due_for_review": 0,
            "mastered_today": 0,
            "missed_today": 0,
            "pending_today": 0,
            "last_mastery_at": None,
        },
    }
    defaults.update(overrides)
    stats_payload = defaults["count_project_stats"]

    async def _count_stats_by_project(_session, project_ids, *, timezone_by_project=None):
        return {pid: stats_payload for pid in project_ids}

    with (
        patch.object(home_service, "SessionLocal", _fake_session_local()),
        patch.object(
            home_service.todos_repo,
            "list_due_soon",
            AsyncMock(return_value=defaults["list_due_soon"]),
        ),
        patch.object(
            home_service.chats_repo,
            "list_for_user",
            AsyncMock(return_value=defaults["list_for_user_chats"]),
        ),
        patch.object(
            home_service.suggestions_repo,
            "list_active",
            AsyncMock(return_value=defaults["list_active_suggestions"]),
        ),
        patch.object(
            home_service.memory_service,
            "load_relevant_memories",
            AsyncMock(return_value=defaults["load_relevant_memories"]),
        ),
        patch.object(
            home_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=defaults["list_projects"]),
        ),
        patch.object(
            home_service.project_items_repo,
            "list_for_projects",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.projects.stats.stats_from_items",
            MagicMock(return_value=stats_payload),
        ),
        patch.object(
            home_service.project_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            home_service,
            "integration_starters",
            AsyncMock(return_value=defaults["integration_starters"]),
        ),
    ):
        yield


@pytest.mark.asyncio
async def test_build_home_screen_never_overlaps_ops_on_one_session():
    """Core home loaders run concurrently; each concurrent loader must use its
    own session (asyncpg raises InterfaceError on overlap). Memories/chats load
    only when there is no project highlight — still on separate sessions.
    """
    import asyncio

    session = AsyncMock()
    user = _user()
    busy: set[int] = set()
    violations: list[str] = []

    def tracked(name: str, result):
        async def impl(s, *args, **kwargs):
            sid = id(s)
            if sid in busy:
                violations.append(name)
            busy.add(sid)
            await asyncio.sleep(0)  # yield so gathered loaders interleave
            busy.discard(sid)
            return result

        return impl

    empty_project_content = home_service.ProjectHomeContent([], None, None, [], False)
    memories_mock = AsyncMock(side_effect=tracked("memories", []))
    chats_mock = AsyncMock(side_effect=tracked("chats", []))
    with (
        patch.object(home_service, "SessionLocal", _fake_session_local()),
        patch.object(
            home_service.todos_repo,
            "list_due_soon",
            AsyncMock(side_effect=tracked("todos", [])),
        ),
        patch.object(
            home_service.memory_service,
            "load_relevant_memories",
            memories_mock,
        ),
        patch.object(
            home_service.chats_repo,
            "list_for_user",
            chats_mock,
        ),
        patch.object(
            home_service.suggestions_repo,
            "list_active",
            AsyncMock(side_effect=tracked("suggestions", [])),
        ),
        patch.object(
            home_service,
            "load_project_home_content",
            AsyncMock(side_effect=tracked("projects", empty_project_content)),
        ),
        patch.object(
            home_service,
            "integration_starters",
            AsyncMock(side_effect=tracked("integrations", [])),
        ),
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert violations == []
    assert screen.greeting
    memories_mock.assert_awaited()
    chats_mock.assert_awaited()


@pytest.mark.asyncio
async def test_build_home_skips_memories_when_highlight_present():
    session = AsyncMock()
    user = _user()
    project = _project()
    memories_mock = AsyncMock(return_value=[])
    chats_mock = AsyncMock(return_value=[])

    with (
        _home_patches(
            list_projects=[project],
            count_project_stats={
                "total": 5,
                "new_count": 2,
                "learning_count": 1,
                "mastered_count": 0,
                "added_this_week": 0,
                "due_for_review": 2,
                "mastered_today": 0,
                "missed_today": 0,
                "pending_today": 0,
                "last_mastery_at": None,
            },
        ),
        patch.object(
            home_service.memory_service,
            "load_relevant_memories",
            memories_mock,
        ),
        patch.object(
            home_service.chats_repo,
            "list_for_user",
            chats_mock,
        ),
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert screen.project_highlight is not None
    memories_mock.assert_not_awaited()
    chats_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_build_home_suggestion_starters_include_id():
    session = AsyncMock()
    user = _user()
    suggestion = MagicMock()
    suggestion.id = uuid4()
    suggestion.text = "Try a 5-minute reflection"

    with _home_patches(list_active_suggestions=[suggestion]):
        screen = await home_service.build_home_screen(session, user, Settings())

    match = next(s for s in screen.starters if "reflection" in s.prompt.lower())
    assert match.id == str(suggestion.id)


@pytest.mark.asyncio
async def test_build_home_includes_urgent_todo():
    session = AsyncMock()
    user = _user()
    urgent = _todo("Pay rent", minutes_from_now=30)

    with _home_patches(list_due_soon=[urgent]):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert len(screen.urgent_todos) == 1
    assert screen.urgent_todos[0].content == "Pay rent"
    assert "Pay rent" in (screen.subtitle or "")
    assert not any(s.kind == "todo" for s in screen.starters)


@pytest.mark.asyncio
async def test_home_urgent_window_uses_user_lead():
    session = AsyncMock()
    user = _user()
    user.reminder_lead_minutes = 30

    with _home_patches(list_due_soon=[]):
        await home_service.build_home_screen(session, user, Settings())
        before_utc = home_service.todos_repo.list_due_soon.call_args.kwargs.get("before_utc")

    assert before_utc is not None
    delta_min = (before_utc - datetime.now(UTC)).total_seconds() / 60
    assert 25 <= delta_min <= 35  # ~now + 30 min lead


@pytest.mark.asyncio
async def test_home_urgent_window_defaults_to_10_min_when_lead_unset():
    session = AsyncMock()
    user = _user()
    user.reminder_lead_minutes = None

    with _home_patches(list_due_soon=[]):
        await home_service.build_home_screen(session, user, Settings())
        before_utc = home_service.todos_repo.list_due_soon.call_args.kwargs.get("before_utc")

    assert before_utc is not None
    delta_min = (before_utc - datetime.now(UTC)).total_seconds() / 60
    assert 7 <= delta_min <= 13  # default lead = 10 min


@pytest.mark.asyncio
async def test_build_home_greeting_uses_name():
    session = AsyncMock()
    user = _user(name="Sam")

    with _home_patches():
        screen = await home_service.build_home_screen(session, user, Settings())

    assert "Sam" in screen.greeting
    assert len(screen.starters) >= 2


@pytest.mark.asyncio
async def test_build_home_language_project_starters():
    session = AsyncMock()
    user = _user()
    project = _project()

    with _home_patches(
        list_projects=[project],
        count_project_stats={
            "total": 3,
            "new_count": 2,
            "learning_count": 1,
            "mastered_count": 0,
            "added_this_week": 0,
            "due_for_review": 2,
        },
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    kinds = {s.kind for s in screen.starters}
    starter_texts = {s.text for s in screen.starters}
    assert screen.project_highlight is not None
    assert screen.project_highlight.title == "Learning English"
    assert screen.project_highlight.kind == "language"
    assert screen.project_highlight.daily_goal == 5
    assert screen.project_highlight.cue == "not_started_today"
    assert "Review Learning English" not in starter_texts
    assert "Start Learning English" not in starter_texts
    assert "chat" not in kinds
    assert "memory" not in kinds
    assert screen.subtitle is None


@pytest.mark.asyncio
async def test_build_home_highlight_skips_duplicate_starters():
    session = AsyncMock()
    user = _user()
    project = _project()
    chat = MagicMock()
    chat.title = "English vocabulary practice"
    memory = MagicMock()
    memory.type = "project"
    memory.text = "User is actively engaged in vocabulary expansion"

    with _home_patches(
        list_projects=[project],
        list_for_user_chats=[chat],
        load_relevant_memories=[memory],
        count_project_stats={
            "total": 10,
            "new_count": 3,
            "learning_count": 4,
            "mastered_count": 3,
            "added_this_week": 1,
            "due_for_review": 7,
        },
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert screen.project_highlight is not None
    starter_texts = {s.text for s in screen.starters}
    assert "Pick up where we left off" not in starter_texts
    assert "Keep building" not in starter_texts
    assert "Practice English" not in starter_texts


@pytest.mark.asyncio
async def test_build_home_language_review_chip_when_due():
    session = AsyncMock()
    user = _user()
    project = _project()

    with _home_patches(
        list_projects=[project],
        count_project_stats={
            "total": 10,
            "new_count": 2,
            "learning_count": 4,
            "mastered_count": 3,
            "added_this_week": 1,
            "due_for_review": 4,
            "mastered_today": 2,
        },
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert screen.project_highlight is not None
    assert screen.project_highlight.cue == "continue"
    assert screen.project_highlight.mastered_today == 2
    assert screen.project_highlight.missed_today == 0
    starter_texts = {s.text for s in screen.starters}
    assert "Review Learning English" not in starter_texts
    assert "Continue Learning English" not in starter_texts


@pytest.mark.asyncio
async def test_build_home_hides_vocab_card_when_daily_goal_met():
    session = AsyncMock()
    user = _user()
    project = _project(daily_goal=5)
    memory = MagicMock()
    memory.type = "project"
    memory.text = (
        "User initiated an 'English · Beginner' vocabulary learning project with a "
        "daily goal of mastering 5 new high-frequency words per session."
    )

    with _home_patches(
        list_projects=[project],
        load_relevant_memories=[memory],
        count_project_stats={
            "total": 12,
            "new_count": 2,
            "learning_count": 0,
            "mastered_count": 10,
            "added_this_week": 5,
            "due_for_review": 3,
            "mastered_today": 5,
            "pending_today": 0,
            "last_mastery_at": datetime.now(UTC).isoformat(),
        },
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert screen.project_highlight is None
    starter_texts = {s.text for s in screen.starters}
    assert "Review Learning English" not in starter_texts
    assert "Practice Learning English" not in starter_texts
    assert "Keep building" not in starter_texts
    assert "Practice English" not in starter_texts


@pytest.mark.asyncio
async def test_build_home_trivia_project_shows_card_when_incomplete():
    session = AsyncMock()
    user = _user()
    project = _trivia_project()

    with _home_patches(
        list_projects=[project],
        count_project_stats={
            "total": 4,
            "new_count": 0,
            "learning_count": 1,
            "mastered_count": 3,
            "added_this_week": 2,
            "due_for_review": 0,
            "mastered_today": 2,
            "pending_today": 0,
            "last_mastery_at": datetime.now(UTC).isoformat(),
        },
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert screen.project_highlight is not None
    assert screen.project_highlight.kind == "trivia"
    assert screen.project_highlight.cue == "continue"
    assert screen.project_highlight.mastered_today == 2
    starter_texts = {s.text for s in screen.starters}
    assert "Continue General knowledge" not in starter_texts


@pytest.mark.asyncio
async def test_build_home_hides_trivia_card_when_daily_goal_met():
    session = AsyncMock()
    user = _user()
    project = _trivia_project(daily_goal=5)

    with _home_patches(
        list_projects=[project],
        count_project_stats={
            "total": 20,
            "new_count": 0,
            "learning_count": 0,
            "mastered_count": 20,
            "added_this_week": 5,
            "due_for_review": 0,
            "mastered_today": 5,
            "pending_today": 0,
            "last_mastery_at": datetime.now(UTC).isoformat(),
        },
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert screen.project_highlight is None
    starter_texts = {s.text for s in screen.starters}
    assert "Continue General knowledge" not in starter_texts
    assert "Quiz me on General knowledge" not in starter_texts


@pytest.mark.asyncio
async def test_build_home_prefers_language_when_both_need_nudging():
    session = AsyncMock()
    user = _user()
    language = _project()
    trivia = _trivia_project()

    with _home_patches(
        list_projects=[trivia, language],
        count_project_stats={
            "total": 3,
            "new_count": 2,
            "learning_count": 1,
            "mastered_count": 0,
            "added_this_week": 0,
            "due_for_review": 1,
            "mastered_today": 0,
            "pending_today": 0,
            "last_mastery_at": None,
        },
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert screen.project_highlight is not None
    assert screen.project_highlight.kind == "language"
    assert screen.project_highlight.title == "Learning English"


@pytest.mark.asyncio
async def test_build_home_batches_daily_project_stats():
    session = AsyncMock()
    user = _user()
    language = _project()
    trivia = _trivia_project()

    with (
        patch.object(home_service, "SessionLocal", _fake_session_local()),
        patch.object(
            home_service.todos_repo,
            "list_due_soon",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            home_service.chats_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            home_service.suggestions_repo,
            "list_active",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            home_service.memory_service,
            "load_relevant_memories",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            home_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=[trivia, language]),
        ),
        patch.object(
            home_service.project_items_repo,
            "list_for_projects",
            AsyncMock(return_value=[]),
        ) as items_mock,
        patch(
            "app.services.projects.stats.stats_from_items",
            MagicMock(
                return_value={
                    "total": 3,
                    "new_count": 2,
                    "learning_count": 1,
                    "mastered_count": 0,
                    "added_this_week": 0,
                    "due_for_review": 1,
                    "mastered_today": 0,
                    "missed_today": 0,
                    "pending_today": 0,
                    "last_mastery_at": None,
                }
            ),
        ),
    ):
        await home_service.build_home_screen(session, user, Settings())

    items_mock.assert_awaited_once()
    assert set(items_mock.await_args.args[1]) == {language.id, trivia.id}


@pytest.mark.asyncio
async def test_build_home_ignores_legacy_non_daily_projects():
    """Legacy programming/general projects must not become FOR YOU chips."""
    session = AsyncMock()
    user = _user()
    project = _general_project(title="TypeScript · Programming")
    chat = MagicMock()
    chat.title = "TypeScript chapter 1"
    memory = MagicMock()
    memory.type = "project"
    memory.text = "User is learning TypeScript"

    with _home_patches(
        list_projects=[project],
        list_for_user_chats=[chat],
        load_relevant_memories=[memory],
        count_project_stats={
            "total": 0,
            "new_count": 0,
            "learning_count": 0,
            "mastered_count": 0,
            "added_this_week": 0,
            "due_for_review": 0,
        },
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    starter_texts = {s.text for s in screen.starters}
    assert "Start TypeScript · Programming" not in starter_texts
    assert "Continue TypeScript · Programming" not in starter_texts
    assert not any("TypeScript" in t for t in starter_texts)


def test_time_starters_vary_by_hour():
    user = _user()
    tz = home_service._resolve_home_tz(user, "UTC")
    with patch("app.services.home.time_starters.local_hour_for_tz", side_effect=[8, 16]):
        morning = home_service._time_starters(user, tz)
        afternoon = home_service._time_starters(user, tz)
    assert morning[0].text != afternoon[0].text
    assert morning[0].text == "Plan my day"
    assert afternoon[0].text == "How did today go?"


def test_time_starters_reflect_starts_at_three_pm():
    user = _user()
    tz = home_service._resolve_home_tz(user, "UTC")
    with patch("app.services.home.time_starters.local_hour_for_tz", return_value=14):
        before = home_service._time_starters(user, tz)
    with patch("app.services.home.time_starters.local_hour_for_tz", return_value=15):
        after = home_service._time_starters(user, tz)
    assert before[0].text == "What are you working on?"
    assert after[0].text == "How did today go?"


@pytest.mark.asyncio
async def test_build_home_cold_user_gets_welcome_not_day_reflect():
    """Brand-new account: no chats/projects/memory/urgents → welcome chips only."""
    session = AsyncMock()
    user = _user()

    with (
        _home_patches(),
        patch("app.services.home.time_starters.local_hour_for_tz", return_value=20),
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    texts = {s.text for s in screen.starters}
    assert "Help me think" in texts
    assert "What can you do?" in texts
    assert "How did today go?" not in texts
    assert "Anything left tonight?" not in texts
    assert "Plan my day" not in texts
    assert all(s.kind != "time" for s in screen.starters)


@pytest.mark.asyncio
async def test_build_home_with_chat_history_keeps_time_starters():
    session = AsyncMock()
    user = _user()
    chat = MagicMock()
    chat.title = "Yesterday's notes"

    with (
        _home_patches(list_for_user_chats=[chat]),
        patch("app.services.home.time_starters.local_hour_for_tz", return_value=20),
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert any(s.kind == "time" for s in screen.starters)
    assert any(s.text in {"How did today go?", "Anything left tonight?"} for s in screen.starters)


def test_client_timezone_overrides_profile():
    user = _user(timezone="UTC")
    tz = home_service._resolve_home_tz(user, "America/New_York")
    assert str(tz) == "America/New_York"


def test_memory_blocked_when_language_daily_goal_met():
    memory = MagicMock()
    memory.type = "project"
    memory.text = (
        "User initiated an 'English · Beginner' vocabulary learning project with a "
        "daily goal of mastering 5 new words per session."
    )
    completed = [("English · Beginner", "language")]
    assert home_service._memory_blocked_by_completed_daily(memory, completed) is True


def test_memory_starter_skips_profile_name_facts():
    memory = MagicMock()
    memory.type = "profile"
    memory.text = "User's name is Binalfew"
    assert home_service._memory_starter(memory) is None


def test_memory_starter_skips_sensitive_health_facts():
    memory = MagicMock()
    memory.type = "focus"
    memory.text = "Has a peanut allergy and sees a therapist weekly"
    assert home_service._memory_starter(memory) is None


def test_pick_home_memory_skips_sensitive_sections():
    allergy = MagicMock()
    allergy.type = "focus"
    allergy.text = "Diagnosed with anxiety last year"
    project = MagicMock()
    project.type = "project"
    project.text = "Building a recipe app"
    picked = home_service.pick_home_memory([allergy, project])
    assert picked is project


def test_memory_starter_english_learning_uses_specific_label():
    memory = MagicMock()
    memory.type = "focus"
    memory.text = "User is learning English"
    starter = home_service._memory_starter(memory)
    assert starter is not None
    assert starter.text == "Practice English"
    assert "English learning" in starter.prompt


def test_memory_starter_profile_english_learning():
    memory = MagicMock()
    memory.type = "profile"
    memory.text = "User is learning English vocabulary"
    starter = home_service._memory_starter(memory)
    assert starter is not None
    assert starter.text == "Practice English"


@pytest.mark.asyncio
async def test_build_home_hides_practice_english_without_language_project():
    """Stale English memories must not show Practice English after class delete."""
    session = AsyncMock()
    user = _user()
    memory = MagicMock()
    memory.type = "focus"
    memory.text = "User is learning English vocabulary"
    suggestion = MagicMock()
    suggestion.id = uuid4()
    suggestion.text = "Practice English vocabulary for 10 minutes"

    with _home_patches(
        load_relevant_memories=[memory],
        list_active_suggestions=[suggestion],
        list_projects=[],
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    starter_texts = {s.text for s in screen.starters}
    assert "Practice English" not in starter_texts
    assert not any("English" in s.text for s in screen.starters)
    assert not any("vocabulary" in (s.prompt or "").lower() for s in screen.starters)


def test_chat_starter_uses_friendly_label():
    match = home_service._chat_starter(["Binalfew Software Engineer Context"])
    assert match is not None
    starter, title = match
    assert starter.text == "Pick up where we left off"
    assert "Software Engineer" in starter.prompt
    assert title == "Binalfew Software Engineer Context"


def test_texts_overlap_matches_project_and_chat():
    assert home_service._texts_overlap("General knowledge", "General knowledge quiz")
    assert home_service._texts_overlap(
        "General knowledge",
        "User is actively engaged in General knowledge",
    )


def test_chat_starter_skips_project_overlap():
    match = home_service._chat_starter(
        ["General knowledge practice"],
        skip_overlapping=["General knowledge"],
    )
    assert match is None


def test_urgent_subtitle_single_uses_time_not_topic():
    user = _user(timezone="UTC")
    due = datetime.now(UTC) + timedelta(minutes=30)
    urgent = [
        home_service.HomeUrgentTodo(
            id=uuid4(),
            content="Walk",
            topic="Walk",
            due_at=due,
            minutes_until=30,
        )
    ]
    subtitle = home_service._urgent_subtitle(user, urgent)
    assert subtitle is not None
    assert "Walk" in subtitle
    assert "(Walk)" not in subtitle
    assert "today at" in subtitle or "Coming up" in subtitle


def test_urgent_subtitle_multiple_counts():
    user = _user()
    due = datetime.now(UTC) + timedelta(minutes=10)
    urgent = [
        home_service.HomeUrgentTodo(
            id=uuid4(),
            content="A",
            topic="General",
            due_at=due,
            minutes_until=10,
        ),
        home_service.HomeUrgentTodo(
            id=uuid4(),
            content="B",
            topic="General",
            due_at=due,
            minutes_until=10,
        ),
    ]
    assert home_service._urgent_subtitle(user, urgent) == "2 reminders in the next hour."


def test_looks_internal_filters_user_facts():
    assert home_service._looks_internal("User's name is Binalfew")
    assert not home_service._looks_internal("Building the Recall app")


def test_looks_internal_allows_learning_facts():
    assert not home_service._looks_internal("User is learning English")


@pytest.mark.asyncio
async def test_get_home_screen_cached_reuses_redis(fake_redis):
    user = _user()
    settings = Settings(home_cache_ttl=60)
    session = AsyncMock()
    screen = home_service.HomeScreenOut(
        greeting="Hi",
        subtitle=None,
        project_highlight=None,
        urgent_todos=[],
        starters=[],
    )

    with (
        patch("app.services.home.get_redis_client", return_value=fake_redis),
        patch.object(
            home_service,
            "build_home_screen",
            AsyncMock(return_value=screen),
        ) as build_mock,
    ):
        first = await home_service.get_home_screen_cached(session, user, settings)
        second = await home_service.get_home_screen_cached(session, user, settings)

    assert first == screen
    assert second == screen
    build_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalidate_home_cache_clears_user_keys(fake_redis):
    user_id = uuid4()
    other_id = uuid4()
    await fake_redis.set(f"home:{user_id}:UTC:1", "{}", ex=60)
    await fake_redis.set(f"home:{user_id}:America/New_York:1", "{}", ex=60)
    await fake_redis.set(f"home:{other_id}:UTC:1", "{}", ex=60)

    with patch("app.services.home.get_redis_client", return_value=fake_redis):
        await home_service.invalidate_home_cache(user_id)

    assert await fake_redis.get(f"home:{user_id}:UTC:1") is None
    assert await fake_redis.get(f"home:{user_id}:America/New_York:1") is None
    assert await fake_redis.get(f"home:{other_id}:UTC:1") == "{}"


@pytest.mark.asyncio
async def test_get_home_screen_cached_rebuilds_after_invalidate(fake_redis):
    user = _user()
    settings = Settings(home_cache_ttl=60)
    session = AsyncMock()
    screen = home_service.HomeScreenOut(
        greeting="Hi",
        subtitle=None,
        project_highlight=None,
        urgent_todos=[],
        starters=[],
    )

    with (
        patch("app.services.home.get_redis_client", return_value=fake_redis),
        patch.object(
            home_service,
            "build_home_screen",
            AsyncMock(return_value=screen),
        ) as build_mock,
    ):
        first = await home_service.get_home_screen_cached(session, user, settings)
        await home_service.invalidate_home_cache(user.id)
        second = await home_service.get_home_screen_cached(session, user, settings)

    assert first == screen
    assert second == screen
    assert build_mock.await_count == 2


@pytest.mark.asyncio
async def test_integration_starters_when_connected():
    session = AsyncMock()
    user_id = uuid4()
    settings = Settings()
    tz = home_service._resolve_home_tz(_user(), "UTC")

    with (
        patch("app.services.home.integration_starters.local_hour_for_tz", return_value=8),
        patch(
            "app.services.home.integration_starters.calendar_service.is_connected",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.services.home.integration_starters.email_service.is_connected",
            AsyncMock(return_value=False),
        ),
    ):
        starters = await home_service._integration_starters(session, user_id, settings, tz=tz)

    assert len(starters) == 1
    assert starters[0].text == "Today's calendar"
    assert "calendar" in starters[0].prompt.lower()
    assert "today" in starters[0].prompt.lower()


@pytest.mark.asyncio
async def test_integration_starters_afternoon_shows_tomorrow_calendar():
    session = AsyncMock()
    user_id = uuid4()
    settings = Settings()
    tz = home_service._resolve_home_tz(_user(), "UTC")

    with (
        patch("app.services.home.integration_starters.local_hour_for_tz", return_value=14),
        patch(
            "app.services.home.integration_starters.calendar_service.is_connected",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.services.home.integration_starters.email_service.is_connected",
            AsyncMock(return_value=True),
        ),
    ):
        starters = await home_service._integration_starters(session, user_id, settings, tz=tz)

    texts = {s.text for s in starters}
    assert texts == {"Tomorrow's calendar"}
    assert "tomorrow" in starters[0].prompt.lower()


@pytest.mark.asyncio
async def test_integration_starters_email_only_in_morning():
    session = AsyncMock()
    user_id = uuid4()
    settings = Settings()
    tz = home_service._resolve_home_tz(_user(), "UTC")

    with (
        patch("app.services.home.integration_starters.local_hour_for_tz", return_value=9),
        patch(
            "app.services.home.integration_starters.calendar_service.is_connected",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.services.home.integration_starters.email_service.is_connected",
            AsyncMock(return_value=True),
        ),
    ):
        morning = await home_service._integration_starters(session, user_id, settings, tz=tz)

    with (
        patch("app.services.home.integration_starters.local_hour_for_tz", return_value=14),
        patch(
            "app.services.home.integration_starters.calendar_service.is_connected",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.services.home.integration_starters.email_service.is_connected",
            AsyncMock(return_value=True),
        ),
    ):
        afternoon = await home_service._integration_starters(session, user_id, settings, tz=tz)

    assert [s.text for s in morning] == ["Email to handle"]
    assert afternoon == []

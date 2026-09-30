from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules import home as home_service


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
        # Unpatched calendar/gmail AsyncMocks look "connected" and emit chips,
        # which incorrectly marks a cold account as warm.
        "integration_starters": [],
    }
    defaults.update(overrides)

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
            home_service,
            "integration_starters",
            AsyncMock(return_value=defaults["integration_starters"]),
        ),
    ):
        yield


@pytest.mark.asyncio
async def test_build_home_screen_never_overlaps_ops_on_one_session():
    """Core home loaders run concurrently; each concurrent loader must use its
    own session (asyncpg raises InterfaceError on overlap).
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


def test_time_starters_vary_by_hour():
    user = _user()
    tz = home_service._resolve_home_tz(user, "UTC")
    with patch("app.modules.home.time_starters.local_hour_for_tz", side_effect=[8, 16]):
        morning = home_service._time_starters(user, tz)
        afternoon = home_service._time_starters(user, tz)
    assert morning[0].text != afternoon[0].text
    assert morning[0].text == "Plan my day"
    assert afternoon[0].text == "How did today go?"


def test_time_starters_reflect_starts_at_three_pm():
    user = _user()
    tz = home_service._resolve_home_tz(user, "UTC")
    with patch("app.modules.home.time_starters.local_hour_for_tz", return_value=14):
        before = home_service._time_starters(user, tz)
    with patch("app.modules.home.time_starters.local_hour_for_tz", return_value=15):
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
        patch("app.modules.home.time_starters.local_hour_for_tz", return_value=20),
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
    chat.id = uuid4()
    chat.title = "Yesterday's notes"

    with (
        _home_patches(list_for_user_chats=[chat]),
        patch("app.modules.home.time_starters.local_hour_for_tz", return_value=20),
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert any(s.kind == "time" for s in screen.starters)
    assert any(s.text in {"How did today go?", "Anything left tonight?"} for s in screen.starters)


def test_client_timezone_overrides_profile():
    user = _user(timezone="UTC")
    tz = home_service._resolve_home_tz(user, "America/New_York")
    assert str(tz) == "America/New_York"


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


def test_chat_starter_uses_friendly_label():
    chat_id = uuid4()
    match = home_service._chat_starter([("Binalfew Software Engineer Context", chat_id)])
    assert match is not None
    starter, title = match
    assert starter.text == "Pick up where we left off"
    assert "Software Engineer" in starter.prompt
    assert title == "Binalfew Software Engineer Context"
    assert starter.chat_id == chat_id


def test_texts_overlap_matches_project_and_chat():
    assert home_service._texts_overlap("General knowledge", "General knowledge quiz")
    assert home_service._texts_overlap(
        "General knowledge",
        "User is actively engaged in General knowledge",
    )


def test_chat_starter_skips_project_overlap():
    match = home_service._chat_starter(
        [("General knowledge practice", uuid4())],
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


def test_looks_internal_allows_ordinary_facts():
    assert not home_service._looks_internal("User is learning English")


def test_memory_starter_focus_uses_progress_label():
    memory = MagicMock()
    memory.type = "focus"
    memory.text = "User is learning English"
    starter = home_service._memory_starter(memory)
    assert starter is not None
    assert starter.text == "Make some progress"
    assert "learning English" in starter.prompt


def test_memory_starter_profile_is_not_a_chip():
    memory = MagicMock()
    memory.type = "profile"
    memory.text = "User is learning English vocabulary"
    assert home_service._memory_starter(memory) is None


@pytest.mark.asyncio
async def test_get_home_screen_cached_reuses_redis(fake_redis):
    user = _user()
    settings = Settings(home_cache_ttl=60)
    session = AsyncMock()
    screen = home_service.HomeScreenOut(
        greeting="Hi",
        subtitle=None,
        urgent_todos=[],
        starters=[],
    )

    with (
        patch("app.modules.home.get_redis_client", return_value=fake_redis),
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
async def test_invalidate_home_cache_bumps_generation(fake_redis):
    """INCR, not SCAN — old keys expire via TTL; readers use the new gen."""
    user_id = uuid4()
    other_id = uuid4()
    await fake_redis.set(f"home:{user_id}:0:UTC:1", "{}", ex=60)
    await fake_redis.set(f"home:{other_id}:0:UTC:1", "{}", ex=60)

    with patch("app.modules.home.get_redis_client", return_value=fake_redis):
        await home_service.invalidate_home_cache(user_id)

    assert await fake_redis.get(home_service._home_generation_key(user_id)) == "1"
    assert await fake_redis.get(f"home:{user_id}:0:UTC:1") == "{}"
    assert await fake_redis.get(f"home:{other_id}:0:UTC:1") == "{}"


@pytest.mark.asyncio
async def test_get_home_screen_cached_rebuilds_after_invalidate(fake_redis):
    user = _user()
    settings = Settings(home_cache_ttl=60)
    session = AsyncMock()
    screen = home_service.HomeScreenOut(
        greeting="Hi",
        subtitle=None,
        urgent_todos=[],
        starters=[],
    )

    with (
        patch("app.modules.home.get_redis_client", return_value=fake_redis),
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
        patch("app.modules.home.integration_starters.local_hour_for_tz", return_value=8),
        patch(
            "app.modules.home.integration_starters.calendar_service.is_connected",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.modules.home.integration_starters.email_service.is_connected",
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
        patch("app.modules.home.integration_starters.local_hour_for_tz", return_value=14),
        patch(
            "app.modules.home.integration_starters.calendar_service.is_connected",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.modules.home.integration_starters.email_service.is_connected",
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
        patch("app.modules.home.integration_starters.local_hour_for_tz", return_value=9),
        patch(
            "app.modules.home.integration_starters.calendar_service.is_connected",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.modules.home.integration_starters.email_service.is_connected",
            AsyncMock(return_value=True),
        ),
    ):
        morning = await home_service._integration_starters(session, user_id, settings, tz=tz)

    with (
        patch("app.modules.home.integration_starters.local_hour_for_tz", return_value=14),
        patch(
            "app.modules.home.integration_starters.calendar_service.is_connected",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.modules.home.integration_starters.email_service.is_connected",
            AsyncMock(return_value=True),
        ),
    ):
        afternoon = await home_service._integration_starters(session, user_id, settings, tz=tz)

    assert [s.text for s in morning] == ["Email to handle"]
    assert afternoon == []

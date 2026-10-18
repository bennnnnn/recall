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


@pytest.mark.asyncio
async def test_build_home_screen_has_no_starter_chips():
    session = AsyncMock()
    user = _user()

    with patch.object(
        home_service.todos_repo,
        "list_due_soon",
        AsyncMock(return_value=[]),
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert screen.greeting
    assert screen.starters == []
    assert screen.urgent_todos == []
    assert screen.subtitle is None


@pytest.mark.asyncio
async def test_build_home_includes_urgent_todo():
    session = AsyncMock()
    user = _user()
    urgent = _todo("Pay rent", minutes_from_now=30)

    with patch.object(
        home_service.todos_repo,
        "list_due_soon",
        AsyncMock(return_value=[urgent]),
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert len(screen.urgent_todos) == 1
    assert screen.urgent_todos[0].content == "Pay rent"
    assert "Pay rent" in (screen.subtitle or "")
    assert screen.starters == []


@pytest.mark.asyncio
async def test_home_urgent_window_uses_user_lead():
    session = AsyncMock()
    user = _user()
    user.reminder_lead_minutes = 30

    with patch.object(
        home_service.todos_repo,
        "list_due_soon",
        AsyncMock(return_value=[]),
    ):
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

    with patch.object(
        home_service.todos_repo,
        "list_due_soon",
        AsyncMock(return_value=[]),
    ):
        await home_service.build_home_screen(session, user, Settings())
        before_utc = home_service.todos_repo.list_due_soon.call_args.kwargs.get("before_utc")

    assert before_utc is not None
    delta_min = (before_utc - datetime.now(UTC)).total_seconds() / 60
    assert 7 <= delta_min <= 13  # default lead = 10 min


@pytest.mark.asyncio
async def test_build_home_greeting_uses_name():
    session = AsyncMock()
    user = _user(name="Sam")

    with patch.object(
        home_service.todos_repo,
        "list_due_soon",
        AsyncMock(return_value=[]),
    ):
        screen = await home_service.build_home_screen(session, user, Settings())

    assert "Sam" in screen.greeting
    assert screen.starters == []


def test_client_timezone_overrides_profile():
    user = _user(timezone="UTC")
    tz = home_service.resolve_home_tz(user, "America/New_York")
    assert str(tz) == "America/New_York"


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
    subtitle = home_service.urgent_subtitle(user, urgent)
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
    assert home_service.urgent_subtitle(user, urgent) == "2 reminders in the next hour."


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
    """A new generation, not SCAN — old keys expire via TTL; readers use the new gen."""
    user_id = uuid4()
    other_id = uuid4()
    await fake_redis.set(f"home:{user_id}:0:UTC:1", "{}", ex=60)
    await fake_redis.set(f"home:{other_id}:0:UTC:1", "{}", ex=60)
    generation_key = home_service._home_generation_key(user_id)

    with patch("app.modules.home.get_redis_client", return_value=fake_redis):
        await home_service.invalidate_home_cache(user_id)
        first = await fake_redis.get(generation_key)
        await home_service.invalidate_home_cache(user_id)

    assert first not in (None, "0")
    assert await fake_redis.get(generation_key) not in (None, "0", first)
    assert await fake_redis.get(f"home:{user_id}:0:UTC:1") == "{}"
    assert await fake_redis.get(f"home:{other_id}:0:UTC:1") == "{}"


@pytest.mark.asyncio
async def test_home_generation_key_expires(fake_redis):
    """The per-user generation key had no TTL: one key per user, forever."""
    from app.core.cache_generation import GENERATION_TTL_SECONDS

    user_id = uuid4()
    with patch("app.modules.home.get_redis_client", return_value=fake_redis):
        await home_service.invalidate_home_cache(user_id)

    ttl = await fake_redis.ttl(home_service._home_generation_key(user_id))
    assert 0 < ttl <= GENERATION_TTL_SECONDS


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
async def test_get_home_screen_cached_unreadable_generation_skips_the_cache(fake_redis, caplog):
    """A failed generation read used to mean generation "0", the key a home screen from
    before the user's last change may still sit under, so a Redis blip served it stale."""
    user = _user()
    settings = Settings(home_cache_ttl=60)
    stale = home_service.HomeScreenOut(
        greeting="Stale", subtitle=None, urgent_todos=[], starters=[]
    )
    fresh = stale.model_copy(update={"greeting": "Fresh"})
    generation_key = home_service._home_generation_key(user.id)
    read = fake_redis.get

    async def get_failing_generation(key):
        if key == generation_key:
            raise ConnectionError("redis down")
        return await read(key)

    with (
        patch("app.modules.home.get_redis_client", return_value=fake_redis),
        patch.object(home_service, "build_home_screen", AsyncMock(side_effect=[stale, fresh])),
    ):
        await home_service.get_home_screen_cached(AsyncMock(), user, settings)
        await home_service.invalidate_home_cache(user.id)  # the user changed a reminder
        with (
            patch.object(fake_redis, "get", side_effect=get_failing_generation),
            caplog.at_level("WARNING", logger="app.modules.home"),
        ):
            screen = await home_service.get_home_screen_cached(AsyncMock(), user, settings)

    assert screen.greeting == "Fresh"
    warnings = [r for r in caplog.records if r.name == "app.modules.home"]
    assert [r.levelname for r in warnings] == ["WARNING"]
    assert "ConnectionError" in warnings[0].getMessage()
    # Nothing is written under a generation it could not read.
    (zero_key,) = await fake_redis.keys(f"home:{user.id}:0:*")
    assert home_service.HomeScreenOut.model_validate_json(await read(zero_key)) == stale

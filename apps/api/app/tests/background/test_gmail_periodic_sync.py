import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.background import gmail_periodic_sync
from app.core.config import Settings


class _FakeSessionCM:
    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


def _fake_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock()
    redis.eval = AsyncMock(return_value=1)
    return redis


@pytest.mark.asyncio
async def test_periodic_cycle_syncs_due_users_concurrently_with_isolated_sessions():
    """Each due user gets synced, each with its own session and error isolation."""
    connections = [SimpleNamespace(user_id=uuid4(), last_sync_at=None) for _ in range(4)]
    redis = _fake_redis()
    sync_calls: list[object] = []
    in_flight = 0
    max_in_flight = 0

    async def fake_sync(session, settings, user_id, *, redis):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        sync_calls.append(user_id)
        await asyncio.sleep(0)  # yield so overlapping calls can interleave
        in_flight -= 1

    settings = Settings(gmail_enabled=True, gmail_periodic_sync_concurrency=2)

    with (
        patch("app.background.gmail_periodic_sync.get_redis_client", return_value=redis),
        patch(
            "app.background.gmail_periodic_sync.SessionLocal",
            side_effect=lambda: _FakeSessionCM(AsyncMock()),
        ),
        patch(
            "app.background.gmail_periodic_sync.gmail_repo.list_all",
            AsyncMock(return_value=connections),
        ),
        patch(
            "app.background.gmail_periodic_sync.email_service.sync_gmail_for_user",
            fake_sync,
        ),
    ):
        await gmail_periodic_sync.run_gmail_periodic_cycle(settings)

    assert {c.user_id for c in connections} == set(sync_calls)
    assert max_in_flight <= 2  # respected the configured concurrency bound


@pytest.mark.asyncio
async def test_periodic_cycle_skips_recently_synced_users():
    now = datetime.now(UTC)
    fresh = SimpleNamespace(user_id=uuid4(), last_sync_at=now)
    stale = SimpleNamespace(user_id=uuid4(), last_sync_at=now - timedelta(hours=2))
    redis = _fake_redis()
    sync_mock = AsyncMock()

    settings = Settings(gmail_enabled=True, gmail_sync_interval_seconds=3600)

    with (
        patch("app.background.gmail_periodic_sync.get_redis_client", return_value=redis),
        patch(
            "app.background.gmail_periodic_sync.SessionLocal",
            side_effect=lambda: _FakeSessionCM(AsyncMock()),
        ),
        patch(
            "app.background.gmail_periodic_sync.gmail_repo.list_all",
            AsyncMock(return_value=[fresh, stale]),
        ),
        patch(
            "app.background.gmail_periodic_sync.email_service.sync_gmail_for_user",
            sync_mock,
        ),
    ):
        await gmail_periodic_sync.run_gmail_periodic_cycle(settings)

    synced_user_ids = {call.args[2] for call in sync_mock.await_args_list}
    assert synced_user_ids == {stale.user_id}


@pytest.mark.asyncio
async def test_periodic_cycle_isolates_one_users_failure_from_the_rest():
    connections = [SimpleNamespace(user_id=uuid4(), last_sync_at=None) for _ in range(3)]
    failing_id = connections[0].user_id
    redis = _fake_redis()
    succeeded: list[object] = []

    async def fake_sync(session, settings, user_id, *, redis):
        if user_id == failing_id:
            raise RuntimeError("boom")
        succeeded.append(user_id)

    settings = Settings(gmail_enabled=True)

    with (
        patch("app.background.gmail_periodic_sync.get_redis_client", return_value=redis),
        patch(
            "app.background.gmail_periodic_sync.SessionLocal",
            side_effect=lambda: _FakeSessionCM(AsyncMock()),
        ),
        patch(
            "app.background.gmail_periodic_sync.gmail_repo.list_all",
            AsyncMock(return_value=connections),
        ),
        patch(
            "app.background.gmail_periodic_sync.email_service.sync_gmail_for_user",
            fake_sync,
        ),
    ):
        await gmail_periodic_sync.run_gmail_periodic_cycle(settings)

    assert set(succeeded) == {c.user_id for c in connections if c.user_id != failing_id}
    # Token-based release uses Lua compare-and-delete via EVAL, not bare DELETE.
    redis.eval.assert_awaited()
    redis.delete.assert_not_awaited()

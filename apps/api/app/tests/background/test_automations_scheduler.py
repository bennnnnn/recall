from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.background import automations_scheduler
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
async def test_cycle_enqueues_one_job_per_due_automation_with_stable_dedupe_key():
    due = [
        SimpleNamespace(id=uuid4(), next_run_at=datetime(2026, 9, 18, 8, tzinfo=UTC)),
        SimpleNamespace(id=uuid4(), next_run_at=datetime(2026, 9, 18, 9, tzinfo=UTC)),
    ]
    redis = _fake_redis()
    settings = Settings(automations_enabled=True)

    with (
        patch("app.background.periodic.get_redis_client", return_value=redis),
        patch("app.background.automations_scheduler.get_redis_client", return_value=redis),
        patch(
            "app.background.automations_scheduler.SessionLocal",
            side_effect=lambda: _FakeSessionCM(AsyncMock()),
        ),
        patch(
            "app.background.automations_scheduler.automations_repo.list_due",
            AsyncMock(return_value=due),
        ),
        patch("app.background.automations_scheduler.enqueue", AsyncMock()) as enqueue_mock,
    ):
        await automations_scheduler.run_automations_cycle(settings)

    assert enqueue_mock.await_count == 2
    for call, automation in zip(enqueue_mock.await_args_list, due, strict=True):
        assert call.args[1] == "automation_run"
        assert call.args[2] == {"automation_id": str(automation.id)}
        assert call.kwargs["dedupe_key"] == (
            f"automation_run:{automation.id}:{automation.next_run_at.isoformat()}"
        )


@pytest.mark.asyncio
async def test_cycle_does_not_mutate_the_automation_row():
    """The scheduler only enqueues — `run_automation` owns every schedule write."""
    automation = SimpleNamespace(id=uuid4(), next_run_at=datetime.now(UTC))
    redis = _fake_redis()
    settings = Settings(automations_enabled=True)
    session = AsyncMock()

    with (
        patch("app.background.periodic.get_redis_client", return_value=redis),
        patch("app.background.automations_scheduler.get_redis_client", return_value=redis),
        patch(
            "app.background.automations_scheduler.SessionLocal",
            side_effect=lambda: _FakeSessionCM(session),
        ),
        patch(
            "app.background.automations_scheduler.automations_repo.list_due",
            AsyncMock(return_value=[automation]),
        ),
        patch("app.background.automations_scheduler.enqueue", AsyncMock()),
    ):
        await automations_scheduler.run_automations_cycle(settings)

    session.commit.assert_not_awaited()
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_cycle_noop_when_nothing_due():
    redis = _fake_redis()
    settings = Settings(automations_enabled=True)

    with (
        patch("app.background.periodic.get_redis_client", return_value=redis),
        patch("app.background.automations_scheduler.get_redis_client", return_value=redis),
        patch(
            "app.background.automations_scheduler.SessionLocal",
            side_effect=lambda: _FakeSessionCM(AsyncMock()),
        ),
        patch(
            "app.background.automations_scheduler.automations_repo.list_due",
            AsyncMock(return_value=[]),
        ),
        patch("app.background.automations_scheduler.enqueue", AsyncMock()) as enqueue_mock,
    ):
        await automations_scheduler.run_automations_cycle(settings)

    enqueue_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_cycle_skips_entirely_when_automations_disabled():
    redis = _fake_redis()
    settings = Settings(automations_enabled=False)

    with (
        patch("app.background.periodic.get_redis_client", return_value=redis),
        patch(
            "app.background.automations_scheduler.automations_repo.list_due",
            AsyncMock(),
        ) as list_due,
    ):
        await automations_scheduler.run_automations_cycle(settings)

    list_due.assert_not_awaited()
    redis.set.assert_not_awaited()

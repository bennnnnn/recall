"""Shared process bootstrap wiring tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import process_bootstrap
from app.core.config import Settings


@pytest.mark.asyncio
async def test_start_worker_runtime_registers_before_consumer_and_schedulers():
    order: list[str] = []

    def register_all() -> None:
        order.append("register")

    async def start_worker(_settings: Settings) -> None:
        order.append("worker")

    settings = Settings(mock_llm_enabled=True)
    with (
        patch("app.process_bootstrap.job_handlers.register_all", side_effect=register_all),
        patch("app.process_bootstrap.jobs.start_worker", side_effect=start_worker),
        patch(
            "app.process_bootstrap.push_scheduler.start_push_scheduler",
            AsyncMock(),
        ),
        patch(
            "app.process_bootstrap.email_reminder_scheduler.start_email_reminder_scheduler",
            AsyncMock(),
        ),
        patch(
            "app.process_bootstrap.gmail_periodic_sync.start_gmail_periodic_scheduler",
            AsyncMock(),
        ),
        patch(
            "app.process_bootstrap.attachment_orphan_reaper.start_orphan_reaper",
            AsyncMock(),
        ),
    ):
        await process_bootstrap.start_worker_runtime(settings)

    assert order == ["register", "worker"]


@pytest.mark.asyncio
async def test_shutdown_process_stops_worker_before_closing_resources():
    stop_worker = AsyncMock()
    redis = AsyncMock()
    redis.aclose = AsyncMock()
    engine = MagicMock()
    engine.dispose = AsyncMock()
    with (
        patch("app.process_bootstrap.drain_background_tasks", AsyncMock()) as drain,
        patch("app.process_bootstrap.stop_worker_runtime", stop_worker),
        patch("app.process_bootstrap.engine", engine),
        patch("app.process_bootstrap.get_redis_client", return_value=redis),
        patch("app.process_bootstrap.aclose_pooled_clients", AsyncMock()) as close_http,
    ):
        await process_bootstrap.shutdown_process(stop_worker=True)

    drain.assert_awaited_once_with(timeout_seconds=10.0)
    stop_worker.assert_awaited_once()
    engine.dispose.assert_awaited_once()
    redis.aclose.assert_awaited_once()
    close_http.assert_awaited_once()

"""Tests for the standalone worker entrypoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.worker_main import _run_worker


@pytest.mark.asyncio
async def test_run_worker_starts_and_shuts_down():
    settings = Settings(mock_llm_enabled=True, environment="development")
    engine_mock = MagicMock()
    engine_mock.dispose = AsyncMock()
    with (
        patch("app.worker_main.setup_logging"),
        patch("app.worker_main.get_settings", return_value=settings),
        patch("app.worker_main.validate_production_settings"),
        patch("app.worker_main.init_sentry"),
        patch("app.worker_main.setup_mcp_adapters"),
        patch("app.worker_main.jobs.start_worker", AsyncMock()) as start_worker,
        patch("app.worker_main.jobs.stop_worker", AsyncMock()) as stop_worker,
        patch("app.worker_main.push_scheduler.start_push_scheduler", AsyncMock()),
        patch("app.worker_main.push_scheduler.stop_push_scheduler", AsyncMock()),
        patch("app.worker_main.gmail_periodic_sync.start_gmail_periodic_scheduler", AsyncMock()),
        patch("app.worker_main.gmail_periodic_sync.stop_gmail_periodic_scheduler", AsyncMock()),
        patch("app.worker_main.attachment_orphan_reaper.start_orphan_reaper", AsyncMock()),
        patch("app.worker_main.attachment_orphan_reaper.stop_orphan_reaper", AsyncMock()),
        patch("app.worker_main.engine", engine_mock),
        patch("app.worker_main.get_redis_client") as redis_client,
        patch("app.worker_main.asyncio.Event") as event_cls,
    ):
        event_cls.return_value.wait = AsyncMock(return_value=None)
        redis = AsyncMock()
        redis.aclose = AsyncMock()
        redis_client.return_value = redis

        await _run_worker()

    start_worker.assert_awaited_once()
    stop_worker.assert_awaited_once()
    engine_mock.dispose.assert_awaited_once()
    redis.aclose.assert_awaited_once()


def test_worker_main_calls_asyncio_run():
    with patch("app.worker_main.asyncio.run") as run_mock:
        from app.worker_main import main

        main()
    run_mock.assert_called_once()

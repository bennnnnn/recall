"""Tests for the standalone worker entrypoint."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.worker_main import _run_worker


@pytest.mark.asyncio
async def test_run_worker_starts_and_shuts_down():
    settings = Settings(
        mock_llm_enabled=True,
        environment="development",
        worker_health_port=0,
    )
    engine_mock = MagicMock()
    engine_mock.dispose = AsyncMock()
    redis = AsyncMock()
    redis.aclose = AsyncMock()
    warmup = AsyncMock()
    start_worker = AsyncMock()
    stop_worker = AsyncMock()
    aclose_pools = AsyncMock()

    with ExitStack() as stack:
        stack.enter_context(patch("app.worker_main.setup_logging"))
        stack.enter_context(patch("app.worker_main.get_settings", return_value=settings))
        stack.enter_context(patch("app.worker_main.validate_production_settings"))
        stack.enter_context(patch("app.worker_main.init_sentry"))
        stack.enter_context(patch("app.worker_main.setup_mcp_adapters"))
        stack.enter_context(patch("app.worker_main.warmup_db_pool", warmup))
        stack.enter_context(patch("app.worker_main.jobs.start_worker", start_worker))
        stack.enter_context(patch("app.worker_main.jobs.stop_worker", stop_worker))
        stack.enter_context(
            patch("app.worker_main.push_scheduler.start_push_scheduler", AsyncMock())
        )
        stack.enter_context(
            patch("app.worker_main.push_scheduler.stop_push_scheduler", AsyncMock())
        )
        stack.enter_context(
            patch(
                "app.worker_main.email_reminder_scheduler.start_email_reminder_scheduler",
                AsyncMock(),
            )
        )
        stack.enter_context(
            patch(
                "app.worker_main.email_reminder_scheduler.stop_email_reminder_scheduler",
                AsyncMock(),
            )
        )
        stack.enter_context(
            patch("app.worker_main.gmail_periodic_sync.start_gmail_periodic_scheduler", AsyncMock())
        )
        stack.enter_context(
            patch("app.worker_main.gmail_periodic_sync.stop_gmail_periodic_scheduler", AsyncMock())
        )
        stack.enter_context(
            patch("app.worker_main.attachment_orphan_reaper.start_orphan_reaper", AsyncMock())
        )
        stack.enter_context(
            patch("app.worker_main.attachment_orphan_reaper.stop_orphan_reaper", AsyncMock())
        )
        stack.enter_context(patch("app.worker_main.engine", engine_mock))
        stack.enter_context(patch("app.worker_main.get_redis_client", return_value=redis))
        stack.enter_context(patch("app.worker_main.aclose_pooled_clients", aclose_pools))
        event_cls = stack.enter_context(patch("app.worker_main.asyncio.Event"))
        event_cls.return_value.wait = AsyncMock(return_value=None)
        await _run_worker()

    warmup.assert_awaited_once()
    start_worker.assert_awaited_once()
    stop_worker.assert_awaited_once()
    engine_mock.dispose.assert_awaited_once()
    redis.aclose.assert_awaited_once()
    aclose_pools.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_worker_starts_health_server_when_port_set():
    """When worker_health_port > 0 the worker must start the health HTTP server
    so Fly can detect + restart a stuck worker."""
    settings = Settings(
        mock_llm_enabled=True,
        environment="development",
        worker_health_port=8001,
    )
    fake_server = MagicMock()
    fake_server.serve = AsyncMock()
    fake_server.shutdown = AsyncMock()
    fake_config = MagicMock()

    with ExitStack() as stack:
        stack.enter_context(patch("app.worker_main.setup_logging"))
        stack.enter_context(patch("app.worker_main.get_settings", return_value=settings))
        stack.enter_context(patch("app.worker_main.validate_production_settings"))
        stack.enter_context(patch("app.worker_main.init_sentry"))
        stack.enter_context(patch("app.worker_main.setup_mcp_adapters"))
        stack.enter_context(patch("app.worker_main.warmup_db_pool", AsyncMock()))
        stack.enter_context(patch("app.worker_main.jobs.start_worker", AsyncMock()))
        stack.enter_context(patch("app.worker_main.jobs.stop_worker", AsyncMock()))
        stack.enter_context(
            patch("app.worker_main.push_scheduler.start_push_scheduler", AsyncMock())
        )
        stack.enter_context(
            patch("app.worker_main.push_scheduler.stop_push_scheduler", AsyncMock())
        )
        stack.enter_context(
            patch(
                "app.worker_main.email_reminder_scheduler.start_email_reminder_scheduler",
                AsyncMock(),
            )
        )
        stack.enter_context(
            patch(
                "app.worker_main.email_reminder_scheduler.stop_email_reminder_scheduler",
                AsyncMock(),
            )
        )
        stack.enter_context(
            patch("app.worker_main.gmail_periodic_sync.start_gmail_periodic_scheduler", AsyncMock())
        )
        stack.enter_context(
            patch("app.worker_main.gmail_periodic_sync.stop_gmail_periodic_scheduler", AsyncMock())
        )
        stack.enter_context(
            patch("app.worker_main.attachment_orphan_reaper.start_orphan_reaper", AsyncMock())
        )
        stack.enter_context(
            patch("app.worker_main.attachment_orphan_reaper.stop_orphan_reaper", AsyncMock())
        )
        stack.enter_context(patch("app.worker_main.engine", MagicMock(dispose=AsyncMock())))
        stack.enter_context(
            patch("app.worker_main.get_redis_client", return_value=MagicMock(aclose=AsyncMock()))
        )
        stack.enter_context(patch("app.worker_main.aclose_pooled_clients", AsyncMock()))
        event_cls = stack.enter_context(patch("app.worker_main.asyncio.Event"))
        event_cls.return_value.wait = AsyncMock(return_value=None)
        server_ctor = stack.enter_context(patch("uvicorn.Server", return_value=fake_server))
        config_ctor = stack.enter_context(patch("uvicorn.Config", return_value=fake_config))
        await _run_worker()

    config_ctor.assert_called_once()
    assert config_ctor.call_args.kwargs["port"] == 8001
    server_ctor.assert_called_once_with(fake_config)
    fake_server.serve.assert_called_once()
    fake_server.shutdown.assert_awaited_once()


def test_worker_main_calls_asyncio_run():
    with patch("app.worker_main.asyncio.run") as run_mock:
        from app.worker_main import main

        main()
    run_mock.assert_called_once()

"""Tests for the standalone worker entrypoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.worker_main import _run_worker


@pytest.mark.asyncio
async def test_run_worker_uses_shared_bootstrap():
    settings = Settings(
        mock_llm_enabled=True,
        environment="development",
        worker_health_port=0,
    )
    initialize = AsyncMock()
    start = AsyncMock()
    shutdown = AsyncMock()
    with (
        patch("app.worker_main.get_settings", return_value=settings),
        patch("app.worker_main.process_bootstrap.initialize_process", initialize),
        patch("app.worker_main.process_bootstrap.start_worker_runtime", start),
        patch("app.worker_main.process_bootstrap.shutdown_process", shutdown),
        patch("app.worker_main.asyncio.Event") as event_cls,
    ):
        event_cls.return_value.wait = AsyncMock(return_value=None)
        await _run_worker()

    initialize.assert_awaited_once_with(settings)
    start.assert_awaited_once_with(settings)
    shutdown.assert_awaited_once_with(
        stop_worker=True,
        drain_before_stop=False,
    )


@pytest.mark.asyncio
async def test_run_worker_starts_health_server_when_port_set():
    settings = Settings(
        mock_llm_enabled=True,
        environment="development",
        worker_health_port=8001,
    )
    fake_server = MagicMock()
    fake_server.serve = AsyncMock()
    fake_server.shutdown = AsyncMock()
    fake_config = MagicMock()
    with (
        patch("app.worker_main.get_settings", return_value=settings),
        patch("app.worker_main.process_bootstrap.initialize_process", AsyncMock()),
        patch("app.worker_main.process_bootstrap.start_worker_runtime", AsyncMock()),
        patch("app.worker_main.process_bootstrap.shutdown_process", AsyncMock()),
        patch("app.worker_main.asyncio.Event") as event_cls,
        patch("uvicorn.Server", return_value=fake_server) as server_ctor,
        patch("uvicorn.Config", return_value=fake_config) as config_ctor,
    ):
        event_cls.return_value.wait = AsyncMock(return_value=None)
        await _run_worker()

    assert config_ctor.call_args.kwargs["port"] == 8001
    server_ctor.assert_called_once_with(fake_config)
    fake_server.shutdown.assert_awaited_once()


def test_worker_main_calls_asyncio_run():
    with patch("app.worker_main.asyncio.run") as run_mock:
        from app.worker_main import main

        main()
    run_mock.assert_called_once()
    run_mock.call_args.args[0].close()

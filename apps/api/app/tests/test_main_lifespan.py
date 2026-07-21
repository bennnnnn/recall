"""App factory and lifespan tests."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app, lifespan


def test_create_app_registers_health_route():
    client = TestClient(create_app())
    assert client.get("/health").status_code == 200


def _lifespan_patches(
    stack: ExitStack,
    *,
    mock_engine: MagicMock,
    mock_redis: MagicMock,
    start_worker: AsyncMock | None = None,
    mock_settings: MagicMock | None = None,
    start_push: AsyncMock | None = None,
) -> AsyncMock:
    """Shared mocks for lifespan tests (avoids Python's nested-block limit)."""
    stack.enter_context(patch("app.main.setup_logging"))
    stack.enter_context(patch("app.main.init_sentry"))
    stack.enter_context(patch("app.main.validate_production_settings"))
    stack.enter_context(patch("app.gateways.mcp.setup_mcp_adapters"))
    if mock_settings is not None:
        stack.enter_context(patch("app.main.get_settings", return_value=mock_settings))
    worker = start_worker if start_worker is not None else AsyncMock()
    stack.enter_context(patch("app.main.jobs.start_worker", worker))
    stack.enter_context(patch("app.main.jobs.stop_worker", AsyncMock()))
    push = start_push if start_push is not None else AsyncMock()
    stack.enter_context(patch("app.main.push_scheduler.start_push_scheduler", push))
    stack.enter_context(patch("app.main.push_scheduler.stop_push_scheduler", AsyncMock()))
    stack.enter_context(
        patch("app.main.email_reminder_scheduler.start_email_reminder_scheduler", AsyncMock())
    )
    stack.enter_context(
        patch("app.main.email_reminder_scheduler.stop_email_reminder_scheduler", AsyncMock())
    )
    stack.enter_context(
        patch("app.main.gmail_periodic_sync.start_gmail_periodic_scheduler", AsyncMock())
    )
    stack.enter_context(
        patch("app.main.gmail_periodic_sync.stop_gmail_periodic_scheduler", AsyncMock())
    )
    stack.enter_context(patch("app.main.attachment_orphan_reaper.start_orphan_reaper", AsyncMock()))
    stack.enter_context(patch("app.main.attachment_orphan_reaper.stop_orphan_reaper", AsyncMock()))
    stack.enter_context(patch("app.main.warmup_db_pool", AsyncMock()))
    stack.enter_context(patch("app.main.drain_background_tasks", AsyncMock()))
    stack.enter_context(patch("app.main.aclose_pooled_clients", AsyncMock()))
    stack.enter_context(patch("app.main.engine", mock_engine))
    stack.enter_context(patch("app.main.get_redis_client", return_value=mock_redis))
    return worker


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_workers():
    app = create_app()

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.aclose = AsyncMock()
    start_worker = AsyncMock()

    with ExitStack() as stack:
        _lifespan_patches(
            stack, mock_engine=mock_engine, mock_redis=mock_redis, start_worker=start_worker
        )
        async with lifespan(app):
            pass

    start_worker.assert_awaited()


@pytest.mark.asyncio
async def test_lifespan_api_role_skips_workers():
    app = create_app()

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.aclose = AsyncMock()
    start_worker = AsyncMock()
    start_push = AsyncMock()

    mock_settings = MagicMock()
    mock_settings.process_role = "api"
    mock_settings.cors_origins = "*"
    mock_settings.sentry_dsn = ""

    with ExitStack() as stack:
        _lifespan_patches(
            stack,
            mock_engine=mock_engine,
            mock_redis=mock_redis,
            start_worker=start_worker,
            mock_settings=mock_settings,
            start_push=start_push,
        )
        async with lifespan(app):
            pass

    start_worker.assert_not_awaited()
    start_push.assert_not_awaited()


@pytest.mark.asyncio
async def test_lifespan_rejects_unknown_process_role():
    app = create_app()

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.aclose = AsyncMock()

    mock_settings = MagicMock()
    mock_settings.process_role = "scheduler"
    mock_settings.cors_origins = "*"
    mock_settings.sentry_dsn = ""

    with ExitStack() as stack:
        start_worker = _lifespan_patches(
            stack,
            mock_engine=mock_engine,
            mock_redis=mock_redis,
            mock_settings=mock_settings,
        )
        with pytest.raises(RuntimeError, match="Invalid PROCESS_ROLE"):
            async with lifespan(app):
                pass

    start_worker.assert_not_awaited()

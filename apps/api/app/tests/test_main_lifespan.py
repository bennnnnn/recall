"""App factory and lifespan tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app, lifespan


def test_create_app_registers_health_route():
    client = TestClient(create_app())
    assert client.get("/health").status_code == 200


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_workers():
    app = create_app()

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.aclose = AsyncMock()
    start_worker = AsyncMock()

    with (
        patch("app.main.setup_logging"),
        patch("app.main.init_sentry"),
        patch("app.main.validate_production_settings"),
        patch("app.gateways.mcp.setup_mcp_adapters"),
        patch("app.main.jobs.start_worker", start_worker),
        patch("app.main.jobs.stop_worker", AsyncMock()),
        patch("app.main.push_scheduler.start_push_scheduler", AsyncMock()),
        patch("app.main.push_scheduler.stop_push_scheduler", AsyncMock()),
        patch(
            "app.main.email_reminder_scheduler.start_email_reminder_scheduler",
            AsyncMock(),
        ),
        patch(
            "app.main.email_reminder_scheduler.stop_email_reminder_scheduler",
            AsyncMock(),
        ),
        patch("app.main.gmail_periodic_sync.start_gmail_periodic_scheduler", AsyncMock()),
        patch("app.main.gmail_periodic_sync.stop_gmail_periodic_scheduler", AsyncMock()),
        patch("app.main.attachment_orphan_reaper.start_orphan_reaper", AsyncMock()),
        patch("app.main.attachment_orphan_reaper.stop_orphan_reaper", AsyncMock()),
        patch("app.main.warmup_db_pool", AsyncMock()),
        patch("app.main.aclose_pooled_clients", AsyncMock()),
        patch("app.main.engine", mock_engine),
        patch("app.main.get_redis_client", return_value=mock_redis),
    ):
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

    with (
        patch("app.main.setup_logging"),
        patch("app.main.validate_production_settings"),
        patch("app.main.init_sentry"),
        patch("app.gateways.mcp.setup_mcp_adapters"),
        patch("app.main.get_settings", return_value=mock_settings),
        patch("app.main.jobs.start_worker", start_worker),
        patch("app.main.jobs.stop_worker", AsyncMock()),
        patch("app.main.push_scheduler.start_push_scheduler", start_push),
        patch("app.main.push_scheduler.stop_push_scheduler", AsyncMock()),
        patch(
            "app.main.email_reminder_scheduler.start_email_reminder_scheduler",
            AsyncMock(),
        ),
        patch(
            "app.main.email_reminder_scheduler.stop_email_reminder_scheduler",
            AsyncMock(),
        ),
        patch("app.main.gmail_periodic_sync.start_gmail_periodic_scheduler", AsyncMock()),
        patch("app.main.gmail_periodic_sync.stop_gmail_periodic_scheduler", AsyncMock()),
        patch("app.main.attachment_orphan_reaper.start_orphan_reaper", AsyncMock()),
        patch("app.main.attachment_orphan_reaper.stop_orphan_reaper", AsyncMock()),
        patch("app.main.warmup_db_pool", AsyncMock()),
        patch("app.main.aclose_pooled_clients", AsyncMock()),
        patch("app.main.engine", mock_engine),
        patch("app.main.get_redis_client", return_value=mock_redis),
    ):
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

    with (
        patch("app.main.setup_logging"),
        patch("app.main.validate_production_settings"),
        patch("app.main.init_sentry"),
        patch("app.gateways.mcp.setup_mcp_adapters"),
        patch("app.main.get_settings", return_value=mock_settings),
        patch("app.main.jobs.start_worker", AsyncMock()) as start_worker,
        patch("app.main.warmup_db_pool", AsyncMock()),
        patch("app.main.aclose_pooled_clients", AsyncMock()),
        patch("app.main.engine", mock_engine),
        patch("app.main.get_redis_client", return_value=mock_redis),
    ):
        with pytest.raises(RuntimeError, match="Invalid PROCESS_ROLE"):
            async with lifespan(app):
                pass

    start_worker.assert_not_awaited()

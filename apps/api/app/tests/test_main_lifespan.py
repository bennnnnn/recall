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
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.aclose = AsyncMock()

    with (
        patch("app.main.setup_logging"),
        patch("app.main.validate_production_settings"),
        patch("app.gateways.mcp.setup_mcp_adapters"),
        patch("app.main.jobs.start_worker", AsyncMock()),
        patch("app.main.jobs.stop_worker", AsyncMock()),
        patch("app.main.push_scheduler.start_push_scheduler", AsyncMock()),
        patch("app.main.push_scheduler.stop_push_scheduler", AsyncMock()),
        patch("app.main.gmail_periodic_sync.start_gmail_periodic_scheduler", AsyncMock()),
        patch("app.main.gmail_periodic_sync.stop_gmail_periodic_scheduler", AsyncMock()),
        patch("app.main.SessionLocal", return_value=session),
        patch("app.main.seed_templates.seed_templates", AsyncMock()),
        patch("app.main.engine", mock_engine),
        patch("app.main.get_redis_client", return_value=mock_redis),
    ):
        async with lifespan(app):
            pass

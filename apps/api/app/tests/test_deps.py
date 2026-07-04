from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.core.deps import get_redis, get_redis_dep, get_settings_dep


@pytest.mark.asyncio
async def test_get_settings_dep_returns_settings():
    settings = Settings(jwt_secret="super-secret-key-that-is-at-least-32-chars!!")
    with patch("app.core.deps.get_settings", return_value=settings):
        assert await get_settings_dep() is settings


@pytest.mark.asyncio
async def test_get_redis_dep_returns_client():
    client = AsyncMock()
    with patch("app.core.deps.get_redis_client", return_value=client):
        assert await get_redis_dep() is client


def test_get_redis_returns_client():
    client = MagicMock()
    with patch("app.core.deps.get_redis_client", return_value=client):
        assert get_redis() is client

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


def test_user_cache_forgets_users_nobody_reads_again(monkeypatch):
    """Every user who ever signed in used to stay cached for the life of the
    process: an entry left only when that user was read again after the TTL."""
    import time
    from uuid import uuid4

    from sqlalchemy.orm import make_transient_to_detached

    from app.core import deps
    from app.models.orm import User

    def user() -> User:
        row = User(id=uuid4(), email="someone@example.com", name="Someone")
        make_transient_to_detached(row)
        return row

    deps._user_cache.clear()
    now = [time.monotonic()]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    for _ in range(50):
        deps.remember_user(user())
    now[0] += deps._USER_CACHE_TTL_SECONDS + 1
    latest = user()
    deps.remember_user(latest)

    assert len(deps._user_cache) == 1
    cached = deps._cached_user(latest.id)
    assert cached is not None
    assert cached.id == latest.id
    deps.forget_user(latest.id)
    assert deps._cached_user(latest.id) is None

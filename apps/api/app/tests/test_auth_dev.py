import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.db import engine
from app.main import app


async def _db_available() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_dev_auth_disabled():
    settings = get_settings()
    original = settings.dev_auth_enabled
    settings.dev_auth_enabled = False
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/auth/dev", json={"email": "x@y.z", "name": "X"})
    settings.dev_auth_enabled = original
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_dev_login_ok():
    if not await _db_available():
        pytest.skip("Postgres not available — run: docker compose up -d")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/auth/dev",
            json={"email": "test@recall.local", "name": "Test User"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@recall.local"

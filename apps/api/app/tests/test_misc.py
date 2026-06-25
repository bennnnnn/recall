"""Targeted coverage for utilities and small code paths."""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.database_url import prepare_asyncpg_url

# ── database_url ───────────────────────────────────────────────────────────────

def test_prepare_asyncpg_url_strips_sslmode():
    url = "postgresql+asyncpg://user:pass@host/db?sslmode=require"
    clean, args = prepare_asyncpg_url(url)
    assert "sslmode" not in clean
    assert args == {"ssl": "require"}


def test_prepare_asyncpg_url_neon_host_sets_ssl():
    url = "postgresql+asyncpg://user:pass@ep-foo.c-4.us-east-1.aws.neon.tech/db"
    _, args = prepare_asyncpg_url(url)
    assert args == {"ssl": "require"}


def test_prepare_asyncpg_url_plain_host_no_ssl():
    url = "postgresql+asyncpg://user:pass@localhost/db"
    clean, args = prepare_asyncpg_url(url)
    assert args == {}
    assert "localhost" in clean


def test_prepare_asyncpg_url_preserves_other_params():
    url = "postgresql+asyncpg://user:pass@host/db?sslmode=require&application_name=app"
    clean, args = prepare_asyncpg_url(url)
    assert "application_name=app" in clean
    assert "sslmode" not in clean


# ── auth service: login_with_google ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_with_google_creates_user():
    from app.models.schemas import UserOut
    from app.services import auth as auth_service

    uid = uuid4()
    fake_user_out = UserOut(
        id=uid,
        email="google@test.local",
        name="Google User",
        avatar_url=None,
        default_model="free-chat",
        response_style="balanced",
        memory_enabled=True,
        created_at="2024-01-01T00:00:00",
    )
    settings_obj = __import__("app.core.config", fromlist=["Settings"]).Settings(
        jwt_secret="super-secret-key-that-is-at-least-32-chars!!"
    )
    payload = {
        "sub": "google-sub-123",
        "email": "google@test.local",
        "name": "Google User",
        "picture": None,
    }

    with (
        patch("app.services.auth.verify_google_id_token", return_value=payload),
        patch("app.services.auth.users_repo.get_by_google_sub", AsyncMock(return_value=None)),
        patch("app.services.auth.users_repo.create", AsyncMock(return_value=MagicMock())),
        patch("app.services.auth.create_access_token", return_value="google-tok"),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
    ):
        result = await auth_service.login_with_google(AsyncMock(), settings_obj, "id-token")
    assert result.access_token == "google-tok"
    assert result.user.email == "google@test.local"


@pytest.mark.asyncio
async def test_login_with_google_existing_user():
    from app.models.schemas import UserOut
    from app.services import auth as auth_service

    uid = uuid4()
    fake_user_out = UserOut(
        id=uid,
        email="existing@test.local",
        name="Existing",
        avatar_url=None,
        default_model="free-chat",
        response_style="balanced",
        memory_enabled=True,
        created_at="2024-01-01T00:00:00",
    )
    settings_obj = __import__("app.core.config", fromlist=["Settings"]).Settings(
        jwt_secret="super-secret-key-that-is-at-least-32-chars!!"
    )
    payload = {"sub": "google-sub-456", "email": "existing@test.local"}

    with (
        patch("app.services.auth.verify_google_id_token", return_value=payload),
        patch(
            "app.services.auth.users_repo.get_by_google_sub",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("app.services.auth.create_access_token", return_value="tok2"),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
    ):
        result = await auth_service.login_with_google(AsyncMock(), settings_obj, "id-token")
    assert result.access_token == "tok2"


@pytest.mark.asyncio
async def test_login_dev_raises_when_disabled():
    from app.gateways.google_auth import GoogleAuthError
    from app.services import auth as auth_service

    settings_obj = __import__("app.core.config", fromlist=["Settings"]).Settings(
        dev_auth_enabled=False
    )
    with pytest.raises(GoogleAuthError):
        await auth_service.login_dev(AsyncMock(), settings_obj, email="x@x.com", name="X")


# ── MagicMock import for test_login_with_google ────────────────────────────────

from unittest.mock import MagicMock  # noqa: E402 (needed for the tests above)

"""Targeted coverage for utilities and small code paths."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.database_url import (
    pool_recycle_seconds_for_url,
    prefer_neon_pooler_hostname,
    prepare_asyncpg_url,
)

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
    clean, _args = prepare_asyncpg_url(url)
    assert "application_name=app" in clean
    assert "sslmode" not in clean


def test_prefer_neon_pooler_hostname():
    host = "ep-cool-name-123456.us-east-2.aws.neon.tech"
    assert prefer_neon_pooler_hostname(host) == "ep-cool-name-123456-pooler.us-east-2.aws.neon.tech"
    assert prefer_neon_pooler_hostname("localhost") == "localhost"


def test_prepare_asyncpg_url_neon_pooler_rewrite():
    url = "postgresql+asyncpg://user:pass@ep-foo.us-east-1.aws.neon.tech/db"
    clean, args = prepare_asyncpg_url(url, prefer_neon_pooler=True)
    assert "-pooler." in clean
    assert args == {"ssl": "require"}


def test_pool_recycle_seconds_for_url():
    assert pool_recycle_seconds_for_url("postgresql://ep-x-pooler.neon.tech/db") == 1800
    assert pool_recycle_seconds_for_url("postgresql://localhost/db") == 300


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
        patch("app.services.auth.users_repo.get_by_email", AsyncMock(return_value=None)),
        patch("app.services.auth.users_repo.create", AsyncMock(return_value=MagicMock())),
        patch(
            "app.services.auth.tokens_service.issue_token_pair",
            AsyncMock(return_value=("google-tok", "refresh")),
        ),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
    ):
        result = await auth_service.login_with_google(
            AsyncMock(), settings_obj, "id-token", AsyncMock()
        )
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
        patch(
            "app.services.auth.tokens_service.issue_token_pair",
            AsyncMock(return_value=("tok2", "refresh")),
        ),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
    ):
        result = await auth_service.login_with_google(
            AsyncMock(), settings_obj, "id-token", AsyncMock()
        )
    assert result.access_token == "tok2"


@pytest.mark.asyncio
async def test_login_with_google_links_existing_account_by_email():
    """Google signup after an Apple signup with the same email must link the
    accounts (set google_sub on the existing user) instead of creating a
    duplicate row, which would violate the unique(email) constraint."""
    from app.models.schemas import UserOut
    from app.services import auth as auth_service

    uid = uuid4()
    fake_user_out = UserOut(
        id=uid,
        email="shared@test.local",
        name="Shared",
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
        "sub": "google-sub-new",
        "email": "shared@test.local",
        "name": "Shared",
        "picture": None,
    }
    existing = MagicMock(id=uid, email="shared@test.local")

    create_mock = AsyncMock(return_value=MagicMock())
    update_mock = AsyncMock(return_value=existing)

    with (
        patch("app.services.auth.verify_google_id_token", return_value=payload),
        patch(
            "app.services.auth.users_repo.get_by_google_sub",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.auth.users_repo.get_by_email",
            AsyncMock(return_value=existing),
        ),
        patch("app.services.auth.users_repo.create", create_mock),
        patch("app.services.auth.users_repo.update", update_mock),
        patch(
            "app.services.auth.tokens_service.issue_token_pair",
            AsyncMock(return_value=("linked-tok", "refresh")),
        ),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
    ):
        result = await auth_service.login_with_google(
            AsyncMock(), settings_obj, "id-token", AsyncMock()
        )

    # The existing account must be linked, not duplicated.
    create_mock.assert_not_called()
    # First update links google_sub; second refreshes email/name/avatar.
    assert update_mock.await_count >= 1
    first_call_kwargs = update_mock.call_args_list[0].kwargs
    assert first_call_kwargs.get("google_sub") == "google-sub-new"
    assert result.access_token == "linked-tok"


@pytest.mark.asyncio
async def test_login_with_apple_creates_user():
    from app.models.schemas import UserOut
    from app.services import auth as auth_service

    uid = uuid4()
    fake_user_out = UserOut(
        id=uid,
        email="apple@test.local",
        name="Apple User",
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
        "sub": "apple-sub-123",
        "email": "apple@test.local",
        "email_verified": True,
    }

    with (
        patch(
            "app.services.auth.verify_apple_id_token",
            AsyncMock(return_value=payload),
        ),
        patch("app.services.auth.users_repo.get_by_apple_sub", AsyncMock(return_value=None)),
        patch("app.services.auth.users_repo.get_by_email", AsyncMock(return_value=None)),
        patch("app.services.auth.users_repo.create", AsyncMock(return_value=MagicMock())),
        patch(
            "app.services.auth.tokens_service.issue_token_pair",
            AsyncMock(return_value=("apple-tok", "refresh")),
        ),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
    ):
        result = await auth_service.login_with_apple(
            AsyncMock(), settings_obj, "id-token", AsyncMock(), name="Apple User"
        )
    assert result.access_token == "apple-tok"
    assert result.user.email == "apple@test.local"


@pytest.mark.asyncio
async def test_login_with_apple_existing_user():
    from app.models.schemas import UserOut
    from app.services import auth as auth_service

    uid = uuid4()
    fake_user_out = UserOut(
        id=uid,
        email="apple-existing@test.local",
        name="Existing Apple",
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
        "sub": "apple-sub-456",
        "email": "apple-existing@test.local",
        "email_verified": True,
    }

    with (
        patch(
            "app.services.auth.verify_apple_id_token",
            AsyncMock(return_value=payload),
        ),
        patch(
            "app.services.auth.users_repo.get_by_apple_sub",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "app.services.auth.tokens_service.issue_token_pair",
            AsyncMock(return_value=("tok-apple", "refresh")),
        ),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
    ):
        result = await auth_service.login_with_apple(
            AsyncMock(), settings_obj, "id-token", AsyncMock()
        )
    assert result.access_token == "tok-apple"


@pytest.mark.asyncio
async def test_login_with_apple_links_existing_account_by_email():
    from app.models.schemas import UserOut
    from app.services import auth as auth_service

    uid = uuid4()
    fake_user_out = UserOut(
        id=uid,
        email="shared-apple@test.local",
        name="Shared",
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
        "sub": "apple-sub-new",
        "email": "shared-apple@test.local",
        "email_verified": True,
    }
    existing = MagicMock(id=uid, email="shared-apple@test.local")
    create_mock = AsyncMock(return_value=MagicMock())
    update_mock = AsyncMock(return_value=existing)

    with (
        patch(
            "app.services.auth.verify_apple_id_token",
            AsyncMock(return_value=payload),
        ),
        patch("app.services.auth.users_repo.get_by_apple_sub", AsyncMock(return_value=None)),
        patch("app.services.auth.users_repo.get_by_email", AsyncMock(return_value=existing)),
        patch("app.services.auth.users_repo.create", create_mock),
        patch("app.services.auth.users_repo.update", update_mock),
        patch(
            "app.services.auth.tokens_service.issue_token_pair",
            AsyncMock(return_value=("linked-apple", "refresh")),
        ),
        patch("app.services.auth.UserOut.model_validate", return_value=fake_user_out),
    ):
        result = await auth_service.login_with_apple(
            AsyncMock(), settings_obj, "id-token", AsyncMock()
        )

    create_mock.assert_not_called()
    assert update_mock.await_count >= 1
    first_call_kwargs = update_mock.call_args_list[0].kwargs
    assert first_call_kwargs.get("apple_sub") == "apple-sub-new"
    assert result.access_token == "linked-apple"


@pytest.mark.asyncio
async def test_login_with_apple_requires_email_on_first_sign_in():
    from app.gateways.google_auth import GoogleAuthError
    from app.services import auth as auth_service

    settings_obj = __import__("app.core.config", fromlist=["Settings"]).Settings(
        jwt_secret="super-secret-key-that-is-at-least-32-chars!!"
    )
    payload = {"sub": "apple-sub-no-email", "email_verified": True}

    with (
        patch(
            "app.services.auth.verify_apple_id_token",
            AsyncMock(return_value=payload),
        ),
        patch("app.services.auth.users_repo.get_by_apple_sub", AsyncMock(return_value=None)),
        patch("app.services.auth.users_repo.get_by_email", AsyncMock(return_value=None)),
    ):
        with pytest.raises(GoogleAuthError, match="did not share an email"):
            await auth_service.login_with_apple(AsyncMock(), settings_obj, "id-token", AsyncMock())


@pytest.mark.asyncio
async def test_login_dev_raises_when_disabled():
    from app.gateways.google_auth import GoogleAuthError
    from app.services import auth as auth_service

    settings_obj = __import__("app.core.config", fromlist=["Settings"]).Settings(
        dev_auth_enabled=False
    )
    with pytest.raises(GoogleAuthError):
        await auth_service.login_dev(
            AsyncMock(), settings_obj, email="x@x.com", name="X", redis=AsyncMock()
        )


# ── MagicMock import for test_login_with_google ────────────────────────────────

from unittest.mock import MagicMock

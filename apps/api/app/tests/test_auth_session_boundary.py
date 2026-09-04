"""Identity linking and session failure behavior at sign-in boundaries."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.exceptions import RedisUnavailableError
from app.gateways.google_auth import GoogleAuthError
from app.models.schemas import AppleAuthRequest, DevAuthRequest, GoogleAuthRequest
from app.routers import auth as auth_router
from app.services import auth as auth_service
from app.tests.test_routers import _fake_user


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["google", "apple"])
async def test_email_match_cannot_replace_another_provider_identity(provider):
    existing = _fake_user(email="shared@example.test")
    setattr(existing, f"{provider}_sub", "existing-subject")
    payload = {"sub": "different-subject", "email": existing.email, "email_verified": True}
    with (
        patch(f"app.services.auth.verify_{provider}_id_token", AsyncMock(return_value=payload)),
        patch(f"app.services.auth.users_repo.get_by_{provider}_sub", AsyncMock(return_value=None)),
        patch("app.services.auth.users_repo.get_by_email", AsyncMock(return_value=existing)),
        patch("app.services.auth.users_repo.update", AsyncMock(return_value=existing)) as update,
        patch(
            "app.services.auth.tokens_service.issue_token_pair", AsyncMock(return_value=("a", "r"))
        ) as issue,
    ):
        login = getattr(auth_service, f"login_with_{provider}")
        with pytest.raises(GoogleAuthError, match="already linked"):
            await login(AsyncMock(), Settings(jwt_secret="x" * 32), "id-token", AsyncMock())
    update.assert_not_awaited()
    issue.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider,body,service",
    [
        ("google", GoogleAuthRequest(id_token="id-token"), "login_with_google"),
        ("apple", AppleAuthRequest(id_token="id-token"), "login_with_apple"),
        ("dev", DevAuthRequest(email="dev@example.test", name="Dev"), "login_dev"),
    ],
)
async def test_login_session_store_outage_returns_retryable_503(provider, body, service):
    request = MagicMock()
    request.client.host = "127.0.0.1"
    with (
        patch("app.routers.auth._enforce_login_rate_limit", AsyncMock()),
        patch(
            f"app.routers.auth.auth_service.{service}",
            AsyncMock(side_effect=RedisUnavailableError()),
        ),
    ):
        login = getattr(auth_router, f"{provider}_login")
        with pytest.raises(HTTPException) as caught:
            await login(
                body,
                request,
                session=AsyncMock(),
                settings=Settings(jwt_secret="x" * 32, dev_auth_enabled=True),
                redis=AsyncMock(),
            )
    assert caught.value.status_code == 503
    assert caught.value.headers == {"Retry-After": "5"}

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.gateways.google_oauth import GoogleOAuthError, refresh_access_token


def _settings() -> Settings:
    return Settings(google_client_id="id", google_client_secret="secret")


def _client(status: int, payload: object) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_refresh_invalid_grant_is_permanent():
    with patch(
        "app.gateways.google_oauth.get_pooled_client",
        return_value=_client(400, {"error": "invalid_grant"}),
    ):
        with pytest.raises(GoogleOAuthError) as exc:
            await refresh_access_token(_settings(), "rt")
    assert exc.value.permanent is True


@pytest.mark.asyncio
async def test_refresh_server_error_is_transient():
    with patch(
        "app.gateways.google_oauth.get_pooled_client",
        return_value=_client(500, {"error": "internal"}),
    ):
        with pytest.raises(GoogleOAuthError) as exc:
            await refresh_access_token(_settings(), "rt")
    assert exc.value.permanent is False

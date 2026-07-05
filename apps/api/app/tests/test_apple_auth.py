"""Tests for Sign in with Apple token verification."""

from typing import Any
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import Settings
from app.gateways.apple_auth import verify_apple_id_token
from app.gateways.google_auth import GoogleAuthError


def _make_apple_token(
    *, sub: str = "apple-user-1", email: str = "user@privaterelay.appleid.com"
) -> tuple[str, str, dict[str, Any]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(public_key)
    import json

    kid = "test-kid"
    token = jwt.encode(
        {
            "iss": "https://appleid.apple.com",
            "aud": "com.recall.app",
            "sub": sub,
            "email": email,
            "email_verified": True,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )
    return token, kid, json.loads(jwk)


@pytest.mark.asyncio
async def test_verify_apple_id_token_accepts_valid_token():
    token, kid, jwk = _make_apple_token()
    settings = Settings(apple_client_id="com.recall.app")
    jwks = {"keys": [{**jwk, "kid": kid, "alg": "RS256", "use": "sig"}]}

    with patch("app.gateways.apple_auth._fetch_apple_jwks", AsyncMock(return_value=jwks)):
        payload = await verify_apple_id_token(token, settings)

    assert payload["sub"] == "apple-user-1"
    assert payload["email"] == "user@privaterelay.appleid.com"


@pytest.mark.asyncio
async def test_verify_apple_id_token_rejects_wrong_audience():
    token, kid, jwk = _make_apple_token()
    settings = Settings(apple_client_id="com.other.app")
    jwks = {"keys": [{**jwk, "kid": kid, "alg": "RS256", "use": "sig"}]}

    with (
        patch("app.gateways.apple_auth._fetch_apple_jwks", AsyncMock(return_value=jwks)),
        pytest.raises(GoogleAuthError, match="Invalid Apple ID token"),
    ):
        await verify_apple_id_token(token, settings)


@pytest.mark.asyncio
async def test_verify_apple_id_token_requires_server_config():
    settings = Settings(apple_client_id="")
    with pytest.raises(GoogleAuthError, match="not configured"):
        await verify_apple_id_token("bad.token.here", settings)


@pytest.mark.asyncio
async def test_public_key_for_kid_refetches_jwks_on_kid_miss():
    import time

    import app.gateways.apple_auth as apple_auth

    _, kid, jwk = _make_apple_token()
    jwks = {"keys": [{**jwk, "kid": kid, "alg": "RS256", "use": "sig"}]}
    apple_auth._jwks_cache = {"keys": []}
    apple_auth._jwks_fetched_at = time.time()

    with patch(
        "app.gateways.apple_auth._fetch_apple_jwks",
        AsyncMock(side_effect=[{"keys": []}, jwks]),
    ) as fetch:
        key = await apple_auth._public_key_for_kid(kid)

    assert key is not None
    assert fetch.call_count == 2
    # Second call is a forced refresh, not a second reliance on the stale cache.
    fetch.assert_any_call(force_refresh=True)


@pytest.mark.asyncio
async def test_fetch_apple_jwks_uses_cache_within_ttl():
    import time

    import app.gateways.apple_auth as apple_auth

    cached = {"keys": [{"kid": "cached"}]}
    apple_auth._jwks_cache = cached
    apple_auth._jwks_fetched_at = time.time()

    with patch("app.gateways.apple_auth.httpx.AsyncClient") as mock_client_cls:
        result = await apple_auth._fetch_apple_jwks()

    assert result is cached
    mock_client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_apple_jwks_force_refresh_bypasses_cache():
    import time

    import app.gateways.apple_auth as apple_auth

    apple_auth._jwks_cache = {"keys": [{"kid": "stale"}]}
    apple_auth._jwks_fetched_at = time.time()

    fresh = {"keys": [{"kid": "fresh"}]}
    client_instance = AsyncMock()
    client_instance.__aenter__ = AsyncMock(return_value=client_instance)
    response = AsyncMock()
    response.raise_for_status = lambda: None
    response.json = lambda: fresh
    client_instance.get = AsyncMock(return_value=response)

    with patch("app.gateways.apple_auth.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value = client_instance
        result = await apple_auth._fetch_apple_jwks(force_refresh=True)

    assert result == fresh
    client_instance.get.assert_awaited_once_with(apple_auth.APPLE_JWKS_URL)

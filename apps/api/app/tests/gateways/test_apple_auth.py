"""Tests for Sign in with Apple token verification."""

import hashlib
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import Settings
from app.gateways.apple_auth import verify_apple_id_token
from app.gateways.google_auth import GoogleAuthError

RAW_NONCE = "raw-nonce-from-the-app"
_UNSET: Any = object()


def _make_apple_token(
    *,
    sub: str = "apple-user-1",
    email: str = "user@privaterelay.appleid.com",
    nonce: Any = _UNSET,
    exp: Any = _UNSET,
) -> tuple[str, str, dict[str, Any]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(public_key)
    import json

    kid = "test-kid"
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": "https://appleid.apple.com",
        "aud": "com.recall.app",
        "sub": sub,
        "email": email,
        "email_verified": True,
        "iat": now,
        "exp": now + 600 if exp is _UNSET else exp,
        # The app passes SHA-256(raw nonce) to Apple; Apple echoes it here.
        "nonce": hashlib.sha256(RAW_NONCE.encode()).hexdigest() if nonce is _UNSET else nonce,
    }
    token = jwt.encode(
        {key: value for key, value in claims.items() if value is not None},
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )
    return token, kid, json.loads(jwk)


def _jwks(kid: str, jwk: dict[str, Any]) -> dict[str, Any]:
    return {"keys": [{**jwk, "kid": kid, "alg": "RS256", "use": "sig"}]}


@pytest.mark.asyncio
async def test_verify_apple_id_token_accepts_valid_token():
    token, kid, jwk = _make_apple_token()
    settings = Settings(apple_client_id="com.recall.app")

    with patch(
        "app.gateways.apple_auth._fetch_apple_jwks", AsyncMock(return_value=_jwks(kid, jwk))
    ):
        payload = await verify_apple_id_token(token, settings, nonce=RAW_NONCE)

    assert payload["sub"] == "apple-user-1"
    assert payload["email"] == "user@privaterelay.appleid.com"


@pytest.mark.asyncio
async def test_verify_apple_id_token_rejects_wrong_audience():
    token, kid, jwk = _make_apple_token()
    settings = Settings(apple_client_id="com.other.app")

    with (
        patch("app.gateways.apple_auth._fetch_apple_jwks", AsyncMock(return_value=_jwks(kid, jwk))),
        pytest.raises(GoogleAuthError, match="Invalid Apple ID token"),
    ):
        await verify_apple_id_token(token, settings, nonce=RAW_NONCE)


@pytest.mark.parametrize(
    "token_nonce, sent_nonce",
    [
        # A token replayed from another sign-in carries that sign-in's nonce.
        ("sha256-of-some-other-nonce", RAW_NONCE),
        # The app sent no nonce, or the token was minted without one.
        (_UNSET, None),
        (_UNSET, ""),
        (None, RAW_NONCE),
        # The raw value itself must not be accepted in place of its hash.
        (RAW_NONCE, RAW_NONCE),
    ],
)
@pytest.mark.asyncio
async def test_verify_apple_id_token_rejects_a_token_not_bound_to_this_sign_in(
    token_nonce, sent_nonce
):
    token, kid, jwk = _make_apple_token(nonce=token_nonce)
    settings = Settings(apple_client_id="com.recall.app")

    with (
        patch("app.gateways.apple_auth._fetch_apple_jwks", AsyncMock(return_value=_jwks(kid, jwk))),
        pytest.raises(GoogleAuthError, match="Invalid Apple ID token"),
    ):
        await verify_apple_id_token(token, settings, nonce=sent_nonce)


@pytest.mark.parametrize("exp", [None, 1_000])
@pytest.mark.asyncio
async def test_verify_apple_id_token_rejects_missing_or_past_expiry(exp):
    token, kid, jwk = _make_apple_token(exp=exp)
    settings = Settings(apple_client_id="com.recall.app")

    with (
        patch("app.gateways.apple_auth._fetch_apple_jwks", AsyncMock(return_value=_jwks(kid, jwk))),
        pytest.raises(GoogleAuthError, match="Invalid Apple ID token"),
    ):
        await verify_apple_id_token(token, settings, nonce=RAW_NONCE)


@pytest.mark.asyncio
async def test_verify_apple_id_token_requires_server_config():
    settings = Settings(apple_client_id="")
    with pytest.raises(GoogleAuthError, match="not configured"):
        await verify_apple_id_token("bad.token.here", settings, nonce=RAW_NONCE)


@pytest.mark.asyncio
async def test_public_key_for_kid_refetches_jwks_on_kid_miss(monkeypatch: pytest.MonkeyPatch):
    import time

    import app.gateways.apple_auth as apple_auth

    _, kid, jwk = _make_apple_token()
    jwks = {"keys": [{**jwk, "kid": kid, "alg": "RS256", "use": "sig"}]}
    monkeypatch.setattr(apple_auth, "_jwks_cache", {"keys": []})
    monkeypatch.setattr(apple_auth, "_jwks_fetched_at", time.time())

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
async def test_fetch_apple_jwks_uses_cache_within_ttl(monkeypatch: pytest.MonkeyPatch):
    import time

    import app.gateways.apple_auth as apple_auth

    cached = {"keys": [{"kid": "cached"}]}
    monkeypatch.setattr(apple_auth, "_jwks_cache", cached)
    monkeypatch.setattr(apple_auth, "_jwks_fetched_at", time.time())

    with patch("app.gateways.apple_auth.get_pooled_client") as mock_client_cls:
        result = await apple_auth._fetch_apple_jwks()

    assert result is cached
    mock_client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_apple_jwks_force_refresh_bypasses_cache(monkeypatch: pytest.MonkeyPatch):
    import time

    import app.gateways.apple_auth as apple_auth

    monkeypatch.setattr(apple_auth, "_jwks_cache", {"keys": [{"kid": "stale"}]})
    monkeypatch.setattr(apple_auth, "_jwks_fetched_at", time.time())

    fresh = {"keys": [{"kid": "fresh"}]}
    client_instance = AsyncMock()
    client_instance.__aenter__ = AsyncMock(return_value=client_instance)
    response = AsyncMock()
    response.raise_for_status = lambda: None
    response.json = lambda: fresh
    client_instance.get = AsyncMock(return_value=response)

    with patch("app.gateways.apple_auth.get_pooled_client") as mock_client_cls:
        mock_client_cls.return_value = client_instance
        result = await apple_auth._fetch_apple_jwks(force_refresh=True)

    assert result == fresh
    client_instance.get.assert_awaited_once_with(apple_auth.APPLE_JWKS_URL)

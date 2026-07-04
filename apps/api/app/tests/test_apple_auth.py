"""Tests for Sign in with Apple token verification."""

from typing import Any
from unittest.mock import patch

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


def test_verify_apple_id_token_accepts_valid_token():
    token, kid, jwk = _make_apple_token()
    settings = Settings(apple_client_id="com.recall.app")
    jwks = {"keys": [{**jwk, "kid": kid, "alg": "RS256", "use": "sig"}]}

    with patch("app.gateways.apple_auth._fetch_apple_jwks", return_value=jwks):
        payload = verify_apple_id_token(token, settings)

    assert payload["sub"] == "apple-user-1"
    assert payload["email"] == "user@privaterelay.appleid.com"


def test_verify_apple_id_token_rejects_wrong_audience():
    token, kid, jwk = _make_apple_token()
    settings = Settings(apple_client_id="com.other.app")
    jwks = {"keys": [{**jwk, "kid": kid, "alg": "RS256", "use": "sig"}]}

    with (
        patch("app.gateways.apple_auth._fetch_apple_jwks", return_value=jwks),
        pytest.raises(GoogleAuthError, match="Invalid Apple ID token"),
    ):
        verify_apple_id_token(token, settings)


def test_verify_apple_id_token_requires_server_config():
    settings = Settings(apple_client_id="")
    with pytest.raises(GoogleAuthError, match="not configured"):
        verify_apple_id_token("bad.token.here", settings)


def test_public_key_for_kid_refetches_jwks_on_kid_miss():
    import time

    import app.gateways.apple_auth as apple_auth

    _, kid, jwk = _make_apple_token()
    jwks = {"keys": [{**jwk, "kid": kid, "alg": "RS256", "use": "sig"}]}
    apple_auth._jwks_cache = {"keys": []}
    apple_auth._jwks_fetched_at = time.time()

    with patch(
        "app.gateways.apple_auth._fetch_apple_jwks",
        side_effect=[{"keys": []}, jwks],
    ) as fetch:
        key = apple_auth._public_key_for_kid(kid)

    assert key is not None
    assert fetch.call_count == 2


def test_fetch_apple_jwks_uses_cache_within_ttl():
    import time

    import app.gateways.apple_auth as apple_auth

    cached = {"keys": [{"kid": "cached"}]}
    apple_auth._jwks_cache = cached
    apple_auth._jwks_fetched_at = time.time()

    with patch("app.gateways.apple_auth.httpx.get") as get:
        assert apple_auth._fetch_apple_jwks() is cached
    get.assert_not_called()

"""Verify Sign in with Apple identity tokens (JWT from Apple ID)."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

from app.core.config import Settings
from app.gateways.google_auth import GoogleAuthError

logger = logging.getLogger(__name__)

APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"
_JWKS_TTL_SECONDS = 3600
_jwks_cache: dict[str, Any] | None = None
_jwks_fetched_at: float = 0.0


def _fetch_apple_jwks() -> dict[str, Any]:
    global _jwks_cache, _jwks_fetched_at
    now = time.time()
    if _jwks_cache is not None and now - _jwks_fetched_at < _JWKS_TTL_SECONDS:
        return _jwks_cache
    response = httpx.get(APPLE_JWKS_URL, timeout=10.0)
    response.raise_for_status()
    parsed: dict[str, Any] = response.json()
    _jwks_cache = parsed
    _jwks_fetched_at = now
    return parsed


def _public_key_for_kid(kid: str) -> Any:
    jwks = _fetch_apple_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return RSAAlgorithm.from_jwk(key)
    _jwks_cache = None
    jwks = _fetch_apple_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return RSAAlgorithm.from_jwk(key)
    raise GoogleAuthError("Apple signing key not found")


def verify_apple_id_token(id_token_str: str, settings: Settings) -> dict[str, Any]:
    client_id = settings.apple_client_id.strip()
    if not client_id:
        raise GoogleAuthError("Apple Sign-In is not configured on this server")

    try:
        header = jwt.get_unverified_header(id_token_str)
        public_key = _public_key_for_kid(str(header["kid"]))
        payload = jwt.decode(
            id_token_str,
            public_key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=APPLE_ISSUER,
        )
    except (jwt.PyJWTError, KeyError, httpx.HTTPError) as exc:
        logger.warning("Apple ID token verification failed: %s", exc)
        raise GoogleAuthError("Invalid Apple ID token") from exc

    sub = payload.get("sub")
    if not sub:
        raise GoogleAuthError("Invalid Apple ID token")

    return payload

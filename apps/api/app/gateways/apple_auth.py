"""Verify Sign in with Apple identity tokens (JWT from Apple ID)."""

from __future__ import annotations

import asyncio
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
# Single-flights concurrent refreshes so a cache expiry (or a kid miss, which
# forces one) doesn't fire a fetch per in-flight sign-in — and, since the
# fetch is async, keeps the check-then-fetch race-free across coroutines.
_jwks_lock = asyncio.Lock()


def _cache_is_fresh() -> bool:
    return _jwks_cache is not None and time.time() - _jwks_fetched_at < _JWKS_TTL_SECONDS


async def _fetch_apple_jwks(*, force_refresh: bool = False) -> dict[str, Any]:
    global _jwks_cache, _jwks_fetched_at
    if not force_refresh and _cache_is_fresh():
        return _jwks_cache  # type: ignore[return-value]

    async with _jwks_lock:
        # Re-check inside the lock: another coroutine may have just refreshed
        # it while we were waiting, so we don't fetch a second time in a row.
        if not force_refresh and _cache_is_fresh():
            return _jwks_cache  # type: ignore[return-value]
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(APPLE_JWKS_URL)
        response.raise_for_status()
        parsed: dict[str, Any] = response.json()
        _jwks_cache = parsed
        _jwks_fetched_at = time.time()
        return parsed


async def _public_key_for_kid(kid: str) -> Any:
    jwks = await _fetch_apple_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return RSAAlgorithm.from_jwk(key)
    # Unknown kid: our cache may just be stale (Apple rotated keys since our
    # last fetch), so force one refresh before giving up.
    jwks = await _fetch_apple_jwks(force_refresh=True)
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return RSAAlgorithm.from_jwk(key)
    raise GoogleAuthError("Apple signing key not found")


async def verify_apple_id_token(id_token_str: str, settings: Settings) -> dict[str, Any]:
    client_id = settings.apple_client_id.strip()
    if not client_id:
        raise GoogleAuthError("Apple Sign-In is not configured on this server")

    try:
        header = jwt.get_unverified_header(id_token_str)
        public_key = await _public_key_for_kid(str(header["kid"]))
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

"""App JWT access tokens: create, decode, and the per-request revocation check.

Every authenticated request verifies its token here (``app.core.deps``). The
account module issues, rotates and revokes sessions, and writes the revocation
keys this module reads. Not Google OAuth.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.exceptions import RedisUnavailableError
from app.gateways.google_auth import GoogleAuthError

logger = logging.getLogger(__name__)

REVOKED_PREFIX = "revoked:jti:"
REVOKED_SESSION_PREFIX = "revoked:sid:"
REVOKED_SINCE_PREFIX = "revoked_since:"


def redis_str(value: str | bytes) -> str:
    """Normalize a Redis reply that may be bytes or str (decode_responses varies)."""
    return value.decode() if isinstance(value, bytes) else value


def revoked_key(jti: str) -> str:
    return f"{REVOKED_PREFIX}{jti}"


def revoked_session_key(session_id: str) -> str:
    """One signed-in device (the ``sid`` claim), revoked from another device."""
    return f"{REVOKED_SESSION_PREFIX}{session_id}"


def revoked_since_key(user_id: UUID) -> str:
    return f"{REVOKED_SINCE_PREFIX}{user_id}"


class AccessTokenError(Exception):
    """Raised when an access JWT is missing, malformed, or otherwise invalid."""


def create_access_token(user_id: UUID, settings: Settings, *, session_id: str | None = None) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload: dict[str, object] = {
        "sub": str(user_id),
        "exp": expire,
        # Keep subsecond precision so a fresh sign-in after session revocation
        # in the same second is newer than the Redis revocation cutoff.
        "iat": now.timestamp(),
        "jti": secrets.token_urlsafe(16),
    }
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise AccessTokenError("Invalid access token") from exc


async def is_access_revoked(redis: Redis, jti: str) -> bool:
    return bool(await redis.get(revoked_key(jti)))


async def is_session_revoked(redis: Redis, session_id: str) -> bool:
    return bool(await redis.get(revoked_session_key(session_id)))


async def _is_access_revoked_since(redis: Redis, user_id: UUID, issued_at: float | None) -> bool:
    if issued_at is None:
        return False
    revoked_since_raw = await redis.get(revoked_since_key(user_id))
    if revoked_since_raw is None:
        return False
    revoked_since = float(redis_str(revoked_since_raw))
    return issued_at <= revoked_since


async def verify_access_token(redis: Redis, token: str, settings: Settings) -> UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise GoogleAuthError("Invalid access token") from exc
    jti = payload.get("jti")
    sid = payload.get("sid")
    try:
        if jti and await is_access_revoked(redis, str(jti)):
            raise GoogleAuthError("Token revoked")
        if isinstance(sid, str) and sid and await is_session_revoked(redis, sid):
            raise GoogleAuthError("Token revoked")
        user_id = UUID(payload["sub"])
        if await _is_access_revoked_since(redis, user_id, payload.get("iat")):
            raise GoogleAuthError("Token revoked")
    except GoogleAuthError:
        raise
    except RedisError as exc:
        # Fail closed: without Redis we cannot check jti / revoked_since.
        # Surface as 503 (not 401) so clients retry instead of forcing re-login.
        logger.warning("Access token revocation check failed; Redis unavailable", exc_info=True)
        raise RedisUnavailableError() from exc
    return user_id

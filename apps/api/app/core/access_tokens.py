"""App JWT access tokens: create, decode, and the per-request revocation check.

Every authenticated request verifies its token here (``app.core.deps``). The
account module issues, rotates and revokes sessions, and writes the revocation
keys this module reads. Not Google OAuth. The same round trip reads the user
row's generation, which says whether this process's copy of the row is current
(``core/user_cache``).
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core import user_cache
from app.core.cache_generation import generation_from
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


def _revocation_keys(payload: dict[str, Any], user_id: UUID) -> tuple[list[str], str | None]:
    """The keys that revoke this token when set, and its user's revoked-since cutoff key.

    A token without a ``jti``, ``sid`` or ``iat`` claim has nothing of that kind to check.
    """
    markers: list[str] = []
    jti = payload.get("jti")
    if jti:
        markers.append(revoked_key(str(jti)))
    sid = payload.get("sid")
    if isinstance(sid, str) and sid:
        markers.append(revoked_session_key(sid))
    since = revoked_since_key(user_id) if payload.get("iat") is not None else None
    return markers, since


@dataclass(frozen=True)
class AccessCheck:
    """A live token's user, and that user row's current generation (``core/user_cache``)."""

    user_id: UUID
    user_generation: str


async def check_access(redis: Redis, token: str, settings: Settings) -> AccessCheck:
    """The token's user once no revocation names it, with the user row's generation.

    Every revocation key (this token, its signed-in device, the user's cutoff)
    and the generation are read in one MGET: this runs before every
    authenticated request and every chat frame, so it is one Redis round trip.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise GoogleAuthError("Invalid access token") from exc
    user_id = UUID(payload["sub"])
    markers, since = _revocation_keys(payload, user_id)
    keys = [*markers, user_cache.generation_key(user_id), *([since] if since else [])]
    try:
        values = await redis.mget(keys)
    except RedisError as exc:
        # Fail closed: without Redis we cannot check jti / revoked_since.
        # Surface as 503 (not 401) so clients retry instead of forcing re-login.
        logger.warning("Access token revocation check failed; Redis unavailable", exc_info=True)
        raise RedisUnavailableError() from exc
    if any(values[: len(markers)]):
        raise GoogleAuthError("Token revoked")
    since_raw = values[-1] if since else None
    if since_raw is not None and payload["iat"] <= float(redis_str(since_raw)):
        raise GoogleAuthError("Token revoked")
    return AccessCheck(user_id=user_id, user_generation=generation_from(values[len(markers)]))


async def verify_access_token(redis: Redis, token: str, settings: Settings) -> UUID:
    """The token's user once no revocation names it (``check_access`` without the row)."""
    return (await check_access(redis, token, settings)).user_id

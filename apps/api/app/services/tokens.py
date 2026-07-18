"""JWT access + refresh token lifecycle (Redis-backed refresh, jti revocation).

Refresh tokens rotate on every use. To detect theft, a rotated-out token
isn't just deleted — it's tombstoned for a grace window. If that exact
token is ever presented again (the only way that happens legitimately
never occurs, since the real client always moves on to its newest token),
it's treated as a compromise signal: every refresh token for that user is
revoked, and a per-user "revoked since" timestamp forces every access
token issued before that moment to fail verification too, even ones that
haven't naturally expired yet.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from uuid import UUID

import jwt
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_tokens import create_access_token
from app.core.config import Settings
from app.gateways.google_auth import GoogleAuthError
from app.models.schemas import UserOut
from app.repositories import users as users_repo

logger = logging.getLogger(__name__)

_REFRESH_PREFIX = "refresh:"
_REVOKED_PREFIX = "revoked:jti:"
_REFRESH_TOMBSTONE_PREFIX = "refresh_used:"
_USER_REFRESH_SET_PREFIX = "refresh_user:"
_REVOKED_SINCE_PREFIX = "revoked_since:"

# How long a rotated-out refresh token is remembered as "already used" —
# long enough to catch a delayed reuse attempt (e.g. an attacker replaying a
# stolen token after the legitimate device already rotated it), short enough
# to bound Redis growth. Independent of the refresh token's own TTL.
_REUSE_DETECTION_WINDOW_SECONDS = 24 * 60 * 60


def _redis_str(value: str | bytes) -> str:
    """Normalize a Redis reply that may be bytes or str (decode_responses varies)."""
    return value.decode() if isinstance(value, bytes) else value


def _refresh_key(token: str) -> str:
    return f"{_REFRESH_PREFIX}{token}"


def _revoked_key(jti: str) -> str:
    return f"{_REVOKED_PREFIX}{jti}"


def _tombstone_key(token: str) -> str:
    return f"{_REFRESH_TOMBSTONE_PREFIX}{token}"


def _user_refresh_set_key(user_id: UUID) -> str:
    return f"{_USER_REFRESH_SET_PREFIX}{user_id}"


def _revoked_since_key(user_id: UUID) -> str:
    return f"{_REVOKED_SINCE_PREFIX}{user_id}"


async def issue_token_pair(redis: Redis, user_id: UUID, settings: Settings) -> tuple[str, str]:
    access_token = create_access_token(user_id, settings)
    refresh_token = secrets.token_urlsafe(32)
    ttl = settings.jwt_refresh_expire_days * 86_400
    await redis.set(_refresh_key(refresh_token), str(user_id), ex=ttl)
    user_set_key = _user_refresh_set_key(user_id)
    await redis.sadd(user_set_key, refresh_token)
    await redis.expire(user_set_key, ttl)
    return access_token, refresh_token


async def _revoke_all_refresh_tokens(redis: Redis, user_id: UUID, settings: Settings) -> None:
    """Kill every refresh token for this user and force existing access
    tokens to re-authenticate — the response to a detected reuse."""
    user_set_key = _user_refresh_set_key(user_id)
    tokens = await redis.smembers(user_set_key)
    if tokens:
        keys = [_refresh_key(_redis_str(t)) for t in tokens]
        await redis.delete(*keys)
    await redis.delete(user_set_key)
    # Any access token issued before now is treated as revoked, regardless of
    # its own exp — bounded by how long an access token can live so the
    # marker doesn't need to be kept forever.
    await redis.set(
        _revoked_since_key(user_id),
        datetime.now(UTC).timestamp(),
        ex=max(60, settings.jwt_expire_minutes * 60),
    )


async def purge_user_sessions(redis: Redis, user_id: UUID, settings: Settings) -> None:
    """Revoke every refresh token + outstanding access token for a user.

    Used on account deletion — without this, a logged-in client keeps a
    working access token after `DELETE /auth/me` and can still hit endpoints
    until the token's own exp (the DB user check is the only remaining gate).
    Best-effort: Redis failures are logged but never block the delete.
    """
    try:
        await _revoke_all_refresh_tokens(redis, user_id, settings)
    except Exception:  # never block account deletion on Redis
        logger.exception("purge_user_sessions failed user_id=%s", user_id)


async def refresh_token_pair(
    redis: Redis,
    refresh_token: str,
    session: AsyncSession,
    settings: Settings,
) -> tuple[str, str, UserOut]:
    user_id_raw = await redis.get(_refresh_key(refresh_token))
    if user_id_raw is None:
        tombstoned = await redis.get(_tombstone_key(refresh_token))
        if tombstoned is not None:
            stolen_user_id = UUID(_redis_str(tombstoned))
            logger.warning(
                "Refresh token reuse detected for user_id=%s — revoking all sessions",
                stolen_user_id,
            )
            await _revoke_all_refresh_tokens(redis, stolen_user_id, settings)
        raise GoogleAuthError("Invalid refresh token")
    user_id = UUID(_redis_str(user_id_raw))

    user = await users_repo.get_by_id(session, user_id)
    if user is None:
        await redis.delete(_refresh_key(refresh_token))
        raise GoogleAuthError("User not found")

    # Rotate: retire this token (tombstoned so a later reuse is detectable)
    # and drop it from the user's live set before issuing the replacement.
    await redis.delete(_refresh_key(refresh_token))
    await redis.set(_tombstone_key(refresh_token), str(user_id), ex=_REUSE_DETECTION_WINDOW_SECONDS)
    await redis.srem(_user_refresh_set_key(user_id), refresh_token)
    access_token, new_refresh = await issue_token_pair(redis, user_id, settings)
    return access_token, new_refresh, UserOut.model_validate(user)


async def revoke_access_token(redis: Redis, access_token: str, settings: Settings) -> None:
    try:
        payload = jwt.decode(access_token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return
    ttl = max(1, int(exp - datetime.now(UTC).timestamp()))
    await redis.set(_revoked_key(str(jti)), "1", ex=ttl)


async def revoke_refresh_token(redis: Redis, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    user_id_raw = await redis.get(_refresh_key(refresh_token))
    await redis.delete(_refresh_key(refresh_token))
    if user_id_raw is not None:
        user_id = UUID(_redis_str(user_id_raw))
        await redis.srem(_user_refresh_set_key(user_id), refresh_token)


async def is_access_revoked(redis: Redis, jti: str) -> bool:
    return bool(await redis.get(_revoked_key(jti)))


async def _is_access_revoked_since(redis: Redis, user_id: UUID, issued_at: float | None) -> bool:
    if issued_at is None:
        return False
    revoked_since_raw = await redis.get(_revoked_since_key(user_id))
    if revoked_since_raw is None:
        return False
    revoked_since = float(_redis_str(revoked_since_raw))
    return issued_at <= revoked_since


async def verify_access_token(redis: Redis, token: str, settings: Settings) -> UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise GoogleAuthError("Invalid access token") from exc
    jti = payload.get("jti")
    if jti and await is_access_revoked(redis, str(jti)):
        raise GoogleAuthError("Token revoked")
    user_id = UUID(payload["sub"])
    if await _is_access_revoked_since(redis, user_id, payload.get("iat")):
        raise GoogleAuthError("Token revoked")
    return user_id

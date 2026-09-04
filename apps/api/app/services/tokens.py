"""JWT access + refresh lifecycle with Redis rotation and revocation.

Rotated-out refresh tokens are tombstoned. Reuse revokes the user's refresh
sessions and older access tokens. This strict policy also rejects a retry
when a successful rotation's response was lost.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from typing import NoReturn
from uuid import UUID

import jwt
from redis.asyncio import Redis
from redis.exceptions import RedisError, WatchError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_tokens import create_access_token
from app.core.config import Settings
from app.exceptions import RedisUnavailableError
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
_MAX_SESSION_TRANSACTION_ATTEMPTS = 3


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
    user_set_key = _user_refresh_set_key(user_id)
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.set(_refresh_key(refresh_token), str(user_id), ex=ttl)
            pipe.sadd(user_set_key, refresh_token)
            pipe.expire(user_set_key, ttl)
            await pipe.execute()
    except RedisError as exc:
        logger.warning("Token issue failed; Redis unavailable", exc_info=True)
        raise RedisUnavailableError() from exc
    return access_token, refresh_token


async def _revoke_all_refresh_tokens(redis: Redis, user_id: UUID, settings: Settings) -> None:
    """Revoke the complete live set atomically, including concurrent rotations."""
    user_set_key = _user_refresh_set_key(user_id)
    async with redis.pipeline(transaction=True) as pipe:
        for _ in range(_MAX_SESSION_TRANSACTION_ATTEMPTS):
            try:
                await pipe.watch(user_set_key)
                live_tokens = await pipe.smembers(user_set_key)
                pipe.multi()
                if live_tokens:
                    pipe.delete(*[_refresh_key(_redis_str(t)) for t in live_tokens])
                pipe.delete(user_set_key)
                pipe.set(
                    _revoked_since_key(user_id),
                    datetime.now(UTC).timestamp(),
                    ex=max(60, settings.jwt_expire_minutes * 60),
                )
                await pipe.execute()
                return
            except WatchError:
                # A new login or rotation changed the live set. Include it in
                # the next snapshot instead of leaving an untracked session.
                continue
    raise RedisUnavailableError()


async def purge_user_sessions(redis: Redis, user_id: UUID, settings: Settings) -> None:
    """Revoke every refresh token + outstanding access token for a user.

    Used on account deletion — without this, a logged-in client keeps a
    working access token after `DELETE /auth/me` and can still hit endpoints
    until the token's own exp (the DB user check is the only remaining gate).

    M1: Redis failures are NOT swallowed — if we can't purge sessions, the
    delete fails (503) so the client knows to retry. Silently succeeding
    leaves live sessions that can call the API until JWT expiry.
    """
    try:
        await _revoke_all_refresh_tokens(redis, user_id, settings)
    except RedisError as exc:
        logger.warning("Session purge failed; Redis unavailable", exc_info=True)
        raise RedisUnavailableError() from exc


async def _reject_invalid_refresh(redis: Redis, refresh_token: str, settings: Settings) -> NoReturn:
    tombstoned = await redis.get(_tombstone_key(refresh_token))
    if tombstoned is not None:
        user_id = UUID(_redis_str(tombstoned))
        logger.warning(
            "Refresh token reuse detected for user_id=%s — revoking all sessions", user_id
        )
        await _revoke_all_refresh_tokens(redis, user_id, settings)
    raise GoogleAuthError("Invalid refresh token")


async def refresh_token_pair(
    redis: Redis,
    refresh_token: str,
    session: AsyncSession,
    settings: Settings,
) -> tuple[str, str, UserOut]:
    try:
        key = _refresh_key(refresh_token)
        user_id_raw = await redis.get(key)
        if user_id_raw is None:
            await _reject_invalid_refresh(redis, refresh_token, settings)
        user_id = UUID(_redis_str(user_id_raw))

        # Finish fallible DB reads / response validation before consuming the
        # credential. A transient failure must leave it available for retry.
        user = await users_repo.get_by_id(session, user_id)
        if user is None:
            await revoke_refresh_token(redis, refresh_token)
            raise GoogleAuthError("User not found")
        user_out = UserOut.model_validate(user)
        access_token = create_access_token(user_id, settings)
        new_refresh = secrets.token_urlsafe(32)
        ttl = settings.jwt_refresh_expire_days * 86_400
        user_set_key = _user_refresh_set_key(user_id)
        async with redis.pipeline(transaction=True) as pipe:
            try:
                await pipe.watch(key)
                if await pipe.get(key) != user_id_raw:
                    await _reject_invalid_refresh(redis, refresh_token, settings)
                pipe.multi()
                pipe.delete(key)
                pipe.set(
                    _tombstone_key(refresh_token),
                    str(user_id),
                    ex=_REUSE_DETECTION_WINDOW_SECONDS,
                )
                pipe.srem(user_set_key, refresh_token)
                pipe.set(_refresh_key(new_refresh), str(user_id), ex=ttl)
                pipe.sadd(user_set_key, new_refresh)
                pipe.expire(user_set_key, ttl)
                await pipe.execute()
            except WatchError as exc:
                if await redis.get(key) == user_id_raw:
                    # Redis also reports lost WATCH connections as WatchError.
                    # The credential is still live: let the client retry it.
                    raise RedisUnavailableError() from exc
                # Logout/purge or another refresh won. Never recreate a session
                # that disappeared while the DB lookup or transaction ran.
                await _reject_invalid_refresh(redis, refresh_token, settings)
    except RedisError as exc:
        logger.warning("Refresh token Redis op failed; Redis unavailable", exc_info=True)
        raise RedisUnavailableError() from exc
    return access_token, new_refresh, user_out


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
    try:
        await redis.set(_revoked_key(str(jti)), "1", ex=ttl)
    except RedisError as exc:
        logger.warning("Access token revoke failed; Redis unavailable", exc_info=True)
        raise RedisUnavailableError() from exc


async def revoke_refresh_token(redis: Redis, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    try:
        async with redis.pipeline(transaction=True) as pipe:
            for _ in range(_MAX_SESSION_TRANSACTION_ATTEMPTS):
                try:
                    key = _refresh_key(refresh_token)
                    await pipe.watch(key)
                    user_id_raw = await pipe.get(key)
                    pipe.multi()
                    pipe.delete(key)
                    if user_id_raw is not None:
                        user_id = UUID(_redis_str(user_id_raw))
                        pipe.srem(_user_refresh_set_key(user_id), refresh_token)
                    await pipe.execute()
                    return
                except WatchError:
                    continue
        raise RedisUnavailableError()
    except RedisError as exc:
        logger.warning("Refresh token revoke failed; Redis unavailable", exc_info=True)
        raise RedisUnavailableError() from exc


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
    try:
        if jti and await is_access_revoked(redis, str(jti)):
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

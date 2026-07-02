"""JWT access + refresh token lifecycle (Redis-backed refresh, jti revocation)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from uuid import UUID

import jwt
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways.google_auth import GoogleAuthError, create_access_token
from app.models.schemas import UserOut
from app.repositories import users as users_repo

_REFRESH_PREFIX = "refresh:"
_REVOKED_PREFIX = "revoked:jti:"


def _refresh_key(token: str) -> str:
    return f"{_REFRESH_PREFIX}{token}"


def _revoked_key(jti: str) -> str:
    return f"{_REVOKED_PREFIX}{jti}"


async def issue_token_pair(redis: Redis, user_id: UUID, settings: Settings) -> tuple[str, str]:
    access_token = create_access_token(user_id, settings)
    refresh_token = secrets.token_urlsafe(32)
    ttl = settings.jwt_refresh_expire_days * 86_400
    await redis.set(_refresh_key(refresh_token), str(user_id), ex=ttl)
    return access_token, refresh_token


async def refresh_token_pair(
    redis: Redis,
    refresh_token: str,
    session: AsyncSession,
    settings: Settings,
) -> tuple[str, str, UserOut]:
    user_id_raw = await redis.get(_refresh_key(refresh_token))
    if user_id_raw is None:
        raise GoogleAuthError("Invalid refresh token")
    user_id = UUID(user_id_raw.decode() if isinstance(user_id_raw, bytes) else user_id_raw)

    user = await users_repo.get_by_id(session, user_id)
    if user is None:
        await redis.delete(_refresh_key(refresh_token))
        raise GoogleAuthError("User not found")

    # Rotate refresh token on each use.
    await redis.delete(_refresh_key(refresh_token))
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
    await redis.delete(_refresh_key(refresh_token))


async def is_access_revoked(redis: Redis, jti: str) -> bool:
    return bool(await redis.get(_revoked_key(jti)))


async def verify_access_token(redis: Redis, token: str, settings: Settings) -> UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise GoogleAuthError("Invalid access token") from exc
    jti = payload.get("jti")
    if jti and await is_access_revoked(redis, str(jti)):
        raise GoogleAuthError("Token revoked")
    return UUID(payload["sub"])

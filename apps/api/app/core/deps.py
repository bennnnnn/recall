import time
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.exceptions import RedisUnavailableError
from app.gateways.google_auth import GoogleAuthError
from app.models.orm import User
from app.services import auth as auth_service
from app.services import tokens as tokens_service

security = HTTPBearer()

# Neon from a laptop is a few hundred milliseconds per checkout. Chat auth
# runs on every send, so keep the last loaded user in this process and skip
# that round trip. Profile edits are rare; a short TTL is enough.
_USER_CACHE_TTL_SECONDS = 60.0
_user_cache: dict[UUID, tuple[float, User]] = {}


def _cached_user(user_id: UUID) -> User | None:
    hit = _user_cache.get(user_id)
    if hit is None:
        return None
    stored_at, user = hit
    if time.monotonic() - stored_at > _USER_CACHE_TTL_SECONDS:
        _user_cache.pop(user_id, None)
        return None
    return user


def remember_user(user: User) -> None:
    _user_cache[user.id] = (time.monotonic(), user)


def forget_user(user_id: UUID) -> None:
    _user_cache.pop(user_id, None)

_REDIS_RETRY_AFTER = "5"


def redis_unavailable_http_exception(exc: RedisUnavailableError) -> HTTPException:
    """Map Redis outage to 503 + Retry-After (shared by deps + auth routes)."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=exc.message,
        headers={"Retry-After": _REDIS_RETRY_AFTER},
    )


async def get_settings_dep() -> Settings:
    return get_settings()


async def get_redis_dep() -> Redis:
    return get_redis_client()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings_dep),
    redis: Redis = Depends(get_redis_dep),
) -> User:
    try:
        user_id = await tokens_service.verify_access_token(redis, credentials.credentials, settings)
    except RedisUnavailableError as exc:
        raise redis_unavailable_http_exception(exc) from exc
    except GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    cached = _cached_user(user_id)
    if cached is not None:
        return cached

    async with SessionLocal() as session:
        user = await auth_service.get_current_user(session, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        # Load columns before the session closes so later requests can reuse
        # this instance without a lazy load.
        session.expunge(user)
    remember_user(user)
    return user


def get_redis() -> Redis:
    return get_redis_client()

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access_tokens, user_cache
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.redis import get_redis_client
from app.exceptions import RedisUnavailableError
from app.gateways.google_auth import GoogleAuthError
from app.models.orm import User
from app.repositories import users as users_repo

security = HTTPBearer()

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
    session: AsyncSession = Depends(get_db),
) -> User:
    try:
        user_id = await access_tokens.verify_access_token(redis, credentials.credentials, settings)
    except RedisUnavailableError as exc:
        raise redis_unavailable_http_exception(exc) from exc
    except GoogleAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    # Per-process cache of the last loaded row (core/user_cache.py).
    cached = user_cache.cached_user(user_id)
    if isinstance(cached, User):
        # Attach the cached row to this request so updates commit.
        return await session.merge(cached, load=False)
    if cached is not None:
        return cached

    user = await users_repo.get_by_id(session, user_id)
    # End the read now. FastAPI closes the request's session only after the response is sent,
    # so an SSE reply or a slow upload kept this connection idle in transaction throughout.
    # Nothing else has used the session yet, and expire_on_commit=False keeps the row loaded.
    await session.commit()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    user_cache.remember_user(user)
    return user


def get_redis() -> Redis:
    return get_redis_client()

import asyncio
import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

# Covers one LLM round-trip + optional fallback retry with headroom.
_MEMORY_WRITE_LOCK_TTL = 150
_DELETE_LOCK_RETRY_ATTEMPTS = 4
_DELETE_LOCK_RETRY_DELAY_SECONDS = 0.15


def memory_write_lock_key(user_id: UUID) -> str:
    return f"memwrite:{user_id}"


async def acquire_memory_write_lock(seams: Any, user_id: UUID) -> str | None:
    """Acquire the per-user memory rewrite lock, failing closed on Redis errors."""
    from app.core.redis_lock import acquire_lock

    try:
        redis = seams.get_redis_client()
        return await acquire_lock(redis, memory_write_lock_key(user_id), _MEMORY_WRITE_LOCK_TTL)
    except Exception:
        logger.debug("Memory write lock acquire failed", exc_info=True)
        return None


async def release_memory_write_lock(seams: Any, user_id: UUID, token: str | None) -> None:
    """Release only when ``token`` still owns the lock."""
    if not token:
        return
    from app.core.redis_lock import release_lock

    try:
        redis = seams.get_redis_client()
        await release_lock(redis, memory_write_lock_key(user_id), token)
    except Exception:
        logger.debug("Memory write lock release failed", exc_info=True)


async def acquire_memory_write_lock_or_raise(seams: Any, user_id: UUID) -> str:
    for attempt in range(_DELETE_LOCK_RETRY_ATTEMPTS):
        token = await seams.acquire_memory_write_lock(user_id)
        if token:
            return token
        if attempt < _DELETE_LOCK_RETRY_ATTEMPTS - 1:
            await asyncio.sleep(_DELETE_LOCK_RETRY_DELAY_SECONDS)
    raise seams.MemoryWriteLockBusyError(user_id)

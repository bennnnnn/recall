"""The per-user memory write lock: one writer at a time over a user's facts."""

import asyncio
import logging
from uuid import UUID

from app.core.redis import get_redis_client
from app.core.redis_lock import acquire_lock, refresh_lock, release_lock
from app.exceptions import DomainError, RedisUnavailableError

logger = logging.getLogger(__name__)

# How long a holder that died keeps the lock. A holder at work keeps it as long as it
# works (``keep_memory_write_lock``): a pass of several model calls (consolidation merges
# pair after pair) outlasted a fixed 150 s and let a second writer in (audit, 2026-11-25).
_MEMORY_WRITE_LOCK_TTL = 150
_MEMORY_WRITE_LOCK_REFRESH_SECONDS = _MEMORY_WRITE_LOCK_TTL / 3
_DELETE_LOCK_RETRY_ATTEMPTS = 4
_DELETE_LOCK_RETRY_DELAY_SECONDS = 0.15


class MemoryWriteLockBusyError(DomainError):
    """Another write holds the user's memory; 409 ``memory_busy``."""

    status_code = 409
    default_code = "memory_busy"

    def __init__(self, user_id: UUID) -> None:
        super().__init__("Memory is being updated right now — try again in a moment.")
        self.user_id = user_id


def memory_write_lock_key(user_id: UUID) -> str:
    return f"memwrite:{user_id}"


async def take_memory_write_lock(user_id: UUID) -> str | None:
    """The per-user memory write lock's token, or None while another write holds it.

    A Redis error raises ``RedisUnavailableError`` (fail closed): Redis cannot say who
    holds the lock, so nothing writes, and an edit the user waits on answers 503.
    """
    try:
        return await acquire_lock(
            get_redis_client(), memory_write_lock_key(user_id), _MEMORY_WRITE_LOCK_TTL
        )
    except Exception as exc:
        raise RedisUnavailableError() from exc


async def acquire_memory_write_lock(user_id: UUID) -> str | None:
    """The lock for a background writer: None while held or while Redis is down.

    Either way the job retries after a backoff (``skipped_lock``), failing closed.
    """
    try:
        return await take_memory_write_lock(user_id)
    except RedisUnavailableError:
        # Not contention: the caller's "lock held" line follows, and this says why.
        logger.warning(
            "Memory write lock unavailable (Redis error) user_id=%s", user_id, exc_info=True
        )
        return None


def keep_memory_write_lock(user_id: UUID, token: str | None) -> asyncio.Task[None] | None:
    """Refresh the lock's TTL while its holder works, so model calls under it can take
    as long as they take; ``stop_keeping`` ends it, before the release."""
    if not token:
        return None
    return asyncio.create_task(_keep(user_id, token), name="memory-write-lock-keeper")


def stop_keeping(keeper: asyncio.Task[None] | None) -> None:
    if keeper is not None:
        keeper.cancel()


async def _keep(user_id: UUID, token: str) -> None:
    key = memory_write_lock_key(user_id)
    while True:
        await asyncio.sleep(_MEMORY_WRITE_LOCK_REFRESH_SECONDS)
        try:
            kept = await refresh_lock(get_redis_client(), key, token, _MEMORY_WRITE_LOCK_TTL)
        except Exception:
            # A blip: the next refresh tries again, well inside the TTL.
            logger.info("Memory write lock refresh failed user_id=%s", user_id, exc_info=True)
            continue
        if not kept:
            # Expired or taken over (Redis lost it): the writes' snapshot checks stand.
            logger.warning("Memory write lock lost while held user_id=%s", user_id)
            return


async def release_memory_write_lock(user_id: UUID, token: str | None) -> None:
    """Release only when ``token`` still owns the lock."""
    if not token:
        return
    try:
        await release_lock(get_redis_client(), memory_write_lock_key(user_id), token)
    except Exception:
        logger.debug("Memory write lock release failed", exc_info=True)


async def acquire_memory_write_lock_or_raise(user_id: UUID) -> str:
    """The lock for a hand edit, retried briefly; ``MemoryWriteLockBusyError`` if held.

    Redis down raises ``RedisUnavailableError`` at once (503 unavailable). It read as held,
    so an outage said "Memory is being updated" (409 ``memory_busy``) after four tries.
    """
    for attempt in range(_DELETE_LOCK_RETRY_ATTEMPTS):
        token = await take_memory_write_lock(user_id)
        if token:
            return token
        if attempt < _DELETE_LOCK_RETRY_ATTEMPTS - 1:
            await asyncio.sleep(_DELETE_LOCK_RETRY_DELAY_SECONDS)
    raise MemoryWriteLockBusyError(user_id)

"""Shared periodic scheduler loop, Redis lock, and cancellation handling.

Each scheduler keeps its own interval and cycle body so a slow cycle cannot
delay the others. Lock TTL helpers mark the two intended conventions:
hold-across-ticks (bounded work) vs yield-next-tick (unbounded work + refresh).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.core.redis_lock import acquire_lock, refresh_lock, release_lock

logger = logging.getLogger(__name__)

_tasks: dict[str, asyncio.Task[None]] = {}


@dataclass(frozen=True, slots=True)
class CycleLock:
    """Lock held for one cycle; refresh during unbounded work."""

    redis: Redis
    key: str
    token: str
    ttl_seconds: int

    async def refresh(self) -> bool:
        return await refresh_lock(self.redis, self.key, self.token, self.ttl_seconds)


CycleFn = Callable[[Settings, CycleLock], Awaitable[None]]


def lock_ttl_hold_across_ticks(interval_seconds: int) -> int:
    """Bounded cycles: hold longer than one interval so a slow run cannot overlap."""
    return max(interval_seconds * 10, 300)


def lock_ttl_yield_next_tick(interval_seconds: int) -> int:
    """Unbounded cycles: expire before the next tick. Refresh during work.

    Do not raise this past ``interval_seconds`` — a crashed holder would then
    block the following cycle entirely.
    """
    return max(interval_seconds - 30, 60)


async def run_locked_cycle(
    *,
    name: str,
    lock_key: str,
    lock_ttl_seconds: int,
    enabled: bool,
    fn: CycleFn,
    settings: Settings,
) -> None:
    if not enabled:
        return
    redis = get_redis_client()
    token = await acquire_lock(redis, lock_key, lock_ttl_seconds)
    if not token:
        return
    lock = CycleLock(redis=redis, key=lock_key, token=token, ttl_seconds=lock_ttl_seconds)
    try:
        await fn(settings, lock)
    except Exception:
        logger.exception("%s cycle failed", name)
    finally:
        await release_lock(redis, lock_key, token)


async def start_periodic(
    *,
    name: str,
    interval_seconds: int,
    enabled: bool,
    cycle: Callable[[Settings], Awaitable[None]],
    settings: Settings,
) -> None:
    if not enabled or name in _tasks:
        return

    async def _loop() -> None:
        while True:
            try:
                await cycle(settings)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("%s loop error", name)
            await asyncio.sleep(max(interval_seconds, 1))

    _tasks[name] = asyncio.create_task(_loop(), name=f"periodic:{name}")


async def stop_periodic(name: str) -> None:
    task = _tasks.pop(name, None)
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

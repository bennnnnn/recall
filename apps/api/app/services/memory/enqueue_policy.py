"""Policy for scheduling memory consolidation work."""

import logging
from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs
from app.models.orm import Memory, User
from app.repositories import memories as memories_repo
from app.services import memory as memory_service

logger = logging.getLogger(__name__)

_CONSOLIDATE_LOCK_TTL = 300


class MemorySection(Protocol):
    type: str
    text: str


def _lock_key(user_id: UUID) -> str:
    return f"memconsolidate:{user_id}"


async def request_consolidation(
    redis: Redis,
    user: User,
    memories: Iterable[MemorySection],
    *,
    skip_if_already_queued: bool,
) -> str:
    memory_list = list(memories)
    if not user.memory_enabled or not memory_list:
        return "skipped"

    lock_key = _lock_key(user.id)
    if skip_if_already_queued and await redis.exists(lock_key):
        return "in_progress"

    sections = {memory.type: memory.text for memory in memory_list}
    if not memory_service.sections_need_consolidation(sections):
        return "skipped"

    acquired = await redis.set(
        lock_key,
        "1",
        ex=_CONSOLIDATE_LOCK_TTL,
        nx=True,
    )
    if not acquired:
        return "in_progress"
    await jobs.enqueue(redis, "memory_consolidate", {"user_id": str(user.id)})
    return "queued"


async def request_user_consolidation(
    session: AsyncSession,
    redis: Redis,
    user: User,
) -> str:
    if not user.memory_enabled:
        return "skipped"
    memories = await memories_repo.list_for_user(session, user.id)
    return await request_consolidation(
        redis,
        user,
        memories,
        skip_if_already_queued=False,
    )


async def list_user_memories(
    session: AsyncSession,
    redis: Redis,
    user: User,
) -> list[Memory]:
    memories = await memories_repo.list_for_user(session, user.id)
    await maybe_request_consolidation(redis, user, memories)
    return memories


async def maybe_request_consolidation(
    redis: Redis,
    user: User,
    memories: Iterable[MemorySection],
) -> None:
    try:
        await request_consolidation(
            redis,
            user,
            memories,
            skip_if_already_queued=True,
        )
    except Exception:
        logger.debug("Failed to enqueue memory consolidation", exc_info=True)

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.models.orm import Memory, User

logger = logging.getLogger(__name__)

TYPE_PRIORITY = {"profile": 0, "preference": 1, "project": 2, "fact": 3, "focus": 4}


def _memory_block_key(user_id: UUID) -> str:
    return f"memblock:{user_id}"


def _confidence_value(memory: Memory) -> float:
    if memory.confidence is None:
        return 1.0
    return float(memory.confidence)


def select_memories_for_prompt(memories: list[Memory], settings: Settings) -> list[Memory]:
    filtered: list[Memory] = []
    seen_text: set[str] = set()

    for memory in memories:
        if _confidence_value(memory) < settings.memory_min_confidence:
            continue
        key = memory.text.strip().lower()
        if key in seen_text:
            continue
        seen_text.add(key)
        filtered.append(memory)

    filtered.sort(
        key=lambda m: (TYPE_PRIORITY.get(m.type, 99), -_confidence_value(m), m.updated_at),
    )
    return filtered[: settings.memory_inject_limit]


def format_memory_block(memories: list) -> str:
    if not memories:
        return ""
    lines = ["Known facts about the user:"]
    for memory in memories:
        lines.append(f"- [{memory.type}] {memory.text}")
    return "\n".join(lines)


async def load_relevant_memories(
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> list:
    if not user.memory_enabled:
        return []
    from app.repositories import memories as memories_repo

    all_memories = await memories_repo.list_for_user(session, user.id)
    return select_memories_for_prompt(all_memories, settings)


async def get_memory_block(session: AsyncSession, user: User, settings: Settings) -> str:
    """Formatted memory block for the prompt, cached in Redis per user.

    Avoids re-querying + re-formatting every memory on every turn. Best-effort:
    any Redis hiccup falls back to a direct DB load.
    """
    if not user.memory_enabled:
        return ""

    key = _memory_block_key(user.id)
    redis = get_redis_client()
    try:
        cached = await redis.get(key)
        if cached is not None:
            return cached
    except Exception:
        logger.debug("Memory block cache read failed", exc_info=True)

    memories = await load_relevant_memories(session, user, settings)
    block = format_memory_block(memories)
    try:
        await redis.set(key, block, ex=settings.memory_cache_ttl)
    except Exception:
        logger.debug("Memory block cache write failed", exc_info=True)
    return block


async def invalidate_memory_block(user_id: UUID) -> None:
    try:
        await get_redis_client().delete(_memory_block_key(user_id))
    except Exception:
        logger.debug("Memory block cache invalidation failed", exc_info=True)


async def delete_memory(session: AsyncSession, user_id: UUID, memory_id: UUID) -> bool:
    from app.repositories import memories as memories_repo

    deleted = await memories_repo.delete_by_id(session, user_id, memory_id)
    if deleted:
        await invalidate_memory_block(user_id)
    return deleted

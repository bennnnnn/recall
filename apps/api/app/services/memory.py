import logging
import re
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.models.orm import Memory, User

logger = logging.getLogger(__name__)

TYPE_PRIORITY = {"profile": 0, "preference": 1, "project": 2, "fact": 3, "focus": 4}
SECTION_LABELS = {
    "profile": "Profile",
    "preference": "Preferences",
    "project": "Projects",
    "fact": "Facts",
    "focus": "Focus",
}


def normalize_memory_text(text: str) -> str:
    clean = re.sub(r"\s+", " ", text.strip()).rstrip(".")
    return clean


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def section_needs_consolidation(text: str) -> bool:
    """True only for migration-style glue (duplicates), not normal long summaries."""
    clean = text.strip()
    if not clean:
        return False
    sentences = _split_sentences(clean)
    normalized = [normalize_memory_text(sentence).lower() for sentence in sentences]
    if len(normalized) != len(set(normalized)):
        return True
    prefixes = [" ".join(sentence.split()[:3]) for sentence in normalized if sentence]
    if len(prefixes) >= 2 and len(prefixes) != len(set(prefixes)):
        return True
    return len(clean) > 900 and len(sentences) >= 6


def sections_need_consolidation(sections: dict[str, str]) -> bool:
    return any(section_needs_consolidation(text) for text in sections.values())


def _confidence_value(memory: Memory) -> float:
    if memory.confidence is None:
        return 1.0
    return float(memory.confidence)


def select_memories_for_prompt(memories: list[Memory], settings: Settings) -> list[Memory]:
    filtered = [
        memory
        for memory in memories
        if _confidence_value(memory) >= settings.memory_min_confidence and memory.text.strip()
    ]
    filtered.sort(key=lambda m: (TYPE_PRIORITY.get(m.type, 99), -_confidence_value(m)))
    return filtered[: settings.memory_inject_limit]


def format_memory_block(memories: list) -> str:
    if not memories:
        return ""
    ordered = sorted(memories, key=lambda m: TYPE_PRIORITY.get(m.type, 99))
    lines = ["Known facts about the user:"]
    for memory in ordered:
        label = SECTION_LABELS.get(memory.type, memory.type.title())
        lines.append(f"\n## {label}\n{memory.text.strip()}")
    return "\n".join(lines)


def select_memories_semantic(
    memories: list[Memory],
    query_embedding: list[float],
    settings: Settings,
) -> list[Memory]:
    from app.gateways.embedding_gateway import cosine_similarity, parse_embedding

    scored: list[tuple[float, Memory]] = []
    for memory in memories:
        if _confidence_value(memory) < settings.memory_min_confidence or not memory.text.strip():
            continue
        vec = parse_embedding(getattr(memory, "embedding_json", None))
        if vec is None:
            continue
        scored.append((cosine_similarity(query_embedding, vec), memory))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [memory for _, memory in scored[: settings.memory_inject_limit]]


async def load_relevant_memories(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    query_text: str | None = None,
) -> list:
    if not user.memory_enabled:
        return []
    from app.repositories import memories as memories_repo

    all_memories = await memories_repo.list_for_user(session, user.id)
    if settings.semantic_memory_enabled and query_text and query_text.strip():
        from app.gateways import embedding_gateway

        query_vec = await embedding_gateway.embed_text(settings, query_text.strip())
        if query_vec:
            semantic = select_memories_semantic(all_memories, query_vec, settings)
            if semantic:
                return semantic
    return select_memories_for_prompt(all_memories, settings)


async def get_memory_block(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    query_text: str | None = None,
) -> str:
    """Formatted memory block for the prompt, cached in Redis per user."""
    if not user.memory_enabled:
        return ""

    key = _memory_block_key(user.id)
    if query_text and settings.semantic_memory_enabled:
        memories = await load_relevant_memories(session, user, settings, query_text=query_text)
        return format_memory_block(memories)

    redis = get_redis_client()
    try:
        cached = await redis.get(key)
        if cached is not None:
            return cast(str, cached)
    except Exception:
        logger.debug("Memory block cache read failed", exc_info=True)

    memories = await load_relevant_memories(session, user, settings)
    block = format_memory_block(memories)
    try:
        await redis.set(key, block, ex=settings.memory_cache_ttl)
    except Exception:
        logger.debug("Memory block cache write failed", exc_info=True)
    return block


def _memory_block_key(user_id: UUID) -> str:
    return f"memblock:{user_id}"


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


async def delete_memory_section(session: AsyncSession, user_id: UUID, memory_type: str) -> bool:
    from app.repositories import memories as memories_repo

    removed = await memories_repo.delete_by_type(session, user_id, memory_type)
    if removed:
        await invalidate_memory_block(user_id)
    return removed > 0

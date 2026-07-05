import asyncio
import hashlib
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


_CONSOLIDATION_ANCHOR_STOP = frozenset(
    {
        "user",
        "the",
        "and",
        "for",
        "with",
        "who",
        "that",
        "this",
        "their",
        "they",
        "prefers",
        "likes",
        "works",
        "name",
        "is",
        "are",
        "was",
        "has",
        "have",
    }
)


def extract_consolidation_anchors(text: str) -> frozenset[str]:
    """Salient tokens from prior memory text that a rewrite should preserve."""
    anchors: set[str] = set()
    for match in re.finditer(r"[\w.+-]+@[\w-]+\.[\w.-]+", text):
        anchors.add(match.group(0).lower())
    for match in re.finditer(r"\b\d{2,}\b", text):
        anchors.add(match.group(0))
    for match in re.finditer(r'"([^"]{2,80})"', text):
        quoted = match.group(1).strip().lower()
        if quoted:
            anchors.add(quoted)
    for match in re.finditer(r"\b[A-Z][a-zA-Z0-9-]{2,}\b", text):
        token = match.group(0).lower()
        if token not in _CONSOLIDATION_ANCHOR_STOP:
            anchors.add(token)
    return frozenset(anchors)


def consolidation_rewrite_preserves_facts(
    prior: str,
    summary: str,
    *,
    min_preserved_ratio: float = 0.8,
) -> bool:
    """True when enough prior anchors appear in the rewritten summary."""
    anchors = extract_consolidation_anchors(prior)
    if len(anchors) < 2:
        return True
    haystack = summary.lower()
    preserved = sum(1 for anchor in anchors if anchor in haystack)
    return preserved / len(anchors) >= min_preserved_ratio


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
    type_cap = min(settings.memory_inject_limit, len(TYPE_PRIORITY))
    return filtered[:type_cap]


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
    min_sim = settings.memory_min_similarity
    if min_sim > 0:
        scored = [(score, memory) for score, memory in scored if score >= min_sim]
    type_cap = min(settings.memory_inject_limit, len(TYPE_PRIORITY))
    return [memory for _, memory in scored[:type_cap]]


def _memory_query_cache_key(user_id: UUID, query_text: str) -> str:
    digest = hashlib.sha256(query_text.strip().lower().encode()).hexdigest()[:32]
    return f"memquery:{user_id}:{digest}"


def _memory_query_embed_key(user_id: UUID, query_text: str) -> str:
    digest = hashlib.sha256(query_text.strip().lower().encode()).hexdigest()[:32]
    return f"memembed:{user_id}:{digest}"


async def _get_cached_query_embedding(
    user_id: UUID,
    query_text: str,
) -> list[float] | None:
    from app.gateways.embedding_gateway import parse_embedding

    redis = get_redis_client()
    key = _memory_query_embed_key(user_id, query_text)
    try:
        cached = await redis.get(key)
        if cached is None:
            return None
        raw = cached.decode() if isinstance(cached, bytes) else cached
        return parse_embedding(raw)
    except Exception:
        logger.debug("Memory query embed cache read failed", exc_info=True)
        return None


async def _semantic_memories_from_vec(
    session: AsyncSession,
    user: User,
    settings: Settings,
    query_vec: list[float],
) -> list[Memory]:
    from app.repositories import memories as memories_repo

    db_hits = await memories_repo.search_semantic(
        session,
        user.id,
        query_vec,
        min_confidence=settings.memory_min_confidence,
        limit=settings.memory_inject_limit,
    )
    if db_hits:
        return db_hits
    all_memories = await memories_repo.list_for_user(session, user.id)
    semantic = select_memories_semantic(all_memories, query_vec, settings)
    if semantic:
        return semantic
    return select_memories_for_prompt(all_memories, settings)


async def load_relevant_memories(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    query_text: str | None = None,
    query_vec: list[float] | None = None,
) -> list:
    if not user.memory_enabled:
        return []
    from app.repositories import memories as memories_repo

    if query_vec is not None:
        return await _semantic_memories_from_vec(session, user, settings, query_vec)

    all_memories = await memories_repo.list_for_user(session, user.id)
    return select_memories_for_prompt(all_memories, settings)


async def _warm_semantic_memory_cache(
    settings: Settings,
    user_id: UUID,
    query_text: str,
) -> None:
    """Best-effort: embed query + cache semantic block for the next turn."""
    from app.core.db import SessionLocal
    from app.gateways import embedding_gateway
    from app.repositories import users as users_repo

    cleaned = query_text.strip()
    if not cleaned:
        return
    try:
        query_vec = await embedding_gateway.embed_text(settings, cleaned)
        if not query_vec:
            return
        redis = get_redis_client()
        gen_before = await redis.get(_memory_generation_key(user_id))
        embed_key = _memory_query_embed_key(user_id, cleaned)
        ttl = max(60, settings.memory_query_embed_cache_ttl)
        try:
            await redis.set(
                embed_key,
                embedding_gateway.serialize_embedding(query_vec),
                ex=ttl,
            )
        except Exception:
            logger.debug("Memory query embed cache write failed", exc_info=True)

        async with SessionLocal() as session:
            user = await users_repo.get_by_id(session, user_id)
            if user is None or not user.memory_enabled:
                return
            memories = await _semantic_memories_from_vec(session, user, settings, query_vec)
            block = format_memory_block(memories)
            gen_after = await redis.get(_memory_generation_key(user_id))
            if gen_before != gen_after:
                return
            query_key = _memory_query_cache_key(user_id, cleaned)
            try:
                await redis.set(
                    query_key,
                    block,
                    ex=max(30, settings.memory_query_cache_ttl),
                )
            except Exception:
                logger.debug("Memory query cache write failed", exc_info=True)
    except Exception:
        logger.debug("Background semantic memory warm failed", exc_info=True)


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
        q = query_text.strip()
        query_key = _memory_query_cache_key(user.id, q)
        redis = get_redis_client()
        try:
            cached = await redis.get(query_key)
            if cached is not None:
                return cast(str, cached)
        except Exception:
            logger.debug("Memory query cache read failed", exc_info=True)

        query_vec = await _get_cached_query_embedding(user.id, q)
        if query_vec is not None:
            memories = await load_relevant_memories(
                session,
                user,
                settings,
                query_vec=query_vec,
            )
            block = format_memory_block(memories)
            try:
                await redis.set(query_key, block, ex=max(30, settings.memory_query_cache_ttl))
            except Exception:
                logger.debug("Memory query cache write failed", exc_info=True)
            return block

        # Cache miss — type-priority memories now; warm semantic cache in background.
        memories = await load_relevant_memories(session, user, settings)
        block = format_memory_block(memories)
        try:
            await redis.set(query_key, block, ex=max(30, settings.memory_query_cache_ttl))
        except Exception:
            logger.debug("Memory query cache write failed", exc_info=True)
        warm_task = asyncio.create_task(_warm_semantic_memory_cache(settings, user.id, q))
        warm_task.add_done_callback(
            lambda t: logger.debug("Semantic memory warm failed", exc_info=t.exception())
            if t.exception()
            else None
        )
        return block

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


def _memory_query_key_prefix(user_id: UUID) -> str:
    return f"memquery:{user_id}:"


def _memory_generation_key(user_id: UUID) -> str:
    return f"memgen:{user_id}"


async def invalidate_memory_block(user_id: UUID) -> None:
    """Drop the per-user memory block cache AND any per-query semantic cache
    entries — both can hold stale content after a memory write or delete."""
    try:
        redis = get_redis_client()
        await redis.incr(_memory_generation_key(user_id))
        await redis.delete(_memory_block_key(user_id))
        # Clear memquery:{user_id}:* entries (semantic recall is query-conditioned
        # and can be stale after an extraction/rewrite/delete).
        prefix = _memory_query_key_prefix(user_id)
        batch: list[str] = []
        async for key in redis.scan_iter(match=f"{prefix}*", count=200):
            batch.append(key if isinstance(key, str) else key.decode())
            if len(batch) >= 200:
                await redis.delete(*batch)
                batch.clear()
        if batch:
            await redis.delete(*batch)
        embed_prefix = f"memembed:{user_id}:"
        batch = []
        async for key in redis.scan_iter(match=f"{embed_prefix}*", count=200):
            batch.append(key if isinstance(key, str) else key.decode())
            if len(batch) >= 200:
                await redis.delete(*batch)
                batch.clear()
        if batch:
            await redis.delete(*batch)
    except Exception:
        logger.debug("Memory block cache invalidation failed", exc_info=True)


def split_memory_facts(text: str) -> list[str]:
    return _split_sentences(text)


def join_memory_facts(facts: list[str]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for raw in facts:
        clean = normalize_memory_text(raw)
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        parts.append(clean)
    merged = ". ".join(parts)
    if merged and not merged.endswith("."):
        merged += "."
    return merged


async def delete_memory_fact(
    session: AsyncSession,
    user_id: UUID,
    memory_id: UUID,
    fact_index: int,
) -> bool:
    from app.repositories import memories as memories_repo

    memory = await memories_repo.get_by_id(session, user_id, memory_id)
    if memory is None:
        return False
    facts = split_memory_facts(memory.text)
    if fact_index < 0 or fact_index >= len(facts):
        return False
    facts.pop(fact_index)
    if not facts:
        deleted = await memories_repo.delete_by_id(session, user_id, memory_id)
        if deleted:
            await invalidate_memory_block(user_id)
        return deleted
    updated = await memories_repo.update_text(session, user_id, memory_id, join_memory_facts(facts))
    if updated is not None:
        await invalidate_memory_block(user_id)
        return True
    return False


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

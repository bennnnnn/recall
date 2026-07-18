import asyncio
import hashlib
import logging
import re
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.background_tasks import create_background_task
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


def embedding_text_hash(text: str) -> str:
    """Hash of the exact text an embedding was computed from — stored
    alongside the vector so a later pass can tell "stale" from "current"
    without needing the specific prior-snapshot text that triggered this
    particular embed call. See migration 0057 and its BUG FIX docstring."""
    return hashlib.sha256(text.encode()).hexdigest()


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
    """True when enough prior anchors appear in the rewritten summary.

    BUG FIX (off-by-one): the safety gate is meant to reject a merge that
    drops >= 20% of anchors (the default `min_preserved_ratio=0.8`). A `>=`
    comparison here accepted a merge that preserved exactly 80% — i.e.
    dropped exactly 20% — when the spec says that boundary should be
    rejected too. Strict `>` closes it.
    """
    anchors = extract_consolidation_anchors(prior)
    if len(anchors) < 2:
        return True
    haystack = summary.lower()
    preserved = sum(1 for anchor in anchors if anchor in haystack)
    return preserved / len(anchors) > min_preserved_ratio


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


def _memory_query_cache_key(user_id: UUID, generation: bytes | str | None, query_text: str) -> str:
    # BUG FIX (was a race): the generation is folded into the key itself,
    # not just checked-then-compared before a separate write. A write
    # started under an old generation lands under that generation's own key
    # namespace, which no reader will ever look up again once the
    # generation bumps — so a slow write racing a concurrent
    # invalidate_memory_block() can no longer resurrect stale content
    # under the current generation, regardless of write/invalidate timing.
    digest = hashlib.sha256(query_text.strip().lower().encode()).hexdigest()[:32]
    if generation is None:
        gen_tag = "0"
    elif isinstance(generation, bytes):
        gen_tag = generation.decode()
    else:
        gen_tag = generation
    return f"memquery:{user_id}:{gen_tag}:{digest}"


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

    # cosine_distance = 1 - cosine_similarity, so a min_similarity cutoff maps
    # to a max_distance cutoff. Apply it DB-side so the DB path behaves like
    # the in-memory path (which filters by memory_min_similarity).
    max_distance: float | None = None
    if settings.memory_min_similarity > 0:
        max_distance = 1.0 - settings.memory_min_similarity

    db_hits = await memories_repo.search_semantic(
        session,
        user.id,
        query_vec,
        min_confidence=settings.memory_min_confidence,
        limit=settings.memory_inject_limit,
        max_distance=max_distance,
    )
    if db_hits:
        return db_hits
    all_memories = await memories_repo.list_for_user(session, user.id)
    # BUG FIX: an empty db_hits list is ambiguous — search_semantic's own
    # docstring says it means "no row has a populated vector yet," but it
    # equally happens when vectors ARE populated and none clear the
    # memory_min_similarity cutoff (a genuine "nothing relevant" result).
    # Falling back to type-priority selection in that second case injects an
    # arbitrary "known facts" block for a query that's actually unrelated,
    # defeating the point of the semantic gate. Only fall back when no
    # memory has an embedding at all — the real "vectors not ready yet" case
    # this fallback exists for.
    if any(memory.embedding is not None for memory in all_memories):
        return []
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

    # BUG FIX: this used to let a DB exception (transient Neon/pgvector
    # failure) propagate straight out of build_prompt_messages's
    # asyncio.gather(...), failing the ENTIRE chat turn over a memory lookup
    # — every Redis call in this file already degrades to a safe default on
    # failure; retrieval on the chat hot path must do the same rather than
    # block streaming (the same "never block the chat request path" spirit
    # as Golden Rule 4's best-effort extraction jobs).
    try:
        if query_vec is not None:
            return await _semantic_memories_from_vec(session, user, settings, query_vec)

        all_memories = await memories_repo.list_for_user(session, user.id)
        return select_memories_for_prompt(all_memories, settings)
    except Exception:
        logger.warning("Memory retrieval failed for user_id=%s", user.id, exc_info=True)
        return []


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
            # Optimization only, not a correctness guard (see
            # _memory_query_cache_key): skip the write outright if we
            # already know the generation moved on, since it would land
            # under a now-unreachable key anyway.
            gen_after = await redis.get(_memory_generation_key(user_id))
            if gen_before != gen_after:
                return
            query_key = _memory_query_cache_key(user_id, gen_before, cleaned)
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
        redis = get_redis_client()
        try:
            generation = await redis.get(_memory_generation_key(user.id))
        except Exception:
            logger.debug("Memory generation read failed", exc_info=True)
            generation = None
        query_key = _memory_query_cache_key(user.id, generation, q)
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
        # BUG FIX: asyncio.create_task alone only keeps a task alive via the
        # caller's local reference, which goes out of scope right after this
        # function returns — per asyncio's own docs, an unreferenced task is
        # eligible for GC before it completes. create_background_task holds
        # a strong reference in a module-level set until the task finishes
        # (same pattern already used correctly in chat/stream.py).
        warm_task = create_background_task(
            _warm_semantic_memory_cache(settings, user.id, q),
            name="warm_semantic_memory_cache",
        )
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


# Generous vs. a typical extraction/consolidation LLM round trip + DB write —
# this is a crash safety net (in case a worker dies mid-critical-section), not
# the normal release path (see release_memory_write_lock).
_MEMORY_WRITE_LOCK_TTL = 60


def _memory_write_lock_key(user_id: UUID) -> str:
    return f"memwrite:{user_id}"


async def acquire_memory_write_lock(user_id: UUID) -> bool:
    """Serializes extraction/consolidation's read-modify-write section for one
    user — without this, two overlapping jobs (extraction from one chat racing
    consolidation, or two extractions from two chats) can both read the same
    prior section text and the later commit silently discards the earlier
    one's write. Best-effort like the jobs that call it: on a Redis error,
    fail closed (treat as not acquired) rather than proceed unprotected."""
    try:
        redis = get_redis_client()
        acquired = await redis.set(
            _memory_write_lock_key(user_id), "1", ex=_MEMORY_WRITE_LOCK_TTL, nx=True
        )
        return bool(acquired)
    except Exception:
        logger.debug("Memory write lock acquire failed", exc_info=True)
        return False


async def release_memory_write_lock(user_id: UUID) -> None:
    try:
        redis = get_redis_client()
        await redis.delete(_memory_write_lock_key(user_id))
    except Exception:
        logger.debug("Memory write lock release failed", exc_info=True)


class MemoryWriteLockBusyError(Exception):
    """A user-initiated memory delete couldn't get the write lock after
    retrying — extraction/consolidation is actively mid-rewrite for this
    user right now. Callers should surface this as "try again shortly"
    rather than a plain failure."""

    def __init__(self, user_id: UUID) -> None:
        super().__init__(f"Memory write lock busy for user_id={user_id}")
        self.user_id = user_id


# Background jobs just skip a run when the lock is held (best-effort, next
# scheduled pass will catch up). A user tapping delete shouldn't silently
# no-op for the same reason — without this, a delete racing a same-second
# extraction/consolidation read-modify-write could have its result silently
# overwritten by the other side's stale-snapshot commit. Retry briefly first
# (typical hold time is one LLM round trip + a DB write, well under a
# second), then surface MemoryWriteLockBusyError so the caller can ask the
# user to retry instead of guessing.
_DELETE_LOCK_RETRY_ATTEMPTS = 4
_DELETE_LOCK_RETRY_DELAY_SECONDS = 0.15


async def _acquire_memory_write_lock_or_raise(user_id: UUID) -> None:
    for attempt in range(_DELETE_LOCK_RETRY_ATTEMPTS):
        if await acquire_memory_write_lock(user_id):
            return
        if attempt < _DELETE_LOCK_RETRY_ATTEMPTS - 1:
            await asyncio.sleep(_DELETE_LOCK_RETRY_DELAY_SECONDS)
    raise MemoryWriteLockBusyError(user_id)


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
    settings: Settings,
    user_id: UUID,
    memory_id: UUID,
    fact_index: int,
    *,
    expected_text: str | None = None,
) -> bool:
    from app.gateways import embedding_gateway
    from app.repositories import memories as memories_repo

    # Same lock extraction/consolidation use for their read-modify-write
    # section — without it, one of those jobs reading this row's prior text
    # concurrently with this delete can commit a merge computed from the
    # stale pre-delete text afterward, silently resurrecting what the user
    # just removed.
    await _acquire_memory_write_lock_or_raise(user_id)
    try:
        memory = await memories_repo.get_by_id(session, user_id, memory_id)
        if memory is None:
            return False
        facts = split_memory_facts(memory.text)
        # BUG FIX (was silent): the client computes fact_index from its own local
        # copy of memory.text, but a background extraction/consolidation job can
        # rewrite this section between when the client loaded it and when the
        # user taps delete — the index can then point at a different fact than
        # the one the user saw, silently deleting the wrong one with no error.
        # When the caller supplies the fact text it actually showed the user,
        # prefer locating that exact fact by content; only fall back to the raw
        # index when no expected_text was given (older clients) or the client's
        # index still happens to be one of the (possibly duplicate) matches. If
        # the expected fact isn't present at all anymore, refuse rather than
        # guess — the client should refresh and let the user retry.
        target_index = fact_index
        if expected_text is not None:
            normalized_expected = normalize_memory_text(expected_text).lower()
            matches = [
                i
                for i, fact in enumerate(facts)
                if normalize_memory_text(fact).lower() == normalized_expected
            ]
            if not matches:
                return False
            target_index = fact_index if fact_index in matches else matches[0]
        if target_index < 0 or target_index >= len(facts):
            return False
        facts.pop(target_index)
        if not facts:
            deleted = await memories_repo.delete_by_id(session, user_id, memory_id)
            if deleted:
                await invalidate_memory_block(user_id)
            return deleted
        new_text = join_memory_facts(facts)
        # Re-embed so semantic recall doesn't rank on the stale pre-delete vector.
        # In dev/mock mode (no embedding key) embed_text returns None and we fall
        # back to a text-only update so the feature still works.
        try:
            new_vec = await embedding_gateway.embed_text(settings, new_text)
        except Exception:
            logger.debug("Memory re-embed on fact delete failed", exc_info=True)
            new_vec = None
        if new_vec is not None:
            updated = await memories_repo.update_text_and_embedding(
                session,
                user_id,
                memory_id,
                new_text,
                new_vec,
                embedding_gateway.serialize_embedding(new_vec),
            )
        else:
            updated = await memories_repo.update_text(session, user_id, memory_id, new_text)
        if updated is not None:
            await invalidate_memory_block(user_id)
            return True
        return False
    finally:
        await release_memory_write_lock(user_id)


async def delete_memory(session: AsyncSession, user_id: UUID, memory_id: UUID) -> bool:
    from app.repositories import memories as memories_repo

    await _acquire_memory_write_lock_or_raise(user_id)
    try:
        deleted = await memories_repo.delete_by_id(session, user_id, memory_id)
        if deleted:
            await invalidate_memory_block(user_id)
        return deleted
    finally:
        await release_memory_write_lock(user_id)


async def delete_memory_section(session: AsyncSession, user_id: UUID, memory_type: str) -> bool:
    from app.repositories import memories as memories_repo

    await _acquire_memory_write_lock_or_raise(user_id)
    try:
        removed = await memories_repo.delete_by_type(session, user_id, memory_type)
        if removed:
            await invalidate_memory_block(user_id)
        return removed > 0
    finally:
        await release_memory_write_lock(user_id)

import logging
from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Memory, User

logger = logging.getLogger(__name__)


async def semantic_memories_from_vec(
    seams: Any,
    session: AsyncSession,
    user: User,
    settings: Settings,
    query_vec: list[float],
    *,
    omit_project_memory: bool = False,
) -> list[Memory]:
    from app.repositories import memories as memories_repo

    all_memories = await memories_repo.list_for_user(session, user.id)
    semantic = seams.select_memories_semantic(
        all_memories,
        query_vec,
        settings,
        omit_project_memory=omit_project_memory,
    )
    if semantic:
        return semantic
    return seams.select_memories_for_prompt(
        all_memories, settings, omit_project_memory=omit_project_memory
    )


async def load_relevant_memories(
    seams: Any,
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    query_text: str | None = None,
    query_vec: list[float] | None = None,
    omit_project_memory: bool = False,
) -> list[Memory]:
    del query_text
    if not user.memory_enabled:
        return []
    from app.repositories import memories as memories_repo

    try:
        if query_vec is not None:
            return await seams._semantic_memories_from_vec(
                session,
                user,
                settings,
                query_vec,
                omit_project_memory=omit_project_memory,
            )
        all_memories = await memories_repo.list_for_user(session, user.id)
        return seams.select_memories_for_prompt(
            all_memories, settings, omit_project_memory=omit_project_memory
        )
    except Exception:
        logger.warning("Memory retrieval failed for user_id=%s", user.id, exc_info=True)
        return []


def filter_surface_memories(
    seams: Any,
    memories: list[Memory],
    *,
    exclude_sensitive: bool,
) -> list[Memory]:
    if not exclude_sensitive:
        return memories
    return [memory for memory in memories if not seams.is_sensitive_memory_text(memory.text)]


async def semantic_block_from_vec(
    seams: Any,
    session: AsyncSession,
    user: User,
    settings: Settings,
    query_vec: list[float],
    *,
    omit_project_memory: bool,
    exclude_sensitive: bool,
) -> str:
    memories = await seams.load_relevant_memories(
        session,
        user,
        settings,
        query_vec=query_vec,
        omit_project_memory=omit_project_memory,
    )
    memories = filter_surface_memories(seams, memories, exclude_sensitive=exclude_sensitive)
    return seams.format_memory_block(memories, max_chars=settings.memory_inject_max_chars)


async def warm_semantic_memory_cache(
    seams: Any,
    settings: Settings,
    user_id: UUID,
    query_text: str,
    *,
    omit_project_memory: bool = False,
) -> None:
    from app.core.db import SessionLocal
    from app.gateways import embedding_gateway
    from app.repositories import users as users_repo

    cleaned = query_text.strip()
    if not cleaned:
        return
    try:
        query_vec = await embedding_gateway.get_or_embed_query(settings, user_id, cleaned)
        if not query_vec:
            return
        redis = seams.get_redis_client()
        gen_before = await redis.get(seams._memory_generation_key(user_id))
        async with SessionLocal() as session:
            user = await users_repo.get_by_id(session, user_id)
            if user is None or not user.memory_enabled:
                return
            block = await seams._semantic_block_from_vec(
                session,
                user,
                settings,
                query_vec,
                omit_project_memory=omit_project_memory,
                exclude_sensitive=False,
            )
            gen_after = await redis.get(seams._memory_generation_key(user_id))
            if gen_before != gen_after:
                return
            query_key = seams._memory_query_scoped_key(
                user_id,
                gen_before,
                cleaned,
                omit_project_memory=omit_project_memory,
                exclude_sensitive=False,
            )
            await seams._write_query_block_cache(query_key, block, settings)
    except Exception:
        logger.debug("Background semantic memory warm failed", exc_info=True)


async def get_memory_block(
    seams: Any,
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    query_text: str | None = None,
    chat_project_id: UUID | None = None,
    exclude_sensitive: bool = False,
) -> str:
    """Return the scoped prompt memory block, using semantic cache when enabled."""
    if not user.memory_enabled:
        return ""

    omit_project_memory = chat_project_id is not None
    max_chars = settings.memory_inject_max_chars
    key = seams._memory_block_key(user.id)
    if query_text and settings.semantic_memory_enabled:
        q = query_text.strip()
        redis = seams.get_redis_client()
        try:
            generation = await redis.get(seams._memory_generation_key(user.id))
        except Exception:
            logger.debug("Memory generation read failed", exc_info=True)
            generation = None
        query_key = seams._memory_query_scoped_key(
            user.id,
            generation,
            q,
            omit_project_memory=omit_project_memory,
            exclude_sensitive=exclude_sensitive,
        )
        try:
            cached = await redis.get(query_key)
            if cached is not None:
                return cast(str, cached)
        except Exception:
            logger.debug("Memory query cache read failed", exc_info=True)

        from app.gateways import embedding_gateway

        query_vec = await embedding_gateway.get_or_embed_query(
            settings,
            user.id,
            q,
            embed_timeout=settings.memory_query_embed_timeout_seconds,
        )
        if query_vec is not None:
            block = await seams._semantic_block_from_vec(
                session,
                user,
                settings,
                query_vec,
                omit_project_memory=omit_project_memory,
                exclude_sensitive=exclude_sensitive,
            )
            await seams._write_query_block_cache(query_key, block, settings)
            return block

        memories = await seams.load_relevant_memories(
            session,
            user,
            settings,
            omit_project_memory=omit_project_memory,
        )
        memories = filter_surface_memories(seams, memories, exclude_sensitive=exclude_sensitive)
        block = seams.format_memory_block(memories, max_chars=max_chars)
        await seams._write_query_block_cache(query_key, block, settings)
        warm_task = seams.create_background_task(
            seams._warm_semantic_memory_cache(
                settings,
                user.id,
                q,
                omit_project_memory=omit_project_memory,
            ),
            name="warm_semantic_memory_cache",
        )
        warm_task.add_done_callback(
            lambda task: logger.debug("Semantic memory warm failed", exc_info=task.exception())
            if not task.cancelled() and task.exception()
            else None
        )
        return block

    redis = seams.get_redis_client()
    parts = [key]
    if omit_project_memory:
        parts.append("p")
    if exclude_sensitive:
        parts.append("x")
    cache_key = ":".join(parts)
    try:
        cached = await redis.get(cache_key)
        if cached is not None:
            return cast(str, cached)
    except Exception:
        logger.debug("Memory block cache read failed", exc_info=True)

    memories = await seams.load_relevant_memories(
        session,
        user,
        settings,
        omit_project_memory=omit_project_memory,
    )
    memories = filter_surface_memories(seams, memories, exclude_sensitive=exclude_sensitive)
    block = seams.format_memory_block(memories, max_chars=max_chars)
    try:
        await redis.set(cache_key, block, ex=settings.memory_cache_ttl)
    except Exception:
        logger.debug("Memory block cache write failed", exc_info=True)
    return block

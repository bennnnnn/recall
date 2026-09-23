import hashlib
import logging
from typing import Any
from uuid import UUID

from app.core.config import Settings

logger = logging.getLogger(__name__)


def memory_query_cache_key(user_id: UUID, generation: bytes | str | None, query_text: str) -> str:
    digest = hashlib.sha256(query_text.strip().lower().encode()).hexdigest()[:32]
    if generation is None:
        gen_tag = "0"
    elif isinstance(generation, bytes):
        gen_tag = generation.decode()
    else:
        gen_tag = generation
    return f"memquery:{user_id}:{gen_tag}:{digest}"


def memory_query_scoped_key(
    user_id: UUID,
    generation: bytes | str | None,
    query_text: str,
    *,
    omit_project_memory: bool,
    exclude_sensitive: bool,
) -> str:
    scope = "p" if omit_project_memory else "g"
    sens = "x" if exclude_sensitive else "a"
    return f"{memory_query_cache_key(user_id, generation, query_text)}:{scope}:{sens}"


def memory_block_key(user_id: UUID) -> str:
    return f"memblock:{user_id}"


def memory_generation_key(user_id: UUID) -> str:
    return f"memgen:{user_id}"


async def write_query_block_cache(
    seams: Any, cache_key: str, block: str, settings: Settings
) -> None:
    try:
        await seams.get_redis_client().set(
            cache_key,
            block,
            ex=max(30, settings.memory_query_cache_ttl),
        )
    except Exception:
        logger.debug("Memory query cache write failed", exc_info=True)


async def invalidate_memory_block(seams: Any, user_id: UUID) -> None:
    """Bump the query generation and drop every scoped block-cache key."""
    try:
        redis = seams.get_redis_client()
        await redis.incr(memory_generation_key(user_id))
        block_key = memory_block_key(user_id)
        await redis.delete(
            block_key,
            f"{block_key}:p",
            f"{block_key}:x",
            f"{block_key}:p:x",
        )
    except Exception:
        logger.debug("Memory block cache invalidation failed", exc_info=True)

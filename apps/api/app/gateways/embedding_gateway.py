"""Embedding gateway — product alias only."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from uuid import UUID

from litellm import aembedding

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.gateways import mock_llm
from app.models.model_catalog import get as get_model

logger = logging.getLogger(__name__)

# Per-user, per-query embedding cache namespace. Shared by memory semantic
# recall and attachment RAG so a single chat turn embeds the query once, not
# twice (each used to call embed_text independently on the same query text).
_EMBED_CACHE_PREFIX = "memembed"


def _embed_cache_key(user_id: UUID, query: str) -> str:
    digest = hashlib.sha256(query.strip().lower().encode()).hexdigest()[:32]
    return f"{_EMBED_CACHE_PREFIX}:{user_id}:{digest}"


async def embed_text(settings: Settings, text: str) -> list[float] | None:
    if mock_llm.should_mock_llm(settings):
        # Deterministic tiny vector padded to the pgvector column dimension so
        # dev/mock mode exercises the full RAG pipeline (has_chunks_for_chat /
        # search_semantic require embedding IS NOT NULL). Zero-fill keeps the
        # signal in the first 8 dims; the rest are zero so cosine similarity is
        # driven by the meaningful dims only.
        from app.repositories.attachment_chunks import EMBEDDING_DIM

        seed = [0.1] * 8
        return seed + [0.0] * (EMBEDDING_DIM - len(seed))

    route = get_model("embedding-model")
    api_key = getattr(settings, route.api_key_field, "")
    if not api_key:
        return None

    kwargs: dict = {"api_key": api_key}
    if route.api_base:
        kwargs["api_base"] = route.api_base

    try:
        async with asyncio.timeout(settings.background_llm_timeout_seconds):
            response = await aembedding(
                model=route.model, input=[text[: settings.embedding_input_max_chars]], **kwargs
            )
        data = response.data[0]["embedding"]
        return list(data)
    except Exception:
        logger.exception("Embedding failed")
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def parse_embedding(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [float(x) for x in data]
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return None


def serialize_embedding(vec: list[float]) -> str:
    return json.dumps(vec)


async def get_or_embed_query(
    settings: Settings,
    user_id: UUID,
    query: str,
    *,
    embed_timeout: float | None = None,
) -> list[float] | None:
    """Embed ``query`` once per (user, query) using a shared Redis cache.

    Memory semantic recall and attachment RAG both need the query embedding
    on a chat turn; previously each called :func:`embed_text` independently —
    two paid HTTP calls on a cache miss. This reads the ``memembed:`` cache
    first, embeds on a miss, and writes the cache so the second caller (or
    the next turn) hits. Cache failures degrade to a direct embed (never
    block the turn on Redis). ``embed_timeout`` bounds only the live embed
    call, not the cache reads.
    """
    q = query.strip()
    if not q:
        return None
    key = _embed_cache_key(user_id, q)
    try:
        cached = await get_redis_client().get(key)
        if cached is not None:
            raw = cached if isinstance(cached, str) else cached.decode()
            parsed = parse_embedding(raw)
            if parsed:
                return parsed
    except Exception:
        logger.debug("Embed cache read failed; falling back to live embed", exc_info=True)
    try:
        # asyncio.timeout(None) disables the timeout, so a single path covers
        # both the bounded (RAG/memory live) and unbounded (warm) cases.
        async with asyncio.timeout(embed_timeout):
            vec = await embed_text(settings, q)
    except Exception:
        logger.debug("Embed call failed", exc_info=True)
        return None
    if vec:
        try:
            await get_redis_client().set(
                key,
                serialize_embedding(vec),
                ex=max(60, settings.memory_query_embed_cache_ttl),
            )
        except Exception:
            logger.debug("Embed cache write failed", exc_info=True)
    return vec

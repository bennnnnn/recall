"""Embedding gateway — product alias only."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from litellm import aembedding

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.gateways import llm_spend, mock_llm
from app.models.model_catalog import get as get_model

logger = logging.getLogger(__name__)

# Per-user, per-query embedding cache namespace. Shared by memory semantic
# recall and attachment RAG so a single chat turn embeds the query once, not
# twice (each used to call embed_text independently on the same query text).
_EMBED_CACHE_PREFIX = "memembed"


def _embed_cache_key(user_id: UUID, query: str) -> str:
    digest = hashlib.sha256(query.strip().lower().encode()).hexdigest()[:32]
    return f"{_EMBED_CACHE_PREFIX}:{user_id}:{digest}"


def _mock_vector() -> list[float]:
    # Deterministic tiny vector padded to the pgvector column dimension so
    # dev/mock mode exercises the full RAG pipeline (has_chunks_for_chat /
    # search_semantic require embedding IS NOT NULL). Zero-fill keeps the
    # signal in the first 8 dims; the rest are zero so cosine similarity is
    # driven by the meaningful dims only.
    # Keep in sync with attachment chunk vectors (pgvector 1536).
    seed = [0.1] * 8
    return seed + [0.0] * (1536 - len(seed))


def _input_index(item: Any) -> int:
    try:
        return int(item["index"])
    except (KeyError, TypeError, ValueError):
        return 0  # a stable sort keeps the provider's order


async def _embed_request(settings: Settings, texts: list[str]) -> list[list[float]] | None:
    """One provider request for ``texts``; vectors in input order, or None when it failed."""
    if mock_llm.should_mock_llm(settings):
        return [_mock_vector() for _ in texts]

    route = get_model("embedding-model")
    api_key = getattr(settings, route.api_key_field, "")
    if not api_key:
        return None

    kwargs: dict = {"api_key": api_key}
    if route.api_base:
        kwargs["api_base"] = route.api_base

    cap = settings.embedding_input_max_chars
    try:
        async with asyncio.timeout(settings.background_llm_timeout_seconds):
            response = await aembedding(
                model=route.model, input=[text[:cap] for text in texts], **kwargs
            )
        llm_spend.meter_model_call(route.id, response)
        # Providers may answer out of order; each item carries its input index.
        rows = sorted(response.data, key=_input_index)
        vectors = [list(item["embedding"]) for item in rows]
    except Exception:
        logger.exception("Embedding failed")
        return None
    if len(vectors) != len(texts):
        logger.error("Embedding returned %d vectors for %d inputs", len(vectors), len(texts))
        return None
    return vectors


async def embed_text(settings: Settings, text: str) -> list[float] | None:
    vectors = await _embed_request(settings, [text])
    return vectors[0] if vectors else None


async def embed_many(
    settings: Settings,
    texts: list[str],
    *,
    concurrency: int,
) -> list[list[float] | None]:
    """Embed ``texts`` in requests of ``embedding_batch_size`` inputs, at most
    ``concurrency`` requests in flight.

    Results are in input order. A batch whose request failed is embedded one
    text at a time (``embed_text``), so one bad input cannot void its whole
    batch; a text that still fails is None in its slot and the caller decides
    whether to drop it. An error ``embed_text`` does not catch propagates and
    fails the call.
    """
    semaphore = asyncio.Semaphore(max(1, concurrency))
    size = max(1, settings.embedding_batch_size)
    batches = [texts[start : start + size] for start in range(0, len(texts), size)]

    async def _batch(batch: list[str]) -> list[list[float] | None]:
        async with semaphore:
            vectors = await _embed_request(settings, batch)
            if vectors is not None:
                return list(vectors)
            return [await embed_text(settings, text) for text in batch]

    results = await asyncio.gather(*(_batch(batch) for batch in batches))
    return [vector for batch in results for vector in batch]


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

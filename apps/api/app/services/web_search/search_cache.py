"""Cached web search execution via Tavily (+ DuckDuckGo fallback)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.gateways import web_search_gateway
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import User
from app.services import quota as quota_service

logger = logging.getLogger(__name__)


def _inject_before_last_user(messages: list[dict[str, str]], block: str) -> list[dict[str, str]]:
    augmented = list(messages)
    insert_at = len(augmented)
    for index in range(len(augmented) - 1, -1, -1):
        if augmented[index].get("role") == "user":
            insert_at = index
            break
    augmented.insert(insert_at, {"role": "system", "content": block})
    return augmented


async def _run_search(
    settings: Settings,
    queries: list[str],
    *,
    user: User | None = None,
    redis: Redis | None = None,
) -> tuple[list[WebSearchHit], list[str]]:
    limit = max(1, min(settings.web_search_max_results, 10))
    if not queries:
        return [], []

    results = await asyncio.gather(
        *(
            _search_with_cache(settings, query, max_results=limit, user=user, redis=redis)
            for query in queries
        )
    )

    seen_urls: set[str] = set()
    merged: list[WebSearchHit] = []
    for hits in results:
        for hit in hits:
            key = hit.url.strip().lower() or hit.title.strip().lower()
            if key in seen_urls:
                continue
            seen_urls.add(key)
            merged.append(hit)
            if len(merged) >= limit:
                return merged, list(queries)

    return merged, list(queries)


def _search_cache_key(query: str, max_results: int) -> str:
    digest = hashlib.sha256(query.strip().lower().encode()).hexdigest()[:32]
    return f"websearch:{max_results}:{digest}"


async def _search_with_cache(
    settings: Settings,
    query: str,
    *,
    max_results: int,
    user: User | None = None,
    redis: Redis | None = None,
) -> list[WebSearchHit]:
    cleaned = query.strip()
    if not cleaned:
        return []

    cache_key = _search_cache_key(cleaned, max_results)
    redis = redis or get_redis_client()

    def _hits_from_payload(payload: object) -> list[WebSearchHit] | None:
        if not isinstance(payload, list):
            return None
        return [
            WebSearchHit(
                title=str(item.get("title") or ""),
                url=str(item.get("url") or ""),
                snippet=str(item.get("snippet") or ""),
            )
            for item in payload
            if isinstance(item, dict)
        ]

    try:
        cached = await redis.get(cache_key)
        if cached:
            hits = _hits_from_payload(json.loads(cached))
            if hits is not None:
                return hits
    except Exception:
        logger.debug("Web search cache read failed", exc_info=True)

    lock_key = f"{cache_key}:lock"
    acquired = False
    try:
        acquired = bool(await redis.set(lock_key, "1", ex=30, nx=True))
    except Exception:
        logger.debug("Web search lock acquire failed", exc_info=True)

    if not acquired:
        for _ in range(20):
            await asyncio.sleep(0.1)
            try:
                cached = await redis.get(cache_key)
                if cached:
                    hits = _hits_from_payload(json.loads(cached))
                    if hits is not None:
                        return hits
            except Exception:
                logger.debug("Web search cache read failed", exc_info=True)

    try:
        skip_tavily = False
        if user is not None:
            client = redis or get_redis_client()
            tavily_limit = quota_service.tavily_search_limit_for_user(user, settings)
            if not await quota_service.reserve_tavily_search(
                client,
                user.id,
                limit=tavily_limit,
            ):
                skip_tavily = True

        hits = await web_search_gateway.search_web(
            settings,
            cleaned,
            max_results=max_results,
            skip_tavily=skip_tavily,
        )
        if hits:
            try:
                await redis.set(
                    cache_key,
                    json.dumps([asdict(hit) for hit in hits]),
                    ex=max(60, settings.web_search_cache_ttl),
                )
            except Exception:
                logger.debug("Web search cache write failed", exc_info=True)
        return hits
    finally:
        if acquired:
            try:
                await redis.delete(lock_key)
            except Exception:
                logger.debug("Web search lock release failed", exc_info=True)

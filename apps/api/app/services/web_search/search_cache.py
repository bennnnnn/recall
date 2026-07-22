"""Cached web search execution via Tavily (+ DuckDuckGo fallback)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.gateways import web_search_gateway
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import User
from app.services import quota as quota_service

logger = logging.getLogger(__name__)


@dataclass
class _TurnTavilyBudget:
    """One Tavily reservation shared across every query in a single search turn.

    A turn fans out into several queries (e.g. sports/news build 3-4) that run
    concurrently. Reserving per query would let one turn spend 3-4 of the
    user's daily Tavily searches instead of one. This reserves at most once per
    turn, lazily (only when a query actually misses cache and is about to hit
    the network), and every concurrent query reuses that single decision. The
    lock makes the check-then-reserve atomic across the gathered coroutines so
    two cache-missing queries can't both reserve.
    """

    settings: Settings
    user: User | None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _decided: bool = False
    _skip_tavily: bool = False

    async def skip_tavily(self, redis: Redis) -> bool:
        """Whether this turn must skip Tavily (daily cap hit). Reserves once."""
        if self.user is None:
            return False
        # Only spend the daily Tavily budget when Tavily can actually run. With
        # no key (or web search off) the turn falls back to free, uncapped
        # DuckDuckGo, so reserving here would burn a slot for a search Tavily
        # never performs.
        if not web_search_gateway.is_configured(self.settings):
            return False
        async with self._lock:
            if not self._decided:
                limit = quota_service.tavily_search_limit_for_user(self.user, self.settings)
                reserved = await quota_service.reserve_tavily_search(
                    redis, self.user.id, limit=limit
                )
                self._skip_tavily = not reserved
                self._decided = True
            return self._skip_tavily


async def run_cached_search(
    settings: Settings,
    queries: list[str],
    *,
    user: User | None = None,
    redis: Redis | None = None,
) -> tuple[list[WebSearchHit], list[str]]:
    """Public cached + quota-aware search (heuristic augment and MCP tool loop).

    Applies the per-user daily Tavily reservation and Redis result cache so
    model-initiated ``web_search`` calls cannot bypass the heuristic path's cap.
    """
    return await _run_search(settings, queries, user=user, redis=redis)


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

    # One Tavily reservation for the whole turn, shared by the fanned-out
    # queries — a multi-query turn spends one daily search, not one per query.
    budget = _TurnTavilyBudget(settings=settings, user=user)
    results = await asyncio.gather(
        *(
            _search_with_cache(settings, query, max_results=limit, budget=budget, redis=redis)
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
    budget: _TurnTavilyBudget | None = None,
    redis: Redis | None = None,
) -> list[WebSearchHit]:
    cleaned = query.strip()
    if not cleaned:
        return []

    cache_key = _search_cache_key(cleaned, max_results)
    cache_redis = redis if redis is not None else get_redis_client()

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
        cached = await cache_redis.get(cache_key)
        if cached:
            hits = _hits_from_payload(json.loads(cached))
            if hits is not None:
                return hits
    except Exception:
        logger.debug("Web search cache read failed", exc_info=True)

    lock_key = f"{cache_key}:lock"
    acquired = False
    try:
        acquired = bool(await cache_redis.set(lock_key, "1", ex=30, nx=True))
    except Exception:
        logger.debug("Web search lock acquire failed", exc_info=True)

    if not acquired:
        for _ in range(20):
            await asyncio.sleep(0.1)
            try:
                cached = await cache_redis.get(cache_key)
                if cached:
                    hits = _hits_from_payload(json.loads(cached))
                    if hits is not None:
                        return hits
            except Exception:
                logger.debug("Web search cache read failed", exc_info=True)

    try:
        # Reserve one Tavily slot for the whole turn (shared budget), only now
        # that this query has missed cache and is about to hit the network.
        skip_tavily = await budget.skip_tavily(cache_redis) if budget is not None else False

        hits = await web_search_gateway.search_web(
            settings,
            cleaned,
            max_results=max_results,
            skip_tavily=skip_tavily,
        )
        if hits:
            try:
                await cache_redis.set(
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
                await cache_redis.delete(lock_key)
            except Exception:
                logger.debug("Web search lock release failed", exc_info=True)

"""Web search — Tavily primary, DuckDuckGo fallback (server-side only)."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_TIMEOUT_SECONDS = 12.0


@dataclass(frozen=True)
class WebSearchHit:
    title: str
    url: str
    snippet: str


def is_configured(settings: Settings) -> bool:
    return bool(settings.web_search_enabled and settings.tavily_api_key.strip())


def mock_search_results(query: str, *, max_results: int) -> list[WebSearchHit]:
    return [
        WebSearchHit(
            title=f"Mock search: {query[:80]}",
            url="https://example.com/mock-search",
            snippet=(
                "Mock web search result (set TAVILY_API_KEY in apps/api/.env for live results). "
                "Use this to verify search injection in dev."
            ),
        )
    ][:max_results]


def _is_newsish_query(query: str) -> bool:
    return bool(
        re.search(
            r"\b(news|headlines|happening|world|today|breaking|events|"
            r"scores?|results?|match(?:es)?|soccer|football|fifa|world\s+cup|"
            r"nba|nfl|mlb|nhl|standings|fixture)\b",
            query,
            re.I,
        )
    )


def _ddg_item_to_hit(item: dict[str, object]) -> WebSearchHit | None:
    title = str(item.get("title") or "").strip()
    url = str(item.get("href") or item.get("link") or item.get("url") or "").strip()
    snippet = str(item.get("body") or item.get("content") or "").strip()
    if not title and not snippet:
        return None
    return WebSearchHit(
        title=title or url or "Untitled",
        url=url,
        snippet=snippet[:600],
    )


def _search_duckduckgo_sync(query: str, max_results: int) -> list[WebSearchHit]:
    try:
        from ddgs import DDGS
    except ImportError:
        logger.warning("ddgs package not installed")
        return []

    hits: list[WebSearchHit] = []

    def _fetch(items: object) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if len(hits) >= max_results:
                return
            if not isinstance(item, dict):
                continue
            hit = _ddg_item_to_hit(item)
            if hit is not None:
                hits.append(hit)

    try:
        with DDGS() as ddgs:
            if _is_newsish_query(query):
                try:
                    _fetch(list(ddgs.news(query, max_results=max_results)))
                except Exception:
                    logger.warning("DuckDuckGo news search failed for query=%r", query[:120])
            if not hits:
                try:
                    _fetch(list(ddgs.text(query, max_results=max_results)))
                except Exception:
                    logger.warning("DuckDuckGo text search failed for query=%r", query[:120])
            if not hits and not _is_newsish_query(query):
                try:
                    _fetch(list(ddgs.news(query, max_results=max_results)))
                except Exception:
                    logger.warning("DuckDuckGo news fallback failed for query=%r", query[:120])
    except Exception:
        logger.exception("DuckDuckGo search failed for query=%r", query[:120])
    return hits


async def _search_duckduckgo(query: str, max_results: int) -> list[WebSearchHit]:
    return await asyncio.to_thread(_search_duckduckgo_sync, query, max_results)


async def _search_tavily(settings: Settings, query: str, max_results: int) -> list[WebSearchHit]:
    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": False,
    }

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            response = await client.post(TAVILY_SEARCH_URL, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.exception("Tavily web search failed for query=%r", query[:120])
        return []

    hits: list[WebSearchHit] = []
    for item in data.get("results") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("content") or item.get("snippet") or "").strip()
        if not title and not snippet:
            continue
        hits.append(
            WebSearchHit(
                title=title or url or "Untitled",
                url=url,
                snippet=snippet[:600],
            )
        )
    return hits


async def search_web(
    settings: Settings,
    query: str,
    *,
    max_results: int | None = None,
    skip_tavily: bool = False,
) -> list[WebSearchHit]:
    cleaned = query.strip()
    if not cleaned:
        return []

    limit = max_results if max_results is not None else settings.web_search_max_results
    limit = max(1, min(limit, 10))

    if not settings.web_search_enabled:
        return []

    if not skip_tavily and settings.tavily_api_key.strip():
        hits = await _search_tavily(settings, cleaned, limit)
        if hits:
            return hits

    if settings.web_search_fallback_enabled:
        hits = await _search_duckduckgo(cleaned, limit)
        if hits:
            return hits

    if settings.mock_llm_enabled:
        return mock_search_results(cleaned, max_results=limit)

    return []

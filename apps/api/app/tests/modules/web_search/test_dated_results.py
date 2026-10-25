"""A search about now also reads news pages, each with the day it was published.

Live 2026-10-25: "who won the world series this year?" was answered "The Tampa Bay Rays
won" from a winners' table whose 2026 row read "Tampa Bay Rays | 0 | 1 | Milwaukee
Brewers", while the series was one game old. No page said when it was written.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit, _published_day, search_web
from app.modules.web_search.formatting import format_search_block
from app.modules.web_search.recency import wants_dated_results
from app.modules.web_search.search_cache import _run_search, _search_cache_key
from app.modules.web_search.source_dates import published_note


@pytest.mark.parametrize(
    ("text", "dated"),
    [
        ("who won the world series this year?", True),
        ("wait is it over already? i thought it just started", True),
        ("so what's the score in the series right now?", True),
        ("is the new zelda out yet", True),
        ("latest iphone", True),
        ("who's winning so far?", True),
        ("has the season started?", True),
        ("why do seasons change?", False),
        ("has the season started yet?", True),
        ("what is the capital of france?", False),
        ("who wrote hamlet", False),
        ("how does photosynthesis work", False),
        ("explain the offside rule", False),
    ],
)
def test_wants_dated_results(text: str, dated: bool) -> None:
    assert wants_dated_results(text) is dated


@pytest.mark.parametrize(
    ("raw", "day"),
    [
        ("Sat, 24 Oct 2026 10:00:00 GMT", "2026-10-24"),
        ("2026-10-23T21:00:24Z", "2026-10-23"),
        ("2026-10-23", "2026-10-23"),
        ("", ""),
        ("yesterday", ""),
        (None, ""),
    ],
)
def test_published_day(raw: object, day: str) -> None:
    assert _published_day(raw) == day


def test_the_note_names_the_weekday_and_how_long_ago() -> None:
    today = date(2026, 10, 25)
    assert published_note("2026-10-24", today) == (
        "[Published Saturday, October 24, 2026 (yesterday).] "
    )
    assert published_note("", today) == ""
    assert published_note("not a day", today) == ""


def _tavily(results: list[dict[str, str]]) -> AsyncMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {"results": results}
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_a_news_search_asks_tavily_for_news_and_keeps_the_day() -> None:
    settings = Settings(tavily_api_key="test-key", web_search_fallback_enabled=False)
    client = _tavily(
        [
            {
                "title": "Rays score 4 runs in first inning of World Series Game 2",
                "url": "https://www.mlb.com/news/rays-game-2",
                "content": "Game 2 at American Family Field.",
                "published_date": "Sun, 25 Oct 2026 04:00:00 GMT",
            }
        ]
    )
    with patch("app.gateways.web_search_gateway.get_pooled_client", return_value=client):
        hits = await search_web(settings, "World Series 2026", topic="news")
    assert client.post.await_args.kwargs["json"]["topic"] == "news"
    assert hits[0].published == "2026-10-25"


@pytest.mark.asyncio
async def test_a_news_search_finds_nothing_without_tavily() -> None:
    """DuckDuckGo gives no dates; the turn's own search already ran it."""
    settings = Settings(mock_llm_enabled=True, tavily_api_key="", web_search_fallback_enabled=True)
    assert await search_web(settings, "World Series 2026", topic="news") == []
    assert await search_web(settings, "World Series 2026")


def test_the_news_search_has_its_own_cache_entry() -> None:
    general = _search_cache_key("world series", 5, user_id="u")
    assert _search_cache_key("world series", 5, user_id="u", topic="general") == general
    assert _search_cache_key("world series", 5, user_id="u", topic="news") == f"{general}:news"


def _hit(name: str, published: str = "") -> WebSearchHit:
    return WebSearchHit(
        title=name, url=f"https://example.com/{name}", snippet=name, published=published
    )


@pytest.mark.asyncio
async def test_a_dated_search_puts_the_newest_page_first_beside_the_general_ones(fake_redis):
    settings = Settings(web_search_max_results=5)
    news = [_hit("game-1", "2026-10-24"), _hit("game-2", "2026-10-25"), _hit("shared")]
    general = [_hit("winners-list"), _hit("shared"), _hit("history")]

    async def search(_settings, query, *, max_results, skip_tavily=False, topic="general"):
        return news if topic == "news" else general

    with patch("app.modules.web_search.search_cache.web_search_gateway.search_web", search):
        merged, tried = await _run_search(
            settings, ["world series 2026"], redis=fake_redis, dated=True
        )
        plain, _ = await _run_search(settings, ["world series 2026"], redis=fake_redis)

    assert tried == ["world series 2026"]
    assert [hit.title for hit in merged] == [
        "game-2",
        "winners-list",
        "game-1",
        "shared",
        "history",
    ]
    assert [hit.title for hit in plain] == ["winners-list", "shared", "history"]
    # The news pages keep their days through the cache.
    again, _ = await _run_search(settings, ["world series 2026"], redis=fake_redis, dated=True)
    assert [hit.published for hit in again][:1] == ["2026-10-25"]


def test_the_search_block_says_when_each_page_was_published() -> None:
    hits = [
        _hit("game-2", "2026-10-25"),
        WebSearchHit(title="winners", url="https://example.com/w", snippet="2025 Dodgers"),
    ]
    with patch("app.modules.web_search.formatting.local_today", return_value=date(2026, 10, 25)):
        block = format_search_block(hits, user_timezone="America/New_York")
    assert (
        "1. game-2 (https://example.com/game-2) — [Published Sunday, October 25, 2026 (today).]"
        in block
    )
    assert "2. winners (https://example.com/w) — 2025 Dodgers" in block

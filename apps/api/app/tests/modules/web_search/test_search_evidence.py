"""What a search hands the reply, and the claim check after it, is what the pages said.

Live round, 2026-11-05: "what's the latest iOS version" read endoflife.date's table cut at
600 characters, "| 27 | 3 weeks ago | Yes | Yes | 27", and answered the year-old iOS 26.7.1;
"latest iOS version 2026", the query with the year added, ranked the iOS 26 pages first.
"Who is top of the Premier League" read two tables from different weeks and named the older
leader. "How many people died in hurricane Melissa" had "at least 76" cut by the claim check
under a page that said it, and the reply began "Some people were still missing".
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.gateways.mcp.base import ToolResult
from app.gateways.web_search_gateway import SNIPPET_CHARS, WebSearchHit, search_web
from app.modules.chat.claim_check import _sentences
from app.modules.chat.claim_evidence import costs_its_sentence, figures, stated_by_a_page
from app.modules.chat.tool_loop.results import _search_hits_from_tool_result
from app.modules.web_search.formatting import NEWEST_SOURCE_RULE, format_search_block
from app.modules.web_search.search_cache import _search_cache_key
from app.modules.web_search.tool import WebSearchAdapter
from app.tests.tool_context import tool_context

_PASSAGES = " [...] ".join(f"Passage {n}: " + "words " * 80 for n in range(3))


def _tavily(content: str) -> AsyncMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "results": [{"title": "iOS", "url": "https://example.com/ios", "content": content}]
    }
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    return client


async def _search(**kwargs: Any) -> tuple[list[WebSearchHit], dict[str, Any]]:
    settings = Settings(tavily_api_key="test-key", web_search_fallback_enabled=False)
    client = _tavily(_PASSAGES)
    with patch("app.gateways.web_search_gateway.get_pooled_client", return_value=client):
        hits = await search_web(settings, "what's the latest iOS version", **kwargs)
    return hits, client.post.await_args.kwargs["json"]


@pytest.mark.asyncio
async def test_a_page_keeps_every_passage_the_search_sent() -> None:
    hits, payload = await _search()
    assert len(_PASSAGES) < SNIPPET_CHARS
    assert hits[0].snippet == _PASSAGES.strip()
    assert "Passage 2" in hits[0].snippet
    # Every page comes with its day when the search can tell, not only news pages.
    assert payload["include_published_date"] is True
    assert "time_range" not in payload


@pytest.mark.asyncio
async def test_an_ask_about_now_keeps_to_pages_from_the_last_year() -> None:
    _hits, payload = await _search(recent=True)
    assert payload["query"] == "what's the latest iOS version"
    assert payload["time_range"] == "year"


def test_a_recent_search_has_its_own_cache_entry() -> None:
    plain = _search_cache_key("latest ios", 5, user_id="u")
    assert _search_cache_key("latest ios", 5, user_id="u", recent=True) == f"{plain}:recent"


def test_the_results_say_to_go_by_the_newest_page() -> None:
    block = format_search_block([WebSearchHit("Table", "https://espn.example", "Arsenal 24")])
    assert NEWEST_SOURCE_RULE in block


@pytest.mark.asyncio
async def test_a_model_written_search_says_it_too_and_keeps_its_pages() -> None:
    page = WebSearchHit("Table", "https://espn.example", "x " * 400, "2026-11-01")
    run_search = AsyncMock(return_value=([page], ["q"]))
    with patch("app.modules.web_search.tool.run_cached_search", run_search):
        result = await WebSearchAdapter(Settings()).invoke(
            {"query": "premier league table"}, tool_context(user_query="who is top")
        )
    assert NEWEST_SOURCE_RULE in result.content
    # The turn's sources are the pages the reply read, not the chips' 280 characters.
    kept = _search_hits_from_tool_result(result)
    assert kept == [page]
    assert result.data is not None and len(result.data["hits"][0]["snippet"]) <= 280


def test_a_result_with_chips_alone_still_gives_its_sources() -> None:
    result = ToolResult(
        name="web_search", content="", data={"hits": [{"title": "T", "url": "u", "snippet": "s"}]}
    )
    assert _search_hits_from_tool_result(result) == [WebSearchHit("T", "u", "s")]


_WORLD_VISION = WebSearchHit(
    "Hurricane Melissa: Facts, FAQs, and how to help",
    "https://www.worldvision.org/melissa",
    "At least 76 people confirmed died across the region: Haiti (43 deaths), Jamaica "
    "(32 deaths), and the Dominican Republic (1 death). Damage of $8,800,000,000.",
)


@pytest.mark.parametrize(
    "quote, stated",
    [
        ("Hurricane Melissa killed at least 76 people", True),
        ("43 in Haiti and 32 in Jamaica", True),
        ("damage of $8.8 billion", False),
        ("damage of 8,800,000,000 dollars", True),
        ("at least 90 people died", False),
        # Two pages' figures together are not one page's claim.
        ("76 died, 12 of them in Cuba", False),
        # A year dates a claim; it does not make one: no figure, nothing stated.
        ("Melissa's status was upgraded in 2026", False),
        ("Cytonn has been reinstated", False),
    ],
)
def test_a_figure_one_page_states_is_not_cut(quote: str, stated: bool) -> None:
    other = WebSearchHit("UN News", "https://news.un.org", "12 days of rain. 5 million tonnes.")
    assert stated_by_a_page(figures(quote), [_WORLD_VISION, other]) is stated


@pytest.mark.parametrize(
    "line, sentences",
    [
        (
            "It peaks at **9:53 a.m. EST** on Tuesday. It is a supermoon.",
            ["It peaks at **9:53 a.m. EST** on Tuesday.", "It is a supermoon."],
        ),
        (
            "Rates rose in the U.S. Europe held steady.",
            ["Rates rose in the U.S. Europe held steady."],
        ),
        # A cut there would leave the bold open.
        (
            "**A bold start. Still bold** and on. Then plain.",
            ["**A bold start. Still bold** and on.", "Then plain."],
        ),
        ("One. Two.", ["One.", "Two."]),
        # A bullet's marker and an underscore inside a word open no emphasis (review).
        (
            "* Gane is the champion. He won in September.",
            ["* Gane is the champion.", "He won in September."],
        ),
        ("See my_notes.txt here. Then go.", ["See my_notes.txt here.", "Then go."]),
    ],
)
def test_a_sentence_ends_neither_at_initials_nor_inside_bold(
    line: str, sentences: list[str]
) -> None:
    assert _sentences(line) == sentences


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "args, recent",
    [
        # The tool is for what changes: last year's pages unless the model says the past.
        ({}, True),
        ({"recent": True}, True),
        ({"recent": "yes"}, True),
        ({"recent": False}, False),
    ],
)
async def test_a_model_written_search_keeps_to_the_last_year_unless_about_the_past(
    args: dict[str, object], recent: bool
) -> None:
    """Live 2026-11-05: "who is top of the premier league table" names no time, was searched
    with none, and read a mid-October table. The news search beside it still follows the
    user's words, so it is not run here."""
    run_search = AsyncMock(return_value=([], ["q"]))
    with patch("app.modules.web_search.tool.run_cached_search", run_search):
        await WebSearchAdapter(Settings()).invoke(
            {"query": "Premier League table", **args},
            tool_context(user_query="who is top of the premier league table"),
        )
    sent: Any = run_search.await_args
    assert sent.kwargs["recent"] is recent
    assert sent.kwargs["dated"] is False


@pytest.mark.asyncio
async def test_a_recent_search_runs_no_news_search(fake_redis: Any) -> None:
    from app.modules.web_search.search_cache import _run_search

    topics: list[tuple[str, bool]] = []

    async def search(
        _settings: Any,
        query: str,
        *,
        max_results: int,
        skip_tavily: bool = False,
        topic: str = "general",
        recent: bool = False,
    ) -> list[WebSearchHit]:
        topics.append((topic, recent))
        return [WebSearchHit("T", "https://t.example", "s")]

    with patch("app.modules.web_search.search_cache.web_search_gateway.search_web", search):
        await _run_search(Settings(), ["premier league table"], redis=fake_redis, recent=True)
    assert topics == [("general", True)]


def test_the_tool_offers_recent_and_asks_for_no_year_in_the_query() -> None:
    tool = WebSearchAdapter(Settings()).to_openai_tool()["function"]
    recent = tool["parameters"]["properties"]["recent"]
    assert recent["default"] is True
    assert "no month or year" in tool["description"]


@pytest.mark.parametrize(
    "quote, kind, cut",
    [
        # A legal standing is always cut: matching words cleared contradicted ones (review).
        ("Acme is licensed in Spain", "legal", True),
        ("Acme is licensed in Spain", "status", True),
        # A figure a page states stays; one no page states goes.
        ("at least 76 people died", "figure", False),
        ("at least 90 people died", "figure", True),
        ("about three million people", "figure", False),
        # An attribution or a detail never costs the answer.
        ("beating defending champions Brazil", "other", False),
        ("according to ESPN", "attribution", False),
    ],
)
def test_only_a_legal_standing_or_an_unstated_figure_costs_its_sentence(
    quote: str, kind: str, cut: bool
) -> None:
    assert costs_its_sentence(quote, kind, [_WORLD_VISION]) is cut

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit, mock_search_results, search_web
from app.services.web_search import (
    augment_prompt_messages,
    build_search_queries,
    build_search_query,
    format_search_block,
    format_search_empty_block,
    format_sources_fence,
    needs_web_search,
    resolve_search_subject,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("search the web for iPhone 17 rumors", True),
        ("What's the latest news on SpaceX?", True),
        ("look up online who won the game last night", True),
        ("look it up", False),
        ("what's happening in the world today", True),
        ("what's cookin in the world", True),
        ("Show me yesterdays game", True),
        ("show me yesterday's game result", True),
        ("Ethiopias game score", True),
        ("explain Python decorators", False),
        ("what time is it", False),
        ("where am I?", False),
        ("help me write an email to my boss", False),
        ("remember that I like hiking", False),
    ],
)
def test_needs_web_search(text, expected):
    assert needs_web_search(text) is expected


def test_needs_web_search_look_it_up_with_prior():
    prior = ["Show me yesterdays game"]
    assert needs_web_search("Look it up", prior_user_messages=prior) is True
    assert needs_web_search("look it up", prior_user_messages=[]) is False


def test_needs_web_search_clarification_follow_up():
    prior = ["Show me yesterdays game", "Look it up"]
    assert needs_web_search("No, the ongoing one.", prior_user_messages=prior) is True


@pytest.mark.parametrize(
    "text",
    [
        "A",
        "B",
        "C",
        "D.",
        "Start an interactive vocabulary quiz for my English project",
    ],
)
def test_needs_web_search_skips_vocab_quiz(text):
    assert needs_web_search(text) is False
    assert needs_web_search(text, prior_user_messages=["Show me yesterdays game"]) is False


def test_build_search_query_clarification_world_cup():
    queries = build_search_queries(
        "No, the ongoing one.",
        user_timezone="UTC",
        prior_user_messages=["Show me yesterdays game"],
    )
    assert queries[0].startswith("FIFA World Cup 2026")
    assert "2026" in queries[0]


def test_build_search_query_team_score_not_world_cup():
    queries = build_search_queries("Ethiopias game score", user_timezone="UTC")
    assert queries[0].startswith("Ethiopia")
    assert "World Cup 2026 qualified" in queries[-1]
    assert not any(q.startswith("FIFA World Cup 2026 live") for q in queries)


def test_resolve_search_subject_follow_up():
    prior = ["Show me yesterdays game"]
    assert (
        resolve_search_subject("Look it up", prior_user_messages=prior) == "Show me yesterdays game"
    )


def test_build_search_query_strips_prefix():
    assert build_search_query("search the web for tesla stock price") == "tesla stock price"


def test_build_search_query_yesterday_sports():
    queries = build_search_queries("Show me yesterdays game", user_timezone="UTC")
    assert any("World Cup" in q or "soccer" in q.lower() for q in queries)
    assert any("June" in q or "yesterday" in q.lower() for q in queries)


def test_build_search_query_news_defaults():
    assert build_search_query("what's happening in the world today") == "top news today"


def test_build_search_query_follow_up_uses_prior():
    queries = build_search_queries(
        "Look it up",
        user_timezone="UTC",
        prior_user_messages=["Show me yesterdays game"],
    )
    assert queries[0] != "Look it up"
    assert any("scores" in q.lower() for q in queries)


def test_format_search_block_includes_links():
    block = format_search_block(
        [
            WebSearchHit(
                title="Example",
                url="https://example.com/a",
                snippet="Snippet text.",
            )
        ]
    )
    assert "Example (https://example.com/a)" in block
    assert "Snippet text." in block


def test_format_search_empty_block_forbids_roleplay():
    block = format_search_empty_block(["top news today"])
    assert "returned no usable results" in block
    assert "Do NOT invent tournament schedules" in block


def test_format_sources_fence_json():
    block = format_sources_fence(
        [WebSearchHit(title="Example", url="https://example.com/a", snippet="info")]
    )
    assert block.startswith("\n\n```sources\n")
    assert '"title": "Example"' in block
    assert '"url": "https://example.com/a"' in block


@pytest.mark.asyncio
async def test_augment_prompt_injects_results_before_user():
    settings = Settings(mock_llm_enabled=True, tavily_api_key="")
    messages = [
        {"role": "system", "content": "base"},
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "search the web for latest AI news"},
    ]
    with patch(
        "app.services.web_search.web_search_gateway.search_web",
        AsyncMock(
            return_value=[
                WebSearchHit(title="Hit", url="https://x.com", snippet="info"),
            ]
        ),
    ):
        out, hits = await augment_prompt_messages(
            messages,
            "search the web for latest AI news",
            settings,
        )
    assert out[-1]["role"] == "user"
    assert out[-2]["role"] == "system"
    assert "Web search results" in out[-2]["content"]
    assert len(hits) == 1


@pytest.mark.asyncio
async def test_augment_prompt_injects_empty_block_when_no_hits():
    settings = Settings(mock_llm_enabled=False, web_search_fallback_enabled=False)
    messages = [
        {"role": "system", "content": "base"},
        {"role": "user", "content": "what's happening in the world today"},
    ]
    with patch(
        "app.services.web_search.web_search_gateway.search_web",
        AsyncMock(return_value=[]),
    ):
        out, hits = await augment_prompt_messages(
            messages,
            "what's happening in the world today",
            settings,
        )
    assert out[-1]["role"] == "user"
    assert out[-2]["role"] == "system"
    assert "returned no usable results" in out[-2]["content"]
    assert hits == []


@pytest.mark.asyncio
async def test_augment_prompt_follow_up_look_it_up():
    settings = Settings()
    messages = [
        {"role": "system", "content": "base"},
        {"role": "user", "content": "Show me yesterdays game"},
        {"role": "assistant", "content": "I don't have live scores."},
        {"role": "user", "content": "Look it up"},
    ]
    with patch(
        "app.services.web_search.web_search_gateway.search_web",
        AsyncMock(
            return_value=[
                WebSearchHit(title="Scores", url="https://scores.example", snippet="2-1"),
            ]
        ),
    ) as search_mock:
        out, hits = await augment_prompt_messages(
            messages, "Look it up", settings, user_timezone="UTC"
        )
    assert search_mock.await_count >= 1
    first_query = search_mock.await_args_list[0].args[1]
    assert first_query.lower() != "look it up"
    assert "Web search results" in out[-2]["content"]
    assert len(hits) == 1


@pytest.mark.asyncio
async def test_augment_prompt_skips_when_not_needed():
    settings = Settings()
    messages = [{"role": "system", "content": "base"}]
    with patch(
        "app.services.web_search.web_search_gateway.search_web",
        AsyncMock(),
    ) as search_mock:
        out, hits = await augment_prompt_messages(messages, "explain recursion", settings)
    search_mock.assert_not_called()
    assert out == messages
    assert hits == []


@pytest.mark.asyncio
async def test_search_web_uses_mock_without_api_key():
    settings = Settings(mock_llm_enabled=True, tavily_api_key="", web_search_fallback_enabled=False)
    hits = await search_web(settings, "test query")
    assert len(hits) == 1
    assert "Mock search" in hits[0].title


@pytest.mark.asyncio
async def test_search_web_falls_back_to_duckduckgo():
    settings = Settings(mock_llm_enabled=False, tavily_api_key="", web_search_fallback_enabled=True)
    ddg_hit = WebSearchHit(title="DDG", url="https://news.example", snippet="story")
    with patch(
        "app.gateways.web_search_gateway._search_duckduckgo",
        AsyncMock(return_value=[ddg_hit]),
    ):
        hits = await search_web(settings, "top news today")
    assert hits[0].title == "DDG"


@pytest.mark.asyncio
async def test_search_web_returns_empty_when_all_providers_fail():
    settings = Settings(mock_llm_enabled=False, tavily_api_key="", web_search_fallback_enabled=True)
    with patch(
        "app.gateways.web_search_gateway._search_duckduckgo",
        AsyncMock(return_value=[]),
    ):
        hits = await search_web(settings, "test query")
    assert hits == []


def test_mock_search_results_respects_limit():
    hits = mock_search_results("query", max_results=1)
    assert len(hits) == 1

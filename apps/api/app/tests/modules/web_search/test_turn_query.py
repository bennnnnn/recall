"""What the tool loop's search sends: the topic, the resolved reference, or the message."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.modules.web_search import turn_query
from app.services import tool_loop
from app.tests.tool_context import tool_context


def _awaited(mock: AsyncMock) -> Any:
    """The last await of *mock*; fails the test when it was never awaited."""
    assert mock.await_args is not None
    return mock.await_args


_NAME_CHAT = [
    {"role": "user", "content": "My name is bini"},
    {"role": "assistant", "content": "Nice to meet you, Bini!"},
    {"role": "user", "content": "What is its meaning"},
    {"role": "assistant", "content": "The name bini is a short form of binary."},
    {"role": "user", "content": "Wrong"},
    {"role": "assistant", "content": "Sorry about that."},
    {"role": "user", "content": "Do a seearch"},
]


@pytest.mark.asyncio
async def test_bare_request_searches_the_resolved_topic() -> None:
    resolve = AsyncMock(return_value="Bini name meaning")
    with patch.object(turn_query, "resolve_reference", resolve):
        queries = await turn_query.search_queries_for_turn(Settings(), "Do a seearch", _NAME_CHAT)
    assert queries == ["Bini name meaning"]
    kwargs = _awaited(resolve).kwargs
    assert kwargs["kind"] == "search"
    assert ("assistant", "The name bini is a short form of binary.") in kwargs["turns"]


@pytest.mark.asyncio
async def test_bare_request_falls_back_past_one_word_reactions() -> None:
    with patch.object(turn_query, "resolve_reference", AsyncMock(return_value=None)):
        queries = await turn_query.search_queries_for_turn(Settings(), "Do a seearch", _NAME_CHAT)
    # The last line that stands alone, not "Wrong" and not the request itself.
    assert queries == ["What is its meaning"]


@pytest.mark.asyncio
async def test_named_topic_is_searched_as_is() -> None:
    resolve = AsyncMock()
    with patch.object(turn_query, "resolve_reference", resolve):
        queries = await turn_query.search_queries_for_turn(
            Settings(), "search for the meaning of bini", _NAME_CHAT
        )
    assert queries == ["the meaning of bini"]
    resolve.assert_not_awaited()


@pytest.mark.asyncio
async def test_pronoun_follow_up_is_resolved() -> None:
    messages = [
        {"role": "user", "content": "Who lived the longest?"},
        {"role": "assistant", "content": "Jeanne Calment, 122 years."},
        {"role": "user", "content": "when did she die?"},
    ]
    resolve = AsyncMock(return_value="Jeanne Calment death date")
    with patch.object(turn_query, "resolve_reference", resolve):
        queries = await turn_query.search_queries_for_turn(
            Settings(), "when did she die?", messages
        )
    assert queries == ["Jeanne Calment death date"]


@pytest.mark.asyncio
async def test_standalone_question_is_its_own_query() -> None:
    resolve = AsyncMock()
    messages = [{"role": "user", "content": "who won the lakers game last night"}]
    with patch.object(turn_query, "resolve_reference", resolve):
        queries = await turn_query.search_queries_for_turn(
            Settings(), "who won the lakers game last night", messages
        )
    assert queries == ["who won the lakers game last night"]
    resolve.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_loop_searches_the_topic_not_the_request() -> None:
    """The screenshot: "Do a seearch" used to reach Tavily as the words "Do a seearch"."""
    run_search = AsyncMock(return_value=([], ["Bini name meaning"]))
    ctx = tool_context()
    with (
        patch.object(turn_query, "resolve_reference", AsyncMock(return_value="Bini name meaning")),
        patch("app.modules.web_search.search_cache.run_cached_search", run_search),
    ):
        _messages, hits = await tool_loop._force_web_search_if_needed(
            settings=Settings(web_search_enabled=True),
            messages=list(_NAME_CHAT),
            search_hits=[],
            ctx=ctx,
            on_status=None,
            should_cancel=None,
            search_required=True,
        )
    assert hits == []
    assert _awaited(run_search).args[1] == ["Bini name meaning"]
    assert _awaited(run_search).kwargs["budget"] is ctx.tavily_budget

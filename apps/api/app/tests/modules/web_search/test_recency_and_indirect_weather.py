"""A search for the newest X keeps to recent pages; "I want to know if it will rain" is weather.

"What's the newest iPhone" answered iPhone 17 from 2018 to 2025 articles. The query then
took the year, and "latest iOS version 2026" found the iOS 26 pages over iOS 27
(2026-11-05): the user's words are searched as written, for pages from the last year. "I
want to know if it will rain tomorrow" got "I don't have access to live weather data".
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.modules.web_search import is_geo_query
from app.modules.web_search.patterns import is_weather_request
from app.modules.web_search.recency import asks_for_newest
from app.modules.web_search.tool import WebSearchAdapter
from app.tests.tool_context import tool_context


@pytest.mark.parametrize(
    "text, newest",
    [
        ("what's the newest iphone", True),
        ("tell me about the new tesla model", True),
        ("what is the latest version of django", True),
        ("the most recent pixel phone", True),
        ("I'm new to python, where should I start?", False),
        ("happy new year!", False),
        ("a new way to learn", False),
        ("who won the last world cup", False),
    ],
)
def test_asks_for_newest_reads_recency_words(text: str, newest: bool) -> None:
    assert asks_for_newest(text) is newest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_query, dated",
    [("what's the newest iphone", True), ("how do iphones charge wirelessly", False)],
)
async def test_model_written_search_asks_for_news_on_a_newest_ask(
    user_query: str, dated: bool
) -> None:
    ctx = tool_context(user_query=user_query)
    run_search = AsyncMock(return_value=([], ["q"]))
    with patch("app.modules.web_search.tool.run_cached_search", run_search):
        await WebSearchAdapter(Settings()).invoke({"query": "newest iPhone model"}, ctx)
    sent: Any = run_search.await_args
    assert sent is not None and sent.args[1] == ["newest iPhone model"]
    assert sent.kwargs["dated"] is dated
    assert sent.kwargs["recent"] is True


@pytest.mark.parametrize(
    "text",
    [
        "I want to know if it will rain tomorrow",
        "can you tell me if it will rain tomorrow",
        "do you know whether it's going to snow this weekend",
        "I wonder if it'll storm tonight",
        "will it rain tomorrow",
    ],
)
def test_an_indirect_rain_question_is_local_weather(text: str) -> None:
    assert is_weather_request(text)
    assert is_geo_query(text)


@pytest.mark.parametrize(
    "text",
    [
        "even if it rains we play",
        # Text pasted to proofread: only a message that opens by asking is a forecast ask.
        "fix this: they don't know if it will rain, so we bring coats",
        "I wonder whether it will matter if I skip breakfast",
        "I'm under the weather",
    ],
)
def test_a_rain_clause_is_not_a_forecast(text: str) -> None:
    assert not is_weather_request(text)

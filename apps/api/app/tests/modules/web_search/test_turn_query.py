"""What the tool loop's search sends: the topic, the resolved reference, or the message."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
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


# "Find a coffee shop near me" searched those words: New York cafés came back and
# the reply gave them Nairobi addresses. "Weather here" found Milwaukee.
_NAIROBI = "Westlands, Nairobi, Kenya"


@pytest.mark.parametrize(
    "query, expected",
    [
        ("coffee shops near me", "coffee shops near Westlands, Nairobi, Kenya"),
        ("coffee nearby", "coffee near Westlands, Nairobi, Kenya"),
        ("weather in current location", "weather in Westlands, Nairobi, Kenya"),
        ("weather in my location today", "weather in Westlands, Nairobi, Kenya today"),
        ("current weather", "current weather Westlands, Nairobi, Kenya"),
        # The model already named the place: it is not added twice.
        ("best coffee shops Westlands Nairobi", "best coffee shops Westlands Nairobi"),
    ],
)
def test_anchor_to_location_names_the_place(query: str, expected: str) -> None:
    from app.modules.web_search.query_builders import anchor_to_location

    assert anchor_to_location(query, _NAIROBI) == expected
    assert anchor_to_location(query, None) == query


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_query, location, sent",
    [
        ("find a coffee shop near me", _NAIROBI, "coffee shops near Westlands, Nairobi, Kenya"),
        ("find a coffee shop near me", None, "coffee shops near me"),
        ("tell me about coffee", _NAIROBI, "coffee shops near me"),
    ],
)
async def test_model_written_search_names_the_place(
    user_query: str, location: str | None, sent: str
) -> None:
    from app.modules.web_search.tool import WebSearchAdapter

    ctx = tool_context(user_query=user_query, user_location=location)
    run_search = AsyncMock(return_value=([], [sent]))
    with patch("app.modules.web_search.tool.run_cached_search", run_search):
        await WebSearchAdapter(Settings()).invoke({"query": "coffee shops near me"}, ctx)
    assert _awaited(run_search).args[1] == [sent]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_query, query, sent",
    [
        (
            "where can I park at the Apple Store",
            "parking near the Apple Store",
            "parking near the Apple Store San Francisco, CA, United States",
        ),
        (
            "We're at the Hilton, any restaurants nearby?",
            "restaurants near the Hilton",
            "restaurants near the Hilton San Francisco, CA, United States",
        ),
    ],
)
async def test_a_venue_keeps_the_users_city_in_the_search(
    user_query: str, query: str, sent: str
) -> None:
    """A Hilton or an Apple Store is the one in the user's city (review, 2026-11-09)."""
    from app.modules.web_search.tool import WebSearchAdapter

    ctx = tool_context(user_query=user_query, user_location="San Francisco, CA, United States")
    run_search = AsyncMock(return_value=([], [sent]))
    with patch("app.modules.web_search.tool.run_cached_search", run_search):
        await WebSearchAdapter(Settings()).invoke({"query": query}, ctx)
    assert _awaited(run_search).args[1] == [sent]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_query, query",
    [
        ("What are the best restaurants in Addis Ababa?", "best restaurants Addis Ababa"),
        ("Where should we eat in Rome tonight?", "best restaurants Rome"),
        # "Near me in Bole" says where "me" is: the phone's city is no part of it (review,
        # 2026-11-09; it searched "coffee shops near San Francisco, CA, United States in Bole").
        ("coffee shops near me in Bole", "coffee shops near me in Bole"),
        ("Is there a pharmacy around here? I'm staying in Kazanchis", "pharmacy near me"),
    ],
)
async def test_a_question_that_names_its_place_is_searched_there(
    user_query: str, query: str
) -> None:
    """From San Francisco, "the best restaurants in Addis Ababa" was searched with San
    Francisco added: a time converter and Los Angeles restaurants came back (2026-11-08)."""
    from app.modules.web_search.tool import WebSearchAdapter

    ctx = tool_context(user_query=user_query, user_location="San Francisco, CA, United States")
    run_search = AsyncMock(return_value=([], [query]))
    with patch("app.modules.web_search.tool.run_cached_search", run_search):
        await WebSearchAdapter(Settings()).invoke({"query": query}, ctx)
    assert _awaited(run_search).args[1] == [query]

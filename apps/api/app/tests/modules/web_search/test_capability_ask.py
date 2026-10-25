"""A yes/no question about whether Recall searches asks about the app, not for a search.

Live (2026-10-25): "Show me how u work", then "Can you search the web?". The question
read as a search request that names nothing, so the turn searched the line before it,
and its source chips were song lyrics.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.gateways.mcp import registry
from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.tool_loop import live_denial
from app.modules.chat.tool_loop.reply_calls import ReplyTurn, reply_tools
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.web_search import WebSearchAdapter, asks_whether_it_searches
from app.modules.web_search.command import asks_to_search, search_command
from app.modules.web_search.detection import needs_web_search, web_search_skip
from app.modules.web_search.turn_query import points_back
from app.tests.fakes import isolated_settings

_SETTINGS = isolated_settings(web_search_enabled=True, mcp_tool_loop_enabled=True)
_PRIOR = ["Show me how u work"]
_SEARCH_FIRST = ["did the bears win today"]

CAPABILITY_QUESTIONS = [
    "Can you search the web?",
    "can you search the web",
    "Can you search?",
    "could you search online?",
    "do you search online?",
    "are you able to browse the internet?",
    "can u google things?",
    "do you have web search?",
    "do you have access to the internet?",
    "Do you have the ability to search the web?",
    "can you browse the web?",
    "can you look things up online?",
    "can you look stuff up?",
    "can you access the internet?",
    "can you use google?",
    "can you go online?",
    "are you connected to the internet?",
    "you can search the internet?",
    "can you actually search the web?",
    "Thanks. Can you search the web?",
    "hey, can you search the internet too?",
    "So you can search the web?",
]
SEARCH_REQUESTS = [
    "can you search for the latest news on Tesla?",
    "can you look it up?",
    "can't you look it up? You looked up the weather",
    "search the web for flights to Paris",
    "can you google it",
    "can you search it?",
    "can you search the web for that?",
    "can you search the web for me",
    "would you search the web?",
    "can you search the web now?",
    "can you do a search",
    "can you look up the weather?",
    "search the web",
    "please search online",
    "can you browse for running shoes?",
]


@pytest.mark.parametrize("text", CAPABILITY_QUESTIONS)
def test_a_capability_question_is_no_search(text: str) -> None:
    assert asks_whether_it_searches(text)
    assert search_command(text) is None
    assert not asks_to_search(text)
    assert not points_back(text, _PRIOR)
    for prior in (None, _PRIOR, _SEARCH_FIRST):
        assert web_search_skip(text, prior_user_messages=prior)
        assert not needs_web_search(text, prior_user_messages=prior)


@pytest.mark.parametrize("text", SEARCH_REQUESTS)
def test_a_search_request_still_searches(text: str) -> None:
    assert not asks_whether_it_searches(text)
    assert asks_to_search(text)
    assert needs_web_search(text, prior_user_messages=_SEARCH_FIRST)


@pytest.mark.parametrize(
    "text",
    [
        "do you have a minute?",
        "do you have any news?",
        "can you access my files?",
        "can you look after my cat",
        "can you go out?",
        "can you get the weather?",
        "can you use a search engine to find flights?",
        "what can you do?",
        "",
    ],
)
def test_other_questions_are_not_capability_questions(text: str) -> None:
    assert not asks_whether_it_searches(text)


def _turn(content: str, prior: list[str] | None) -> ReplyTurn:
    return ReplyTurn(
        content=content,
        lightweight=False,
        has_instant_reply=False,
        has_verified_math=False,
        has_search_sources=False,
        prior_user_messages=prior,
        prior_assistant=None,
    )


@pytest.mark.parametrize("text", CAPABILITY_QUESTIONS[:6])
def test_the_reply_is_not_offered_search_on_a_capability_question(text: str) -> None:
    registry.register(WebSearchAdapter(_SETTINGS))
    assert reply_tools(_SETTINGS, _turn(text, _PRIOR)) == []


def _context(content: str) -> StreamContext:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": content}],
        run_title=False,
        user_message_content=content,
        reserved_tokens=100,
        max_output_tokens=100,
    )
    ctx.denial_retry_tools = [{"type": "function"}]
    return ctx


@pytest.mark.parametrize(
    "text, retried",
    [
        ("Can you search the web?", False),
        ("do you have web search?", False),
        ("did the bears win today", True),
    ],
)
def test_a_denial_on_a_capability_question_is_not_retried_with_search(
    text: str, retried: bool
) -> None:
    accum = StreamAccum(parts=["I can't browse the web, sorry."])
    assert live_denial.asks_again(_context(text), [], accum, 0) is retried

"""The reply's model searches the user's earlier chats with ``recall_chats``.

Whether a turn read past chats was a phrase list: "what did i ask you earlier about a
lens" matched nothing and the reply said there was no earlier conversation (2026-11-05).
"""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.gateways.mcp import registry
from app.gateways.mcp.base import ToolContext
from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.stream_paths import run_llm_token_stream
from app.modules.chat.tool_loop.reply_calls import ReplyTurn, offers_search, reply_tools
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.memory.recall_tool import RECALL_TOOL, RecallChatsAdapter
from app.services.prompt_safety import holds_earlier_chats, wrap_earlier_chats
from app.tests.fakes import isolated_settings, redis_mock
from app.tests.modules.chat.chat_test_support import turn_deps

_SETTINGS = isolated_settings(
    mcp_tool_loop_enabled=True, chat_history_rag_enabled=True, web_search_enabled=False
)
_SNIPPETS = wrap_earlier_chats("[1] (Nov 4) User: where is the image of a lens 30 cm away?")
_RETRIEVE = "app.modules.conversation.history_rag.retrieve_for_prompt"
_RECALL_CALL = {
    "id": "call_1",
    "type": "function",
    "function": {"name": RECALL_TOOL, "arguments": '{"query": "lens question"}'},
}


@pytest.fixture
def recall() -> dict[str, Any]:
    """The tool as production registers it at startup."""
    adapter = RecallChatsAdapter(_SETTINGS)
    registry.register(adapter)
    return adapter.to_openai_tool()


def _turn(content: str, **fields: Any) -> ReplyTurn:
    values: dict[str, Any] = {
        "content": content,
        "lightweight": False,
        "has_instant_reply": False,
        "has_verified_math": False,
        "has_search_sources": False,
        "prior_user_messages": None,
        "prior_assistant": None,
        "may_recall": True,
        **fields,
    }
    return ReplyTurn(**values)


def _ctx(user: Any) -> ToolContext:
    return ToolContext(
        user=user,
        redis=None,
        chat_id=uuid4(),
        user_timezone=None,
        user_query="what did i ask you earlier about a lens",
        tavily_budget=SimpleNamespace(),  # recall never searches the web
    )


def test_the_tool_is_offered_on_an_everyday_turn(recall: dict[str, Any]) -> None:
    tools = reply_tools(_SETTINGS, _turn("what did i ask you earlier about a lens"))
    assert tools == [recall]
    assert not offers_search(tools)


@pytest.mark.parametrize(
    "fields",
    [
        {"may_recall": False},  # memory off, or the prompt already holds past snippets
        {"lightweight": True},
        {"has_instant_reply": True},
        {"has_verified_math": True},
    ],
)
def test_the_tool_is_not_offered_when_the_turn_has_no_use_for_it(
    recall: dict[str, Any], fields: dict[str, Any]
) -> None:
    assert reply_tools(_SETTINGS, _turn("what was my lens question before", **fields)) == []


def test_the_tool_is_off_with_chat_history_recall(recall: dict[str, Any]) -> None:
    off = isolated_settings(mcp_tool_loop_enabled=True, chat_history_rag_enabled=False)
    assert reply_tools(off, _turn("what did i ask earlier")) == []


def test_a_prompt_that_already_holds_past_snippets_is_seen() -> None:
    assert holds_earlier_chats([{"role": "system", "content": f"Rules.\n\n{_SNIPPETS}"}])
    assert not holds_earlier_chats([{"role": "user", "content": _SNIPPETS}])
    assert not holds_earlier_chats([{"role": "system", "content": "Rules."}])


async def test_invoke_returns_the_snippets_and_reuses_them() -> None:
    user = SimpleNamespace(id=uuid4(), memory_enabled=True)
    ctx = _ctx(user)
    with patch(_RETRIEVE, AsyncMock(return_value=_SNIPPETS)) as retrieve:
        first = await RecallChatsAdapter(_SETTINGS).invoke({"query": "lens question"}, ctx)
        again = await RecallChatsAdapter(_SETTINGS).invoke({"query": "lens"}, ctx)
    assert first.content == _SNIPPETS
    assert again is first
    # Earlier chats only: this chat's own lines are already in the prompt.
    retrieve.assert_awaited_once_with(
        _SETTINGS, user_id=user.id, query="lens question", exclude_chat_id=ctx.chat_id
    )


async def test_invoke_says_when_nothing_matches_or_memory_is_off() -> None:
    with patch(_RETRIEVE, AsyncMock(return_value="")):
        none = await RecallChatsAdapter(_SETTINGS).invoke(
            {"query": "x"}, _ctx(SimpleNamespace(id=uuid4(), memory_enabled=True))
        )
    off = await RecallChatsAdapter(_SETTINGS).invoke(
        {"query": "x"}, _ctx(SimpleNamespace(id=uuid4(), memory_enabled=False))
    )
    assert "couldn't find it" in none.content
    assert "Memory is off" in off.content


def _model(*calls: tuple[list[str], list[dict[str, Any]]]) -> tuple[Any, list[dict[str, Any]]]:
    seen: list[dict[str, Any]] = []
    plays = iter(calls)

    async def stream_chat_completion(**kwargs: Any) -> AsyncIterator[str]:
        seen.append({**kwargs, "messages": list(kwargs["messages"])})
        tokens, tool_calls = next(plays)
        for token in tokens:
            yield token
        kwargs["tool_calls"].extend(tool_calls)
        kwargs["stream_meta"]["model_alias"] = kwargs["model_alias"]
        if tool_calls:
            kwargs["stream_meta"]["finish_reason"] = "tool_calls"

    return SimpleNamespace(stream_chat_completion=stream_chat_completion), seen


def _stream_ctx(content: str, tools: list[dict[str, Any]]) -> StreamContext:
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
    ctx.user = SimpleNamespace(id=ctx.user_id, memory_enabled=True, locale=None)  # type: ignore[assignment]
    ctx.reply_tools = tools
    return ctx


async def _reply(ctx: StreamContext, llm: Any, accum: StreamAccum) -> None:
    async for _token in run_llm_token_stream(
        turn_deps(llm=llm),
        redis_mock(),
        _SETTINGS,
        ctx,
        usage={},
        outcome=None,
        on_reasoning=None,
        accum=accum,
        should_cancel=None,
    ):
        pass


async def test_a_recall_question_searches_then_answers_from_the_snippets(
    recall: dict[str, Any],
) -> None:
    answer = "Earlier you asked where a lens forms the image of an object 30 cm away."
    llm, seen = _model((["Let me look."], [_RECALL_CALL]), ([answer], []))
    accum = StreamAccum()
    with patch(_RETRIEVE, AsyncMock(return_value=_SNIPPETS)) as retrieve:
        await _reply(_stream_ctx("what did i ask you earlier about a lens", [recall]), llm, accum)
    retrieve.assert_awaited_once()
    # The answering call reads the snippets as the tool's message; the text before the
    # call held the place and gives way to the answer.
    assert seen[1]["messages"][-1] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": _SNIPPETS,
    }
    assert accum.reply_text() == answer


async def test_a_question_with_no_past_to_recall_never_searches(recall: dict[str, Any]) -> None:
    llm, seen = _model((["A lens bends light to form an image."], []))
    with patch(_RETRIEVE, AsyncMock()) as retrieve:
        await _reply(_stream_ctx("how does a lens work", [recall]), llm, StreamAccum())
    retrieve.assert_not_awaited()
    assert len(seen) == 1

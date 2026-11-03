"""What a reply's call wrote before its search is not the reply: the answer after it is.

Live (2026-11-03), "is he still friends w elon or nah": the first call wrote "This is a
current-events question, and their relationship has changed several times, so I'll check
the latest reporting before answering.", searched, and the saved reply opened with that
narration. "Purecart" before it: "Thanks, Dev. I'll look into Purecart now." stayed above
an answer that greeted again. The text before a search had no results to go on; it holds
the place while the search runs, and done carries the answer that replaces it.
"""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.gateways.mcp import registry
from app.gateways.web_search_gateway import WebSearchHit
from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.stream_paths import run_llm_token_stream
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.web_search import WebSearchAdapter
from app.tests.fakes import isolated_settings, redis_mock
from app.tests.modules.chat.chat_test_support import turn_deps

_SETTINGS = isolated_settings(web_search_enabled=True, mcp_tool_loop_enabled=True)
_HIT = WebSearchHit(title="Purecart", url="https://purecart.example", snippet="A shop.")
_SEARCH_CALL = {
    "id": "call_1",
    "type": "function",
    "function": {"name": "web_search", "arguments": '{"query": "Purecart"}'},
}
_BEFORE = "This is a current-events question, so I'll check the latest reporting."
_ANSWER = "The search didn't return any information about Purecart itself."


@pytest.fixture
def web_search_tool() -> dict[str, Any]:
    adapter = WebSearchAdapter(_SETTINGS)
    registry.register(adapter)
    return adapter.to_openai_tool()


def _context(content: str) -> StreamContext:
    return StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": content}],
        run_title=False,
        user_message_content=content,
        reserved_tokens=100,
        max_output_tokens=100,
    )


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

    return SimpleNamespace(stream_chat_completion=stream_chat_completion), seen


async def _reply(ctx: StreamContext, llm: Any, accum: StreamAccum) -> str:
    with patch(
        "app.modules.web_search.tool.run_cached_search", AsyncMock(return_value=([_HIT], ["q"]))
    ):
        tokens = [
            token
            async for token in run_llm_token_stream(
                turn_deps(llm=llm),
                redis_mock(),
                _SETTINGS,
                ctx,
                usage={},
                outcome=None,
                on_reasoning=None,
                accum=accum,
                should_cancel=None,
            )
        ]
    return "".join(tokens)


@pytest.mark.asyncio
async def test_the_text_before_a_search_is_not_saved(web_search_tool: dict[str, Any]) -> None:
    ctx = _context("Purecart")
    ctx.reply_tools = [web_search_tool]
    llm, seen = _model(([_BEFORE], [_SEARCH_CALL]), ([_ANSWER], []))
    accum = StreamAccum()
    drawn = await _reply(ctx, llm, accum)

    # The phone drew the placeholder while the search ran, then the answer.
    assert drawn == f"{_BEFORE}{_ANSWER}"
    # The saved reply is the answer alone, and done replaces what was drawn.
    assert accum.reply_text() == _ANSWER
    assert accum.retracted == _BEFORE
    # The answering call still reads the first call's text as its own turn.
    assert seen[1]["messages"][-2]["content"] == _BEFORE


@pytest.mark.asyncio
async def test_a_search_with_no_text_before_keeps_the_whole_answer(
    web_search_tool: dict[str, Any],
) -> None:
    ctx = _context("Purecart")
    ctx.reply_tools = [web_search_tool]
    llm, _seen = _model(([], [_SEARCH_CALL]), (["Thanks, Dev. ", _ANSWER], []))
    accum = StreamAccum()
    assert await _reply(ctx, llm, accum) == f"Thanks, Dev. {_ANSWER}"
    assert accum.reply_text() == f"Thanks, Dev. {_ANSWER}"


@pytest.mark.asyncio
async def test_a_reply_that_never_searches_keeps_its_text(web_search_tool: dict[str, Any]) -> None:
    ctx = _context("Purecart")
    ctx.reply_tools = [web_search_tool]
    llm, _seen = _model(([_ANSWER], []))
    accum = StreamAccum()
    assert await _reply(ctx, llm, accum) == _ANSWER
    assert accum.reply_text() == _ANSWER
    assert not accum.retracted

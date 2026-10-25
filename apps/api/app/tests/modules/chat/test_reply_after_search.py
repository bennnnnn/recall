"""The answer after a reply's search never opens by repeating the text before it.

"Purecart" (live chat): the first call wrote "Thanks, Dev. I'll look into Purecart now.",
searched, and the answer opened "Thanks, Dev." again.
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
from app.modules.chat.tool_loop.repeat_filter import RepeatFilter
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
_BEFORE = "Thanks, Dev. I'll look into Purecart now."
_ANSWER = "The search didn't return any information about Purecart itself."


def _filtered(before: str, tokens: list[str]) -> str:
    repeats = RepeatFilter(before)
    return "".join(repeats.feed(token) for token in tokens) + repeats.flush()


@pytest.mark.parametrize(
    "tokens, kept",
    [
        # Live: the greeting again, then the answer.
        (
            ["Thanks, ", "Dev. ", "The search didn't ", "return anything."],
            "The search didn't return anything.",
        ),
        # The whole opening again, in one token or many.
        ([f"{_BEFORE} {_ANSWER}"], _ANSWER),
        (
            [
                "Thanks",
                ",",
                " Dev",
                ".",
                " I'll",
                " look",
                " into",
                " Purecart",
                " now",
                ".",
                "\n\n",
                "Purecart sells",
            ],
            "Purecart sells",
        ),
        # Case, bold and punctuation do not make a sentence new.
        (["**Thanks Dev!** ", "Purecart is a shop."], "Purecart is a shop."),
        (["thanks, dev.\n", "Purecart is a shop."], "Purecart is a shop."),
        # An answer that starts new goes out as written.
        (["Purecart ", "is a shop."], "Purecart is a shop."),
        (
            ["Thanks for waiting. ", "Purecart is a shop."],
            "Thanks for waiting. Purecart is a shop.",
        ),
        (["Thanks, Devon. ", "Purecart is a shop."], "Thanks, Devon. Purecart is a shop."),
        # Only the opening: a sentence said again later is the answer's own.
        (["Purecart is a shop. ", "Thanks, Dev."], "Purecart is a shop. Thanks, Dev."),
        # A short answer that is still the start of a sentence said before.
        (["Thanks"], "Thanks"),
        # An answer that only repeats leaves nothing to add.
        (["Thanks, Dev."], ""),
    ],
)
def test_repeat_filter_drops_an_opening_said_before(tokens: list[str], kept: str) -> None:
    assert _filtered(_BEFORE, tokens) == kept


@pytest.mark.parametrize("before", ["", "   ", "**"])
def test_repeat_filter_passes_everything_after_no_text(before: str) -> None:
    assert _filtered(before, ["Thanks, Dev. ", "Hi."]) == "Thanks, Dev. Hi."


def test_repeat_filter_lets_a_new_answer_through_at_its_first_word() -> None:
    repeats = RepeatFilter(_BEFORE)
    assert repeats.feed("Purecart") == "Purecart"
    assert repeats.feed(" is") == " is"


def test_repeat_filter_holds_only_while_the_opening_may_repeat() -> None:
    repeats = RepeatFilter(_BEFORE)
    assert repeats.feed("Thanks,") == ""
    assert repeats.feed(" Dev.") == ""
    assert repeats.feed(" The") == "The"


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
async def test_the_answer_after_a_search_does_not_greet_again(
    web_search_tool: dict[str, Any],
) -> None:
    ctx = _context("Purecart")
    ctx.reply_tools = [web_search_tool]
    llm, seen = _model(
        (["Thanks, Dev. ", "I'll look into Purecart now."], [_SEARCH_CALL]),
        (["Thanks, Dev. ", _ANSWER], []),
    )
    accum = StreamAccum()
    drawn = await _reply(ctx, llm, accum)

    assert drawn == f"{_BEFORE}\n\n{_ANSWER}"
    # The saved reply is the text the phone drew: nothing to replace on done.
    assert accum.reply_text() == drawn
    assert "".join(accum.parts) == drawn
    # The answering call still reads the first call's text as its own turn.
    assert seen[1]["messages"][-2]["content"] == _BEFORE


@pytest.mark.asyncio
async def test_an_answer_that_starts_new_streams_as_written(
    web_search_tool: dict[str, Any],
) -> None:
    ctx = _context("Purecart")
    ctx.reply_tools = [web_search_tool]
    llm, _seen = _model(([_BEFORE], [_SEARCH_CALL]), ([_ANSWER], []))
    accum = StreamAccum()
    assert await _reply(ctx, llm, accum) == f"{_BEFORE}\n\n{_ANSWER}"


@pytest.mark.asyncio
async def test_a_search_with_no_text_before_keeps_the_whole_answer(
    web_search_tool: dict[str, Any],
) -> None:
    ctx = _context("Purecart")
    ctx.reply_tools = [web_search_tool]
    llm, _seen = _model(([], [_SEARCH_CALL]), (["Thanks, Dev. ", _ANSWER], []))
    accum = StreamAccum()
    assert await _reply(ctx, llm, accum) == f"Thanks, Dev. {_ANSWER}"

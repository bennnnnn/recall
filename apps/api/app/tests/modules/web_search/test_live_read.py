"""A model reads whether a message's answer depends on facts that change (``live_read``)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.gateways.litellm_gateway import _call_kwargs
from app.gateways.stream_tool_calls import ToolOffer
from app.models import model_catalog
from app.modules.web_search import live_read
from app.tests.fakes import isolated_settings

_SETTINGS = isolated_settings(web_search_enabled=True, mcp_tool_loop_enabled=True)
_STRUCTURED = "app.gateways.structured_completion.complete_structured"


@pytest.mark.parametrize("live", [True, False])
@pytest.mark.asyncio
async def test_the_read_is_the_models_answer(live: bool) -> None:
    ask = AsyncMock(return_value=live_read.LiveRead(live=live))
    with patch(_STRUCTURED, ask):
        read = await live_read.read_live(_SETTINGS, "who won the last world cup", earlier=None)
    assert read is not None and read.live is live
    assert ask.await_args is not None
    messages = ask.await_args.kwargs["messages"]
    assert messages[0]["role"] == "system" and "Today is" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "who won the last world cup"}


@pytest.mark.asyncio
async def test_a_follow_up_is_read_with_the_reply_before_it() -> None:
    ask = AsyncMock(return_value=live_read.LiveRead(live=True))
    with patch(_STRUCTURED, ask):
        await live_read.read_live(
            _SETTINGS, "and who won in ohio?", earlier="Mike Rogers won Michigan."
        )
    assert ask.await_args is not None
    roles = [message["role"] for message in ask.await_args.kwargs["messages"]]
    assert roles == ["system", "assistant", "user"]


@pytest.mark.parametrize("answer", [None, RuntimeError("provider down")])
@pytest.mark.asyncio
async def test_no_read_is_no_answer(answer: Any) -> None:
    ask = (
        AsyncMock(side_effect=answer)
        if isinstance(answer, Exception)
        else AsyncMock(return_value=None)
    )
    with patch(_STRUCTURED, ask):
        assert await live_read.read_live(_SETTINGS, "hi", earlier=None) is None


@pytest.mark.asyncio
async def test_an_empty_message_is_never_read() -> None:
    ask = AsyncMock()
    with patch(_STRUCTURED, ask):
        assert await live_read.read_live(_SETTINGS, "  ", earlier=None) is None
    ask.assert_not_awaited()


@pytest.mark.parametrize(
    "off",
    [
        {"live_read_enabled": False},
        {"web_search_enabled": False},
        {"reply_search_tool_enabled": False},
        {"mcp_tool_loop_enabled": False},
    ],
)
def test_no_read_starts_while_search_is_off(off: dict[str, bool]) -> None:
    settings = isolated_settings(
        **{"web_search_enabled": True, "mcp_tool_loop_enabled": True, **off}
    )
    assert live_read.start_live_read(settings, "who won the last world cup", earlier=None) is None


@pytest.mark.asyncio
async def test_a_slow_read_counts_as_none() -> None:
    async def slow() -> live_read.LiveRead | None:
        await asyncio.sleep(5)
        return live_read.LiveRead(live=True)

    settings = isolated_settings(live_read_wait_seconds=0.01)
    assert await live_read.live_read_result(asyncio.ensure_future(slow()), settings) is None
    assert await live_read.live_read_result(None, settings) is None


@pytest.mark.asyncio
async def test_only_a_live_read_is_handed_on() -> None:
    async def read(live: bool) -> live_read.LiveRead | None:
        return live_read.LiveRead(live=live, query="world cup winner 2026" if live else "")

    found = await live_read.live_read_result(asyncio.ensure_future(read(True)), _SETTINGS)
    assert found is not None and found.query == "world cup winner 2026"
    assert await live_read.live_read_result(asyncio.ensure_future(read(False)), _SETTINGS) is None


def _tools(*names: str) -> list[dict[str, Any]]:
    return [{"type": "function", "function": {"name": name, "parameters": {}}} for name in names]


@pytest.mark.parametrize(
    ("require", "choice"),
    [
        ("web_search", {"type": "function", "function": {"name": "web_search"}}),
        (None, "auto"),
        # A tool the call does not carry is never required of it.
        ("generate_image", "auto"),
    ],
)
def test_a_required_tool_is_named_to_the_provider(require: str | None, choice: Any) -> None:
    kwargs, calls = _call_kwargs(
        isolated_settings(openrouter_api_key="sk-or-test"),
        model_catalog.get("qwen-3.7-flash"),
        False,
        ToolOffer(_tools("web_search", "recall_chats"), require),
    )
    assert calls is not None
    assert kwargs["tool_choice"] == choice

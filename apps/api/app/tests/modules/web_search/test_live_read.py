"""A model reads whether a message's answer depends on facts that change (``live_read``)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
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


@pytest.fixture(autouse=True)
def under_the_spend_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.redis.get_redis_client", lambda: object())
    monkeypatch.setattr("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False))


@pytest.mark.asyncio
async def test_no_read_past_the_spend_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.quota.global_spend_exceeded", AsyncMock(return_value=True))
    ask = AsyncMock()
    with patch(_STRUCTURED, ask):
        assert (
            await live_read.read_live(_SETTINGS, "who won the last world cup", earlier=[]) is None
        )
    ask.assert_not_awaited()


@pytest.mark.parametrize("live", [True, False])
@pytest.mark.asyncio
async def test_the_read_is_the_models_answer(live: bool) -> None:
    ask = AsyncMock(return_value=live_read.LiveRead(live=live))
    with patch(_STRUCTURED, ask):
        read = await live_read.read_live(_SETTINGS, "who won the last world cup", earlier=[])
    assert read is not None and read.live is live
    assert ask.await_args is not None
    messages = ask.await_args.kwargs["messages"]
    assert messages[0]["role"] == "system" and "Today is" in messages[0]["content"]
    assert messages[-1] == {
        "role": "user",
        "content": "The user's last message: who won the last world cup",
    }


@pytest.mark.asyncio
async def test_a_follow_up_is_read_with_the_turns_before_it_quoted() -> None:
    """After a chat about a MacBook Air's battery, "How much" was searched as an iPhone
    battery's cost when the read saw one reply; and given the chat as turns, a model
    answered the user instead of judging the message."""
    ask = AsyncMock(return_value=live_read.LiveRead(live=True))
    recent = [
        SimpleNamespace(role="user", content="Macbook air"),
        SimpleNamespace(role="assistant", content="A MacBook Air has no fan."),
        SimpleNamespace(role="user", content="Can I replace the battery myself?"),
        SimpleNamespace(role="assistant", content="You can, but it's fiddly."),
    ]
    with patch(_STRUCTURED, ask):
        await live_read.read_live(_SETTINGS, "How much", earlier=live_read.earlier_turns(recent))
    assert ask.await_args is not None
    messages = ask.await_args.kwargs["messages"]
    assert [message["role"] for message in messages] == ["system", "user"]
    assert messages[1]["content"] == (
        "Earlier turns:\nUser: Macbook air\nAssistant: A MacBook Air has no fan.\n"
        "User: Can I replace the battery myself?\nAssistant: You can, but it's fiddly.\n\n"
        "The user's last message: How much"
    )


def test_the_read_sees_the_last_two_exchanges_each_cut_short() -> None:
    recent = [
        SimpleNamespace(role="user", content="first"),
        SimpleNamespace(role="assistant", content="first reply"),
        SimpleNamespace(role="system", content="a note"),
        SimpleNamespace(role="user", content="second"),
        SimpleNamespace(role="assistant", content="x" * 1000),
        SimpleNamespace(role="user", content="third"),
        SimpleNamespace(role="assistant", content="   "),
        SimpleNamespace(role="assistant", content="third reply"),
    ]
    assert live_read.earlier_turns(recent) == [
        ("user", "second"),
        ("assistant", "x" * 400),
        ("user", "third"),
        ("assistant", "third reply"),
    ]
    assert live_read.earlier_turns(None) == []


@pytest.mark.parametrize(
    "kind",
    [
        # 2026-11-09, one chat: each of these was searched before a reply that needed none.
        "whether to repair, replace or buy something",
        "steps, settings and checks on a phone",
        "where the user is",
        "getting from the user to a place the conversation already named",
        # And what searches whatever the topic: the read's ``asked``.
        "asked is true when the user's last message asks you to search the web",
        # Never the user's own words sent to the web: their chats and memory are here.
        "a search of their own chats, memory, notes, to-dos or files is not asked",
        # Whether to think first (``model_routing.thinking``), and what never needs it.
        "think is true when a careful answer must be reasoned out before it is written",
        "a single equation or expression to solve, differentiate or simplify",
    ],
)
def test_the_reads_instructions_name_each_kind(kind: str) -> None:
    assert kind in live_read._messages("hi", [])[0]["content"]


@pytest.mark.parametrize(
    ("live", "asked", "searches"),
    [(True, False, True), (False, True, True), (False, False, False)],
)
def test_a_live_answer_or_an_asked_search_searches(live: bool, asked: bool, searches: bool) -> None:
    assert live_read.LiveRead(live=live, asked=asked).searches is searches


@pytest.mark.parametrize("answer", [None, RuntimeError("provider down")])
@pytest.mark.asyncio
async def test_no_read_is_no_answer(answer: Any) -> None:
    ask = (
        AsyncMock(side_effect=answer)
        if isinstance(answer, Exception)
        else AsyncMock(return_value=None)
    )
    with patch(_STRUCTURED, ask):
        assert await live_read.read_live(_SETTINGS, "hi", earlier=[]) is None


@pytest.mark.asyncio
async def test_an_empty_message_is_never_read() -> None:
    ask = AsyncMock()
    with patch(_STRUCTURED, ask):
        assert await live_read.read_live(_SETTINGS, "  ", earlier=[]) is None
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
    assert live_read.start_live_read(settings, "who won the last world cup", recent=None) is None


@pytest.mark.asyncio
async def test_a_slow_read_counts_as_none() -> None:
    async def slow() -> live_read.LiveRead | None:
        await asyncio.sleep(5)
        return live_read.LiveRead(live=True)

    settings = isolated_settings(live_read_wait_seconds=0.01)
    assert await live_read.live_read_result(asyncio.ensure_future(slow()), settings) is None
    assert await live_read.live_read_result(None, settings) is None


@pytest.mark.parametrize("live", [True, False])
@pytest.mark.asyncio
async def test_the_reads_answer_is_handed_on_live_or_not(live: bool) -> None:
    """A settled answer is handed on too: the reply is told it (``reply_calls``)."""

    async def read() -> live_read.LiveRead | None:
        return live_read.LiveRead(live=live, query="world cup winner" if live else "")

    found = await live_read.live_read_result(asyncio.ensure_future(read()), _SETTINGS)
    assert found is not None and found.live is live


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

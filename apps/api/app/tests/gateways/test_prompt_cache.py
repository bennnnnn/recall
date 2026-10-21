"""Prompt caching at the gateway: the stable system message is marked only for a model
that caches a marked prefix."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from litellm.llms.openrouter.chat.transformation import OpenrouterConfig

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.gateways.prompt_cache import EPHEMERAL, with_cache_breakpoint
from app.models import model_catalog

_PROMPT = [
    {"role": "system", "content": "Stable instructions"},
    {"role": "system", "content": "Current local time: 9:00 AM"},
    {"role": "user", "content": "hi"},
]


def test_only_a_model_that_needs_the_mark_gets_it() -> None:
    marked = with_cache_breakpoint(_PROMPT, model_catalog.get("free-chat"))
    assert marked[0] == {
        "role": "system",
        "content": [{"type": "text", "text": "Stable instructions", "cache_control": EPHEMERAL}],
    }
    # The turn's own context and the user turn go as they were, after the mark.
    assert marked[1:] == _PROMPT[1:]
    # A provider that reuses an identical prefix by itself gets the prompt untouched.
    for alias in ("qwen-3.7-flash", "smart-chat", "glm-5.2", "gpt-6-luna"):
        assert with_cache_breakpoint(_PROMPT, model_catalog.get(alias)) is _PROMPT


def test_the_prompt_itself_is_never_changed() -> None:
    prompt = [dict(message) for message in _PROMPT]
    with_cache_breakpoint(prompt, model_catalog.get("free-chat"))
    assert prompt == _PROMPT


@pytest.mark.parametrize(
    "messages",
    [
        # A lone system prompt holds the turn's own text: a mark would be a write per turn.
        [{"role": "system", "content": "everything"}, {"role": "user", "content": "hi"}],
        [{"role": "user", "content": "hi"}],
        [],
        # Already in parts (a caller's own format) or empty: left alone.
        [
            {"role": "system", "content": [{"type": "text", "text": "x"}]},
            {"role": "system", "content": "turn"},
        ],
        [{"role": "system", "content": ""}, {"role": "system", "content": "turn"}],
    ],
)
def test_no_mark_without_a_stable_message_before_the_turns(messages: list[dict[str, Any]]) -> None:
    assert with_cache_breakpoint(messages, model_catalog.get("free-chat")) is messages


def test_litellm_forwards_the_mark_to_openrouter_for_claude() -> None:
    route = model_catalog.get("free-chat")
    body = OpenrouterConfig().transform_request(
        model=route.model.removeprefix("openrouter/"),
        messages=with_cache_breakpoint(_PROMPT, route),  # type: ignore[arg-type]
        optional_params={},
        litellm_params={},
        headers={},
    )
    assert body["messages"][0]["content"][0]["cache_control"] == EPHEMERAL


class _OneChunk:
    def __init__(self, usage: Any = None) -> None:
        self.done = False
        self.usage = usage

    def __aiter__(self) -> _OneChunk:
        return self

    async def __anext__(self) -> Any:
        if self.done:
            raise StopAsyncIteration
        self.done = True
        delta = SimpleNamespace(content="Hello")
        return SimpleNamespace(
            choices=[SimpleNamespace(delta=delta, finish_reason="stop")], usage=self.usage
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("alias, marked", [("free-chat", True), ("qwen-3.7-flash", False)])
async def test_the_stream_sends_the_mark_for_its_route(alias: str, marked: bool) -> None:
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    acompletion = AsyncMock(return_value=_OneChunk())
    with patch("app.gateways.litellm_gateway.acompletion", acompletion):
        tokens = [
            token
            async for token in litellm_gateway._stream_chat_once(
                settings=settings, model_alias=alias, messages=_PROMPT, max_tokens=10
            )
        ]
    assert "".join(tokens) == "Hello"
    assert acompletion.await_args is not None
    sent = acompletion.await_args.kwargs["messages"]
    assert isinstance(sent[0]["content"], list) is marked
    assert sent[1:] == _PROMPT[1:]

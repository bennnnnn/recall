"""A reply's thinking gets its own tokens and a ceiling; thinking that runs out of either
goes on without thinking (``gateways.stream_thinking``, 2026-11-18: a 20-part question
thought to the output cap on three models and showed nothing for 143 s)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.gateways.reasoning import reasoning_body
from app.gateways.stream_signals import THOUGHT_OUT, StreamAttempt
from app.gateways.stream_thinking import AttemptThinking, ThinkingPlan
from app.models import model_catalog

_BASE = 1000
_BUDGET = 4096


def _settings(**overrides: Any) -> Settings:
    fields: dict[str, Any] = {
        "mock_llm_enabled": False,
        "openrouter_api_key": "sk-or-test",
        "chat_reasoning_budget_tokens": _BUDGET,
    }
    return Settings(**(fields | overrides))


def _chunk(*, content: str = "", reasoning: str = "", finish: str | None = None) -> MagicMock:
    delta = MagicMock()
    delta.content = content
    delta.reasoning_content = reasoning
    delta.tool_calls = None
    choice = MagicMock()
    choice.delta = delta
    choice.finish_reason = finish
    chunk = MagicMock()
    chunk.choices = [choice]
    chunk.usage = None
    return chunk


class _Stream:
    """A provider stream: ``thoughts`` reasoning chunks, then ``answer`` (or a length end)."""

    def __init__(self, *, thoughts: int, answer: str | None, endless: bool = False) -> None:
        self._chunks = [_chunk(reasoning="thinking ") for _ in range(thoughts)]
        if answer is not None:
            self._chunks.append(_chunk(content=answer, finish="stop"))
        elif not endless:
            self._chunks.append(_chunk(finish="length"))
        self._endless = endless

    def __aiter__(self) -> _Stream:
        return self

    async def __anext__(self) -> MagicMock:
        await asyncio.sleep(0.01)
        if self._chunks:
            return self._chunks.pop(0)
        if self._endless:
            return _chunk(reasoning="still thinking ")
        raise StopAsyncIteration


class _Provider:
    """``acompletion`` stand-in: one stream per call, each call's arguments kept."""

    def __init__(self, *streams: _Stream) -> None:
        self._streams = list(streams)
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> _Stream:
        self.calls.append(kwargs)
        return self._streams.pop(0)


def _reasoning(call: dict[str, Any]) -> dict[str, Any] | None:
    return (call.get("extra_body") or {}).get("reasoning")


async def _reply(
    settings: Settings,
    provider: _Provider,
    alias: str,
    fallbacks: list[str],
    *,
    thinking: bool | str = "hard",
    attempts: list[StreamAttempt] | None = None,
) -> str:
    with patch.object(litellm_gateway, "acompletion", provider):
        return "".join(
            [
                token
                async for token in litellm_gateway.stream_chat_completion(
                    settings=settings,
                    model_alias=alias,
                    messages=[{"role": "user", "content": "a long question"}],
                    max_tokens=_BASE,
                    fallback_aliases=fallbacks,
                    thinking=thinking,
                    attempts=attempts,
                )
            ]
        )


def test_reasoning_body_caps_thinking_in_tokens_only_where_the_model_takes_a_cap() -> None:
    qwen = model_catalog.get("qwen-3.8-flash")
    deepseek = model_catalog.get("smart-chat")
    assert reasoning_body(qwen, "hard", budget=_BUDGET) == {"max_tokens": _BUDGET}
    assert reasoning_body(qwen, "hard") == {"effort": qwen.thinking_on}
    assert reasoning_body(qwen, False, budget=_BUDGET) == {"effort": "none"}
    assert reasoning_body(deepseek, "hard", budget=_BUDGET) == {"effort": deepseek.thinking_on}


@pytest.mark.parametrize(
    "alias, level, budget",
    [
        ("smart-chat", "hard", _BUDGET),
        ("smart-chat", "deep", _BUDGET),
        ("smart-chat", False, 0),
        # GLM always thinks: its "off" level is an effort, so it is held too.
        ("glm-5.3-flash", False, _BUDGET),
        ("qwen-3.7-flash", "hard", 0),
    ],
)
def test_thinking_plan_gives_a_budget_and_ceiling_only_to_an_attempt_that_thinks(
    alias: str, level: bool | str, budget: int
) -> None:
    think = ThinkingPlan(_settings(), level).attempt(model_catalog.get(alias), has_next=True)
    assert think.budget == budget
    assert (think.answer_within is not None) == (budget > 0)


def test_the_last_model_that_cannot_think_less_is_not_held() -> None:
    """GLM as the last model at its lowest level: holding it would only end the turn."""
    glm = model_catalog.get("glm-5.3-flash")
    think = ThinkingPlan(_settings(), False).attempt(glm, has_next=False)
    assert think.budget == _BUDGET
    assert think.answer_within is None and think.reasoning_chars is None
    # DeepSeek can think less, so it is held as the last model too.
    deepseek = ThinkingPlan(_settings(), "hard").attempt(
        model_catalog.get("smart-chat"), has_next=False
    )
    assert deepseek.answer_within is not None and deepseek.reasoning_chars


@pytest.mark.asyncio
async def test_thinking_that_used_the_tokens_goes_on_without_thinking() -> None:
    """DeepSeek thought to the length limit: Qwen answers with thinking off and the reply's
    own cap, and the empty try is no mark against DeepSeek's health."""
    provider = _Provider(_Stream(thoughts=3, answer=None), _Stream(thoughts=0, answer="Part 1"))
    attempts: list[StreamAttempt] = []
    text = await _reply(_settings(), provider, "smart-chat", ["qwen-3.8-flash"], attempts=attempts)
    assert text == "Part 1"
    first, second = provider.calls
    assert first["max_tokens"] == _BASE + _BUDGET
    assert _reasoning(first) == {"effort": "low"}
    assert second["max_tokens"] == _BASE
    assert _reasoning(second) == {"effort": "none"}
    assert attempts[0].cause == THOUGHT_OUT
    assert not attempts[0].model_failed


@pytest.mark.asyncio
async def test_thinking_past_the_ceiling_with_no_answer_gives_way() -> None:
    """Reasoning streams, so no first-reply cap fires: the ceiling ends it."""
    provider = _Provider(
        _Stream(thoughts=0, answer=None, endless=True), _Stream(thoughts=0, answer="Part 1")
    )
    settings = _settings(chat_stream_thought_ceiling_seconds=0.2)
    text = await _reply(settings, provider, "smart-chat", ["qwen-3.8-flash"])
    assert text == "Part 1"
    assert _reasoning(provider.calls[1]) == {"effort": "none"}


@pytest.mark.asyncio
async def test_reasoning_past_the_budget_gives_way_on_a_model_that_takes_no_cap() -> None:
    """DeepSeek lists efforts only: its streamed reasoning is held to the budget."""
    provider = _Provider(
        _Stream(thoughts=0, answer=None, endless=True), _Stream(thoughts=0, answer="Part 1")
    )
    # 10 tokens is about 30 characters: four chunks of "thinking " run past it.
    settings = _settings(chat_reasoning_budget_tokens=10)
    attempts: list[StreamAttempt] = []
    text = await _reply(settings, provider, "smart-chat", ["qwen-3.8-flash"], attempts=attempts)
    assert text == "Part 1"
    assert attempts[0].cause == THOUGHT_OUT
    assert _reasoning(provider.calls[1]) == {"effort": "none"}


class _StalledThought(_Stream):
    """Reasoning starts, then the provider goes silent."""

    def __init__(self) -> None:
        super().__init__(thoughts=1, answer=None, endless=True)

    async def __anext__(self) -> MagicMock:
        if self._chunks:
            return self._chunks.pop(0)
        await asyncio.sleep(30)
        raise StopAsyncIteration


@pytest.mark.wall_clock
@pytest.mark.asyncio
async def test_silence_while_thinking_gives_way_before_the_idle_timeout() -> None:
    """The lever question: DeepSeek's reasoning began, then nothing came for 30 s."""
    provider = _Provider(_StalledThought(), _Stream(thoughts=0, answer="a) 2400 N m"))
    settings = _settings(chat_stream_thought_idle_seconds=0.2, chat_stream_timeout_seconds=30)
    attempts: list[StreamAttempt] = []
    started = asyncio.get_running_loop().time()
    text = await _reply(settings, provider, "smart-chat", ["qwen-3.8-flash"], attempts=attempts)
    assert text == "a) 2400 N m"
    assert asyncio.get_running_loop().time() - started < 5
    assert attempts[0].cause == "timeout"
    # A silence is the provider's, not the thinking's: the next model still thinks.
    assert _reasoning(provider.calls[1]) == {"max_tokens": _BUDGET}


class _SlowFirstChunk(_Stream):
    """A provider that takes a while to send anything at all (reading a photo)."""

    async def __anext__(self) -> MagicMock:
        if not getattr(self, "_waited", False):
            self._waited = True
            await asyncio.sleep(0.4)
        return await super().__anext__()


@pytest.mark.wall_clock
@pytest.mark.asyncio
async def test_a_slow_first_chunk_keeps_the_usual_idle_wait() -> None:
    """Review: the short silence is for thinking under way; before any chunk (a photo read,
    a slow lane) the wait stays the usual one, and the model keeps the turn."""
    provider = _Provider(_SlowFirstChunk(thoughts=1, answer="It is a cat."))
    settings = _settings(chat_stream_thought_idle_seconds=0.2, chat_stream_timeout_seconds=30)
    attempts: list[StreamAttempt] = []
    text = await _reply(settings, provider, "smart-chat", ["qwen-3.8-flash"], attempts=attempts)
    assert text == "It is a cat." and len(provider.calls) == 1


@pytest.mark.asyncio
async def test_the_last_model_is_tried_once_more_without_thinking() -> None:
    provider = _Provider(_Stream(thoughts=2, answer=None), _Stream(thoughts=0, answer="Answer"))
    text = await _reply(_settings(), provider, "qwen-3.8-flash", [])
    assert text == "Answer"
    first, second = provider.calls
    assert _reasoning(first) == {"max_tokens": _BUDGET}
    assert _reasoning(second) == {"effort": "none"}


@pytest.mark.asyncio
async def test_a_last_model_whose_thinking_cannot_drop_is_not_sent_again() -> None:
    """GLM at "hard" and without thinking both send "low": the same request is not repeated."""
    provider = _Provider(_Stream(thoughts=2, answer=None))
    with pytest.raises(litellm_gateway.ModelUnavailableError):
        await _reply(_settings(), provider, "glm-5.3-flash", [], thinking="hard")
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_a_cut_off_attempt_counts_its_reasoning_toward_spend() -> None:
    provider = _Provider(
        _Stream(thoughts=0, answer=None, endless=True), _Stream(thoughts=0, answer="Part 1")
    )
    settings = _settings(chat_reasoning_budget_tokens=10)
    with patch("app.gateways.llm_spend.meter_discarded_attempt") as meter:
        await _reply(settings, provider, "smart-chat", ["qwen-3.8-flash"])
    alias, usage, _chars, cause = meter.call_args.args
    assert (alias, cause) == ("smart-chat", THOUGHT_OUT)
    assert usage["output"] >= 10


@pytest.mark.asyncio
async def test_a_model_that_always_thinks_is_not_retried_once_thinking_is_off() -> None:
    """GLM thinks even when asked not to: thinking off already, it is not tried again."""
    provider = _Provider(_Stream(thoughts=2, answer=None))
    with pytest.raises(litellm_gateway.ModelUnavailableError) as raised:
        await _reply(_settings(), provider, "glm-5.3-flash", [], thinking=False)
    assert raised.value.cause == THOUGHT_OUT
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_an_answer_after_thinking_is_kept_and_a_reply_without_thinking_has_no_ceiling() -> (
    None
):
    provider = _Provider(_Stream(thoughts=3, answer="Done"))
    assert await _reply(_settings(), provider, "smart-chat", []) == "Done"
    assert AttemptThinking(False).answer_by() is None

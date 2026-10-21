"""What a model stream shows before its answer: the think hold, thinking, first-reply caps."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.gateways.think_stripper import STRAY_THINK_LEAD_HOLD, THINK_CLOSE, ThinkStripper

_SETTINGS = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")


def chunk(content: str | None = None, reasoning: str | None = None) -> SimpleNamespace:
    delta = SimpleNamespace(content=content, reasoning_content=reasoning)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=None)], usage=None)


class FakeStream:
    """A provider stream: each chunk after its delay, then it waits for ``finish``
    (or fails, when given an ``error``)."""

    def __init__(
        self,
        chunks: list[SimpleNamespace],
        *,
        delay: float = 0.0,
        error: Exception | None = None,
    ) -> None:
        self._chunks = list(chunks)
        self._delay = delay
        self._error = error
        self.finish = asyncio.Event()

    def __aiter__(self) -> FakeStream:
        return self

    async def __anext__(self) -> SimpleNamespace:
        if not self._chunks:
            if self._error is not None:
                raise self._error
            await self.finish.wait()
            raise StopAsyncIteration
        if self._delay:
            await asyncio.sleep(self._delay)
        return self._chunks.pop(0)


def stream_once(alias: str, provider: FakeStream, **kwargs: Any) -> AsyncIterator[str]:
    async def run() -> AsyncIterator[str]:
        with patch.object(litellm_gateway, "acompletion", AsyncMock(return_value=provider)):
            async for token in litellm_gateway._stream_chat_once(
                settings=kwargs.pop("settings", _SETTINGS),
                model_alias=alias,
                messages=[{"role": "user", "content": "what is 2 + 2?"}],
                max_tokens=50,
                **kwargs,
            ):
                yield token

    return run()


# ── the think hold ─────────────────────────────────────────────────────────────


def test_the_hold_ends_when_reasoning_streams_on_its_own_channel() -> None:
    stripper = ThinkStripper(lead_hold=STRAY_THINK_LEAD_HOLD)
    assert stripper.feed("Paris is the capital of France.") == ""
    assert stripper.holding_thought
    released = stripper.reasoning_streamed()
    assert released == "Paris is the capital of "
    assert not stripper.holding_thought
    assert stripper.feed(" Its river") + stripper.flush() == "France. Its river"


def test_after_reasoning_streams_the_start_is_never_held() -> None:
    stripper = ThinkStripper(lead_hold=STRAY_THINK_LEAD_HOLD)
    assert stripper.reasoning_streamed() == ""
    assert stripper.feed("The answer is 4, since 2 + 2 = 4.") == "The answer is 4, since 2 +"
    # A lone closing tag is still never shown.
    assert stripper.feed(f"{THINK_CLOSE} Done.") + stripper.flush() == " 2 = 4. Done."


def test_a_think_block_is_a_held_thought() -> None:
    stripper = ThinkStripper()
    assert stripper.feed("<think>the user wants a sum") == ""
    assert stripper.holding_thought
    assert stripper.feed("</think>4") + stripper.flush() == "4"
    assert not stripper.holding_thought


def test_without_a_hold_nothing_is_a_held_thought() -> None:
    stripper = ThinkStripper()
    stripper.feed("Hello")
    assert not stripper.holding_thought
    assert stripper.reasoning_streamed() == ""


@pytest.mark.asyncio
async def test_a_guarded_model_with_channel_reasoning_shows_its_answer_at_once() -> None:
    provider = FakeStream(
        [chunk(reasoning="Capital of France."), chunk(content="Paris is the capital of France.")]
    )
    tokens = stream_once("glm-5.3-flash", provider)
    # Not held for the stray-tag window: the text arrives while the stream is open.
    first = await asyncio.wait_for(anext(tokens), 1)
    assert first == "Paris is the capital of "
    provider.finish.set()
    assert first + "".join([token async for token in tokens]) == "Paris is the capital of France."


@pytest.mark.asyncio
async def test_a_guarded_model_still_drops_a_leaked_start_without_channel_reasoning() -> None:
    provider = FakeStream([chunk(content="Simple question."), chunk(content=f"{THINK_CLOSE}4")])
    provider.finish.set()
    tokens = [token async for token in stream_once("glm-5.3-flash", provider)]
    assert "".join(tokens) == "4"


@pytest.mark.asyncio
async def test_a_guarded_model_holds_a_clean_start_until_the_stream_ends() -> None:
    provider = FakeStream([chunk(content="Paris is the capital of France.")])
    tokens = stream_once("glm-5.3-flash", provider)
    pending = asyncio.ensure_future(anext(tokens))
    await asyncio.sleep(0.05)
    assert not pending.done()
    provider.finish.set()
    assert await pending == "Paris is the capital of France."


# ── first-reply caps ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "alias, thinking, has_next, signal, text",
    [
        # Auto's everyday lane: no thinking, first text in about a second.
        ("qwen-3.7-flash", "off", True, 3.0, None),
        ("gpt-6-luna", "off", True, 3.0, None),
        ("free-chat", False, True, 3.0, None),
        # A fast model asked to think gets no signal cap: it may think silently.
        ("free-chat", "hard", True, None, None),
        # The free plan's hard and maths lane always thinks, and streams it.
        ("glm-5.3-flash", "off", True, 4.0, None),
        ("glm-5.3-flash", "escalate", True, 4.0, None),
        # Paid reasoning lanes keep the silent-thought cap on visible text.
        ("smart-chat", "hard", True, None, 8.0),
        ("glm-5.2", "hard", True, None, 8.0),
        # The photo lane reads an image first; it is not the everyday lane.
        ("vision-chat", "off", True, None, None),
        # The last model in the chain is never capped.
        ("qwen-3.7-flash", "off", False, None, None),
        ("glm-5.3-flash", "off", False, None, None),
        ("smart-chat", "hard", False, None, None),
    ],
)
def test_first_reply_caps_by_lane(
    alias: str, thinking: str | bool, has_next: bool, signal: float | None, text: float | None
) -> None:
    from app.gateways.stream_signals import first_reply_caps

    caps = first_reply_caps(_SETTINGS, alias, thinking, has_next=has_next)
    assert (caps.signal, caps.text) == (signal, text)


def _fast_caps(**overrides: Any) -> Settings:
    return Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        chat_stream_first_text_timeout_seconds=0.15,
        chat_stream_first_thought_timeout_seconds=0.15,
        chat_stream_timeout_seconds=30,
        **overrides,
    )


def _chain(*providers: FakeStream) -> AsyncMock:
    queue = list(providers)

    async def acompletion(**_kwargs: Any) -> FakeStream:
        return queue.pop(0)

    return AsyncMock(side_effect=acompletion)


async def _reply(alias: str, fallbacks: list[str], fake: AsyncMock, settings: Settings) -> str:
    meta: dict[str, str] = {}
    with patch.object(litellm_gateway, "acompletion", fake):
        tokens = [
            token
            async for token in litellm_gateway.stream_chat_completion(
                settings=settings,
                model_alias=alias,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=50,
                fallback_aliases=fallbacks,
                stream_meta=meta,
                thinking="off",
            )
        ]
    return f"{meta['model_alias']}: {''.join(tokens)}"


def _ready(*chunks: SimpleNamespace, delay: float = 0.0) -> FakeStream:
    provider = FakeStream(list(chunks), delay=delay)
    provider.finish.set()
    return provider


@pytest.mark.asyncio
async def test_a_silent_everyday_model_gives_way_after_the_first_text_cap() -> None:
    silent = FakeStream([])  # opens, then never sends a chunk
    fake = _chain(silent, _ready(chunk(content="Hello there, friend.")))
    started = time.monotonic()
    reply = await _reply("qwen-3.7-flash", ["free-chat"], fake, _fast_caps())
    assert reply == "free-chat: Hello there, friend."
    # The idle timeout is 30 s: the cap moved on in a fraction of a second.
    assert time.monotonic() - started < 2.0


@pytest.mark.asyncio
async def test_a_slow_opening_counts_against_the_first_text_cap() -> None:
    async def hangs(**_kwargs: Any) -> FakeStream:
        await asyncio.sleep(5)
        raise AssertionError("never opens in time")

    queue: list[Any] = [hangs, _ready(chunk(content="Hello there, friend."))]

    async def acompletion(**kwargs: Any) -> FakeStream:
        step = queue.pop(0)
        return await step(**kwargs) if callable(step) else step

    started = time.monotonic()
    settings = _fast_caps(chat_stream_connect_timeout_seconds=15)
    reply = await _reply(
        "qwen-3.7-flash", ["free-chat"], AsyncMock(side_effect=acompletion), settings
    )
    assert reply == "free-chat: Hello there, friend."
    assert time.monotonic() - started < 2.0


@pytest.mark.asyncio
async def test_a_thinking_model_is_not_capped_once_it_streams_reasoning() -> None:
    # Reasoning for well past the cap, then the answer: the same model answers.
    thinking = [chunk(reasoning="step") for _ in range(6)]
    provider = _ready(*thinking, chunk(content="The answer is 4."), delay=0.05)
    fake = _chain(provider)
    reply = await _reply("glm-5.3-flash", ["free-chat"], fake, _fast_caps())
    assert reply == "glm-5.3-flash: The answer is 4."


@pytest.mark.asyncio
async def test_a_silent_thinking_model_gives_way_after_the_first_thought_cap() -> None:
    fake = _chain(FakeStream([]), _ready(chunk(content="The answer is 4.")))
    started = time.monotonic()
    reply = await _reply("glm-5.3-flash", ["free-chat"], fake, _fast_caps())
    assert reply == "free-chat: The answer is 4."
    assert time.monotonic() - started < 2.0


@pytest.mark.asyncio
async def test_no_cap_fires_after_text_has_been_sent() -> None:
    # Text, then a pause longer than the cap (but not the idle timeout).
    provider = FakeStream([chunk(content="Hello there, friend. ")])
    fake = _chain(provider)

    async def finish_later() -> None:
        await asyncio.sleep(0.4)
        provider.finish.set()

    finisher = asyncio.create_task(finish_later())
    reply = await _reply("qwen-3.7-flash", ["free-chat"], fake, _fast_caps())
    await finisher
    assert reply == "qwen-3.7-flash: Hello there, friend. "


@pytest.mark.asyncio
async def test_the_last_model_in_the_chain_is_not_capped() -> None:
    provider = FakeStream([chunk(content="Late, but here.")], delay=0.4)
    provider.finish.set()
    reply = await _reply("qwen-3.7-flash", [], _chain(provider), _fast_caps())
    assert reply == "qwen-3.7-flash: Late, but here."


# ── what each model tried did ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_each_model_tried_is_recorded_with_its_outcome() -> None:
    from app.gateways.stream_signals import StreamAttempt

    attempts: list[StreamAttempt] = []
    fake = _chain(FakeStream([]), _ready(chunk(content="Hello there, friend.")))
    with patch.object(litellm_gateway, "acompletion", fake):
        tokens = [
            token
            async for token in litellm_gateway.stream_chat_completion(
                settings=_fast_caps(),
                model_alias="qwen-3.7-flash",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=50,
                fallback_aliases=["free-chat"],
                thinking="off",
                attempts=attempts,
            )
        ]
    assert "".join(tokens) == "Hello there, friend."
    assert [(a.alias, a.failed) for a in attempts] == [
        ("qwen-3.7-flash", True),
        ("free-chat", False),
    ]
    # The silent model never started; the one that answered did, quickly.
    assert attempts[0].first_delta_ms is None
    assert attempts[1].first_delta_ms is not None and attempts[1].first_delta_ms < 1000


@pytest.mark.asyncio
async def test_a_reply_that_fails_partway_is_recorded_as_failed() -> None:
    from app.gateways.stream_signals import StreamAttempt

    attempts: list[StreamAttempt] = []
    broken = FakeStream([chunk(content="The first half of it")], error=RuntimeError("reset"))
    with patch.object(litellm_gateway, "acompletion", _chain(broken)):
        with pytest.raises(litellm_gateway.ModelUnavailableError):
            async for _ in litellm_gateway.stream_chat_completion(
                settings=_fast_caps(),
                model_alias="qwen-3.7-flash",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=50,
                fallback_aliases=["free-chat"],
                thinking="off",
                attempts=attempts,
            ):
                pass
    assert [(a.alias, a.failed) for a in attempts] == [("qwen-3.7-flash", True)]


# ── the thinking signal ────────────────────────────────────────────────────────


async def _signals(alias: str, *chunks: SimpleNamespace) -> list[str]:
    """What the caller sees, in order: each text, and "THINKING" when it is told."""
    seen: list[str] = []

    async def on_thinking() -> None:
        seen.append("THINKING")

    provider = _ready(*chunks)
    with patch.object(litellm_gateway, "acompletion", AsyncMock(return_value=provider)):
        async for token in litellm_gateway.stream_chat_completion(
            settings=_SETTINGS,
            model_alias=alias,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=50,
            on_thinking=on_thinking,
        ):
            seen.append(token)
    return seen


@pytest.mark.asyncio
async def test_reasoning_on_its_own_channel_is_thinking_before_the_text() -> None:
    seen = await _signals(
        "smart-chat",
        chunk(reasoning="Try x = 4."),
        chunk(reasoning="Check: 4 + 4 = 8."),
        chunk(content="So x = 4, since 4 + 4 = 8."),
    )
    assert seen[0] == "THINKING"
    assert seen.count("THINKING") == 1
    assert "".join(seen[1:]) == "So x = 4, since 4 + 4 = 8."


@pytest.mark.asyncio
async def test_a_think_block_in_the_text_is_thinking() -> None:
    seen = await _signals(
        "smart-chat", chunk(content="<think>Try x = 4."), chunk(content="</think>x = 4, done.")
    )
    assert seen[0] == "THINKING"
    assert "".join(seen[1:]) == "x = 4, done."


@pytest.mark.asyncio
async def test_a_reply_that_never_thinks_sends_no_thinking() -> None:
    seen = await _signals("qwen-3.7-flash", chunk(content="Hello there, friend."))
    assert "THINKING" not in seen


@pytest.mark.asyncio
async def test_reasoning_after_the_text_has_started_is_not_thinking() -> None:
    seen = await _signals(
        "smart-chat",
        chunk(content="Hello there, friend. "),
        chunk(reasoning="an afterthought"),
        chunk(content="How can I help?"),
    )
    assert "THINKING" not in seen


@pytest.mark.asyncio
async def test_a_thinking_status_that_fails_is_not_the_models_failure() -> None:
    async def broken() -> None:
        raise OSError("socket gone")

    provider = _ready(chunk(reasoning="Try x = 4."), chunk(content="So x = 4, since 4 + 4 = 8."))
    attempts: list[Any] = []
    with patch.object(litellm_gateway, "acompletion", AsyncMock(return_value=provider)):
        tokens = [
            token
            async for token in litellm_gateway.stream_chat_completion(
                settings=_SETTINGS,
                model_alias="smart-chat",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=50,
                fallback_aliases=["glm-5.2"],
                on_thinking=broken,
                attempts=attempts,
            )
        ]
    assert "".join(tokens) == "So x = 4, since 4 + 4 = 8."
    assert [(a.alias, a.failed) for a in attempts] == [("smart-chat", False)]


@pytest.mark.asyncio
async def test_a_held_start_on_a_model_that_always_thinks_is_thinking() -> None:
    # GLM 5.3 with no reasoning channel: its start may be leaked reasoning.
    seen = await _signals(
        "glm-5.3-flash", chunk(content="Simple question."), chunk(content="</think>4")
    )
    assert seen == ["THINKING", "4"]

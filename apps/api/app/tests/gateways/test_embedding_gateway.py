"""embed_many: the one bounded embedding fan-out (attachments, chat history, memory).

The provider call is ``embed_text``; every test here patches it, so no test
reaches the network.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.gateways import embedding_gateway

_EMBED_TEXT = "app.gateways.embedding_gateway.embed_text"


def _vector_for(text: str) -> list[float]:
    return [float(len(text)), 0.5]


@pytest.mark.asyncio
async def test_embed_many_returns_results_in_input_order():
    texts = ["a", "bb", "ccc", "dddd", "eeeee"]

    async def embed(_settings: Settings, text: str) -> list[float]:
        # Later inputs finish first, so completion order is the reverse of input order.
        await asyncio.sleep(0.002 * (len(texts) - len(text)))
        return _vector_for(text)

    with patch(_EMBED_TEXT, embed):
        result = await embedding_gateway.embed_many(Settings(), texts, concurrency=len(texts))

    assert result == [_vector_for(text) for text in texts]


@pytest.mark.asyncio
@pytest.mark.parametrize(("concurrency", "count"), [(1, 5), (3, 12), (8, 20), (8, 4)])
async def test_embed_many_caps_calls_in_flight(concurrency: int, count: int):
    in_flight = 0
    peak = 0
    calls = 0

    async def embed(_settings: Settings, text: str) -> list[float]:
        nonlocal in_flight, peak, calls
        calls += 1
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.005)
        in_flight -= 1
        return _vector_for(text)

    texts = [f"piece {index}" for index in range(count)]
    with patch(_EMBED_TEXT, embed):
        result = await embedding_gateway.embed_many(Settings(), texts, concurrency=concurrency)

    assert calls == count
    assert len(result) == count
    # Bounded, and still a fan-out rather than one call at a time.
    assert peak == min(concurrency, count)


@pytest.mark.asyncio
async def test_embed_many_empty_input_makes_no_calls():
    embed = AsyncMock(return_value=[0.1])

    with patch(_EMBED_TEXT, embed):
        result = await embedding_gateway.embed_many(Settings(), [], concurrency=8)

    assert result == []
    embed.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("concurrency", [0, -3])
async def test_embed_many_treats_concurrency_below_one_as_one(concurrency: int):
    in_flight = 0
    peak = 0

    async def embed(_settings: Settings, text: str) -> list[float]:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0)
        in_flight -= 1
        return _vector_for(text)

    with patch(_EMBED_TEXT, embed):
        async with asyncio.timeout(1):
            result = await embedding_gateway.embed_many(
                Settings(), ["one", "two", "three"], concurrency=concurrency
            )

    assert result == [_vector_for("one"), _vector_for("two"), _vector_for("three")]
    assert peak == 1


@pytest.mark.asyncio
async def test_embed_many_keeps_a_failed_piece_as_none_in_its_slot():
    """``embed_text`` returns None on a provider failure; each caller decides what that means
    (attachments drop it, chat history stores a null vector, memory skips the row)."""

    async def embed(_settings: Settings, text: str) -> list[float] | None:
        return None if text == "bad" else _vector_for(text)

    with patch(_EMBED_TEXT, embed):
        result = await embedding_gateway.embed_many(
            Settings(), ["good", "bad", "fine"], concurrency=2
        )

    assert result == [_vector_for("good"), None, _vector_for("fine")]


@pytest.mark.asyncio
async def test_embed_many_raises_what_escapes_embed_text():
    """An error ``embed_text`` does not turn into None fails the whole batch, as each caller's
    own loop did: the attachment job retries, a chat-history message is skipped and logged."""

    async def embed(_settings: Settings, text: str) -> list[float]:
        if text == "boom":
            raise RuntimeError("embedding route missing")
        return _vector_for(text)

    with patch(_EMBED_TEXT, embed), pytest.raises(RuntimeError, match="route missing"):
        await embedding_gateway.embed_many(Settings(), ["ok", "boom", "ok too"], concurrency=3)


@pytest.mark.asyncio
async def test_embed_many_passes_settings_to_each_call():
    settings = Settings(embedding_input_max_chars=123)
    embed = AsyncMock(return_value=[0.1])

    with patch(_EMBED_TEXT, embed):
        await embedding_gateway.embed_many(settings, ["x", "y"], concurrency=2)

    assert [call.args for call in embed.await_args_list] == [(settings, "x"), (settings, "y")]


def test_embedding_concurrency_default_keeps_rag_fan_out():
    assert Settings().embedding_concurrency == 8

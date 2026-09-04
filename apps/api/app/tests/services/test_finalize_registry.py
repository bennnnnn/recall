"""Per-chat pending-finalize registry tests."""

import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.exceptions import RedisUnavailableError
from app.services.chat import finalize_registry


@pytest.mark.asyncio
async def test_gather_wait_does_not_deadlock_when_producer_is_inflight():
    """WS registers the producer as inflight, not finalize.

    stream_chat_response gather-waits finalize as a child Task. If the
    producer were on that same map, the child would wait 10s on the parent.
    """
    chat_id = uuid4()
    finished = asyncio.Event()

    async def producer() -> None:
        await asyncio.gather(
            finalize_registry.wait_for_pending_finalize(chat_id),
            asyncio.sleep(0),
        )
        finished.set()

    task = asyncio.create_task(producer())
    finalize_registry.register_inflight_stream(chat_id, task)
    await asyncio.wait_for(finished.wait(), timeout=0.5)
    await task


@pytest.mark.asyncio
async def test_messages_wait_blocks_on_inflight_stream():
    chat_id = uuid4()
    gate = asyncio.Event()
    order: list[str] = []

    async def producer() -> None:
        await gate.wait()
        order.append("streamed")

    task = asyncio.create_task(producer())
    finalize_registry.register_inflight_stream(chat_id, task)

    async def list_messages() -> None:
        await finalize_registry.wait_for_inflight_stream(chat_id)
        order.append("listed")

    waiter = asyncio.create_task(list_messages())
    await asyncio.sleep(0)
    assert order == []

    gate.set()
    await waiter
    assert order == ["streamed", "listed"]


@pytest.mark.asyncio
async def test_wait_blocks_until_pending_finalize_completes():
    chat_id = uuid4()
    gate = asyncio.Event()
    order: list[str] = []

    async def finalize():
        await gate.wait()
        order.append("finalized")

    task = asyncio.create_task(finalize())
    finalize_registry.register_pending_finalize(chat_id, task)

    async def next_turn():
        await finalize_registry.wait_for_pending_finalize(chat_id)
        order.append("next-turn")

    waiter = asyncio.create_task(next_turn())
    await asyncio.sleep(0)
    assert order == []

    gate.set()
    await waiter
    assert order == ["finalized", "next-turn"]


@pytest.mark.asyncio
async def test_registry_clears_after_completion():
    chat_id = uuid4()
    baseline = finalize_registry.pending_finalize_count()

    async def finalize():
        return None

    task = asyncio.create_task(finalize())
    finalize_registry.register_pending_finalize(chat_id, task)
    assert finalize_registry.pending_finalize_count() == baseline + 1
    await task
    # done callbacks run soon after completion
    await asyncio.sleep(0)
    assert finalize_registry.pending_finalize_count() == baseline
    await finalize_registry.wait_for_pending_finalize(chat_id)


@pytest.mark.asyncio
async def test_inflight_registry_clears_after_completion():
    chat_id = uuid4()
    baseline = finalize_registry.inflight_stream_count()

    async def producer() -> None:
        return None

    task = asyncio.create_task(producer())
    finalize_registry.register_inflight_stream(chat_id, task)
    assert finalize_registry.inflight_stream_count() == baseline + 1
    await task
    await asyncio.sleep(0)
    assert finalize_registry.inflight_stream_count() == baseline


@pytest.mark.asyncio
async def test_wait_swallows_finalize_failure():
    chat_id = uuid4()

    async def finalize():
        raise RuntimeError("boom")

    task = asyncio.create_task(finalize())
    finalize_registry.register_pending_finalize(chat_id, task)
    await asyncio.sleep(0)
    # Must not raise — the finalize task owns its error reporting.
    await finalize_registry.wait_for_pending_finalize(chat_id)
    # Consume the exception so the loop doesn't warn at teardown (production
    # code attaches a logging done-callback that does this).
    assert isinstance(task.exception(), RuntimeError)


@pytest.mark.asyncio
async def test_newer_registration_replaces_older():
    chat_id = uuid4()
    baseline = finalize_registry.pending_finalize_count()
    first_gate = asyncio.Event()

    async def first():
        await first_gate.wait()

    async def second():
        return None

    first_task = asyncio.create_task(first())
    finalize_registry.register_pending_finalize(chat_id, first_task)
    second_task = asyncio.create_task(second())
    finalize_registry.register_pending_finalize(chat_id, second_task)

    await second_task
    await asyncio.sleep(0)
    # The old still-running task must not linger in (or resurrect) the registry.
    assert finalize_registry.pending_finalize_count() == baseline

    first_gate.set()
    await first_task
    await asyncio.sleep(0)
    assert finalize_registry.pending_finalize_count() == baseline


@pytest.mark.asyncio
async def test_redis_marker_blocks_cross_process_wait(fake_redis):
    """Without a local task, waiters poll Redis until the marker clears."""
    chat_id = uuid4()
    order: list[str] = []

    await finalize_registry.mark_pending_finalize(fake_redis, chat_id)

    async def next_turn():
        await finalize_registry.wait_for_pending_finalize(chat_id, fake_redis)
        order.append("next-turn")

    waiter = asyncio.create_task(next_turn())
    await asyncio.sleep(0.05)
    assert order == []

    await finalize_registry.clear_pending_finalize(fake_redis, chat_id)
    await waiter
    assert order == ["next-turn"]


@pytest.mark.asyncio
async def test_redis_marker_absent_is_immediate(fake_redis):
    chat_id = uuid4()
    await finalize_registry.wait_for_pending_finalize(chat_id, fake_redis)


@pytest.mark.asyncio
@pytest.mark.parametrize("finalize_owner", ["local", "remote"])
async def test_history_timeout_remains_bounded_without_cancelling_finalize(
    fake_redis, finalize_owner
):
    chat_id = uuid4()
    gate = asyncio.Event()

    async def finalize():
        await gate.wait()

    task = asyncio.create_task(finalize())
    if finalize_owner == "local":
        finalize_registry.register_pending_finalize(chat_id, task)
    else:
        await finalize_registry.mark_pending_finalize(fake_redis, chat_id)
    try:
        with (
            patch("app.services.chat.finalize_registry._FINALIZE_WAIT_TIMEOUT_SECONDS", 0.01),
            patch("app.services.chat.finalize_registry._FINALIZE_POLL_INTERVAL_SECONDS", 0.001),
        ):
            await finalize_registry.wait_for_pending_finalize(chat_id, fake_redis)
        assert not task.done()
    finally:
        gate.set()
        await task
        await finalize_registry.clear_pending_finalize(fake_redis, chat_id)


@pytest.mark.asyncio
async def test_strict_finalize_wait_fails_closed_when_redis_is_unavailable():
    redis = AsyncMock()
    redis.exists.side_effect = RuntimeError("Redis unavailable")
    with pytest.raises(RedisUnavailableError):
        await finalize_registry.wait_for_pending_finalize(uuid4(), redis, require_complete=True)
    # History can still return its last committed snapshot during the outage.
    await finalize_registry.wait_for_pending_finalize(uuid4(), redis)

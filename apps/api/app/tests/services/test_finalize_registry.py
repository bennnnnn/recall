"""Per-chat pending-finalize registry tests."""

import asyncio
from uuid import uuid4

import pytest

from app.services.chat import finalize_registry


@pytest.mark.asyncio
async def test_wait_is_noop_when_nothing_pending():
    await finalize_registry.wait_for_pending_finalize(uuid4())


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

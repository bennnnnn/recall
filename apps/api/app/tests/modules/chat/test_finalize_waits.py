"""The figure, data chart and formal answer started beside a reply share one deadline at
finalize: each waited its own 2 s after the one before, so a turn with all three could wait
6 s for pictures and a check that were still not in (audit, 2026-11-25)."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.tests.modules.chat.test_formal_turn import _ctx, _settings, _state


@pytest.mark.wall_clock
@pytest.mark.asyncio
async def test_waits_beside_the_reply_share_one_deadline() -> None:
    state = _state(_ctx(), "reply", _settings())
    never = [asyncio.get_running_loop().create_future() for _ in range(3)]
    started = time.monotonic()
    for task in never:
        await state.wait_beside(task, 0.3)
    took = time.monotonic() - started
    assert took < 0.55, f"{took:.2f}s: the waits added up"
    assert took >= 0.25


@pytest.mark.asyncio
async def test_a_task_already_in_is_taken_whatever_the_deadline() -> None:
    state = _state(_ctx(), "reply", _settings())
    await state.wait_beside(asyncio.get_running_loop().create_future(), 0.05)
    done = asyncio.get_running_loop().create_future()
    done.set_result("figure")
    await state.wait_beside(done, 0.05)  # past the deadline: no wait, the result stands
    assert done.done()


@pytest.mark.wall_clock
@pytest.mark.asyncio
async def test_a_longer_allowance_waits_only_its_own_rest() -> None:
    """A wait with a longer allowance (formal's, set higher) still has its own, counted from
    the first wait: it never loses time to a shorter one before it."""
    state = _state(_ctx(), "reply", _settings())
    loop = asyncio.get_running_loop()
    started = time.monotonic()
    await state.wait_beside(loop.create_future(), 0.1)
    late = loop.create_future()
    loop.call_later(0.25, late.set_result, "answer")
    await state.wait_beside(late, 0.4)
    assert late.done()
    assert time.monotonic() - started < 0.4

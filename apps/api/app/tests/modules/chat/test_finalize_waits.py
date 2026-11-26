"""The figure, data chart and formal answer started beside a reply share one deadline at
finalize: each waited its own 2 s after the one before, so a turn with all three could wait
6 s for pictures and a check that were still not in (audit, 2026-11-25)."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.modules.chat.finalize_passes import run_finalize_passes
from app.modules.chat.turn_decision import TurnDecision
from app.tests.modules.chat.test_chart_turn import _LINE
from app.tests.modules.chat.test_formal_turn import _ctx, _settings, _state


def _never() -> asyncio.Future[None]:
    return asyncio.get_running_loop().create_future()


@pytest.mark.wall_clock
@pytest.mark.asyncio
async def test_waits_beside_the_reply_share_one_deadline() -> None:
    state = _state(_ctx(), "reply", _settings())
    started = time.monotonic()
    for task in (_never(), _never(), _never()):
        await state.wait_beside(task, 0.3)
    took = time.monotonic() - started
    assert took < 0.55, f"{took:.2f}s: the waits added up"
    assert took >= 0.25


@pytest.mark.wall_clock
@pytest.mark.asyncio
async def test_a_wait_past_the_shared_deadline_returns_at_once() -> None:
    state = _state(_ctx(), "reply", _settings())
    await state.wait_beside(_never(), 0.2)
    started = time.monotonic()
    await state.wait_beside(_never(), 0.2)
    assert time.monotonic() - started < 0.05


@pytest.mark.wall_clock
@pytest.mark.asyncio
async def test_a_longer_allowance_waits_only_its_own_rest() -> None:
    """A wait with a longer allowance still has its own, counted from the first wait: it
    never loses time to a shorter one before it."""
    state = _state(_ctx(), "reply", _settings())
    loop = asyncio.get_running_loop()
    started = time.monotonic()
    await state.wait_beside(_never(), 0.1)
    late = loop.create_future()
    loop.call_later(0.25, late.set_result, "answer")
    await state.wait_beside(late, 0.4)
    took = time.monotonic() - started
    assert late.done()
    assert 0.2 <= took < 0.4


async def _finalized_with(chart: asyncio.Future[None], formal: asyncio.Future[None]) -> float:
    read: asyncio.Future[TurnDecision | None] = asyncio.get_running_loop().create_future()
    read.set_result(TurnDecision(live=False, think=False, subject="physics"))
    ctx = _ctx(_LINE, chart=chart, formal=formal, live_read=read)
    state = _state(
        ctx, "Rent is the most.", _settings(chart_wait_seconds=0.5, formal_wait_seconds=0.5)
    )
    started = time.monotonic()
    assert await run_finalize_passes(state) is True
    return time.monotonic() - started


@pytest.mark.wall_clock
@pytest.mark.asyncio
async def test_a_turn_whose_chart_and_formal_answer_never_come_waits_one_allowance() -> None:
    """Through every finalize pass: the chart's and the formal answer's waits are the
    shared one, so two tasks that never finish cost one allowance (0.5 s), not two."""
    loop = asyncio.get_running_loop()
    done = [loop.create_future(), loop.create_future()]
    for future in done:
        future.set_result(None)
    baseline = await _finalized_with(*done)
    took = await _finalized_with(_never(), _never())
    waited = took - baseline
    assert 0.4 <= waited < 0.8, f"waited {waited:.2f}s for two never-finishing tasks"

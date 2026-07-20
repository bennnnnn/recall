"""Chat stream_events helpers (finalize wait / done gating)."""

import asyncio

import pytest

from app.services.chat import stream_events


@pytest.mark.asyncio
async def test_await_finalize_commit_timeout_does_not_cancel_task(monkeypatch: pytest.MonkeyPatch):
    """Bare wait_for would cancel finalize on timeout; shield must keep it alive."""
    gate = asyncio.Event()

    async def slow_finalize() -> None:
        await gate.wait()

    task = asyncio.create_task(slow_finalize())
    monkeypatch.setattr(stream_events, "DONE_COMMIT_WAIT_SECONDS", 0.05)
    ok = await stream_events.await_finalize_commit(task)

    assert ok is True
    assert not task.done()

    gate.set()
    await task
    assert task.done()
    assert task.exception() is None


@pytest.mark.asyncio
async def test_await_finalize_commit_returns_false_on_failure():
    async def boom() -> None:
        raise RuntimeError("commit failed")

    task = asyncio.create_task(boom())
    ok = await stream_events.await_finalize_commit(task)
    assert ok is False

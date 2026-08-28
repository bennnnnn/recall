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
    status = await stream_events.await_finalize_commit(task)

    assert status == "timeout"
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
    status = await stream_events.await_finalize_commit(task)
    assert status == "failed"


@pytest.mark.asyncio
async def test_await_finalize_commit_returns_committed_on_success():
    async def ok_finalize() -> None:
        return None

    task = asyncio.create_task(ok_finalize())
    status = await stream_events.await_finalize_commit(task)
    assert status == "committed"


@pytest.mark.asyncio
async def test_await_finalize_commit_returns_committed_when_no_task():
    status = await stream_events.await_finalize_commit(None)
    assert status == "committed"


@pytest.mark.asyncio
async def test_persist_finalize_if_pending_awaits_task():
    ran = False

    async def finalize() -> None:
        nonlocal ran
        ran = True

    result = {"_finalize_db_task": asyncio.create_task(finalize()), "_finalize_task": object()}
    await stream_events.persist_finalize_if_pending(result)
    assert ran is True
    assert "_finalize_db_task" not in result


@pytest.mark.asyncio
async def test_persist_finalize_if_pending_is_noop_without_task():
    await stream_events.persist_finalize_if_pending({})

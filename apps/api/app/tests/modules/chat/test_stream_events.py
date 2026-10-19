"""Chat stream_events helpers (finalize wait / done gating)."""

import asyncio

import pytest

from app.modules.chat import stream_events
from app.modules.chat.turn_outcome import TurnOutcome


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

    outcome = TurnOutcome(
        finalize_db_task=asyncio.create_task(finalize()),
        finalize_task=asyncio.create_task(asyncio.sleep(0)),
    )
    await stream_events.persist_finalize_if_pending(outcome)
    assert ran is True
    assert outcome.finalize_db_task is None
    assert outcome.finalize_task is None


@pytest.mark.asyncio
async def test_persist_finalize_if_pending_is_noop_without_task():
    await stream_events.persist_finalize_if_pending(TurnOutcome())


def test_spend_cap_refusal_has_its_own_code():
    from app.exceptions import SpendCapReachedError

    payload = stream_events.error_payload_for_exception(SpendCapReachedError("Paused today."))
    assert payload == {"type": "error", "code": "spend_cap", "message": "Paused today."}


@pytest.mark.parametrize("saved", [True, False])
def test_turn_error_payload_says_whether_the_user_message_saved(saved: bool):
    from app.exceptions import ChatBusyError

    assert stream_events.turn_error_payload(ChatBusyError(), user_message_saved=saved) == {
        "type": "error",
        "code": "busy",
        "message": "Still generating — wait or cancel first.",
        "user_message_saved": saved,
    }
    assert stream_events.turn_error_payload(
        None, user_message_saved=saved, message=stream_events.REPLY_SAVE_FAILED_MESSAGE
    ) == {
        "type": "error",
        "message": stream_events.REPLY_SAVE_FAILED_MESSAGE,
        "user_message_saved": saved,
    }

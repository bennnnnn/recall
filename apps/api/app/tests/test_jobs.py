"""Tests for the durable Redis-stream job queue."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core import jobs
from app.core.config import Settings


class _FakeSessionCM:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *args):
        return False


def _patch_session():
    return patch("app.core.jobs.SessionLocal", lambda: _FakeSessionCM())


# ── enqueue ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enqueue_adds_to_stream(fake_redis):
    await jobs.enqueue(fake_redis, "memory", {"a": 1})
    assert await fake_redis.xlen(jobs.JOBS_STREAM) == 1


@pytest.mark.asyncio
async def test_enqueue_swallows_errors():
    redis = AsyncMock()
    redis.xadd = AsyncMock(side_effect=RuntimeError("redis down"))
    await jobs.enqueue(redis, "memory", {"a": 1})  # must not raise


@pytest.mark.asyncio
async def test_enqueue_failure_reports_to_sentry():
    """A failed enqueue must be reported to Sentry (when available) so silent
    job loss is observable — not just logged."""
    redis = AsyncMock()
    redis.xadd = AsyncMock(side_effect=RuntimeError("redis down"))
    with patch("sentry_sdk.capture_exception") as capture:
        await jobs.enqueue(redis, "memory", {"a": 1})
    capture.assert_called_once()


@pytest.mark.asyncio
async def test_enqueue_failure_still_swallows_when_sentry_unavailable():
    """If sentry-sdk isn't importable, enqueue still swallows the redis error
    (the helper's internal import is guarded)."""
    redis = AsyncMock()
    redis.xadd = AsyncMock(side_effect=RuntimeError("redis down"))
    import sys

    original = sys.modules.get("sentry_sdk")
    sys.modules["sentry_sdk"] = None  # make `import sentry_sdk` raise ImportError
    try:
        await jobs.enqueue(redis, "memory", {"a": 1})
    finally:
        if original is not None:
            sys.modules["sentry_sdk"] = original
        else:
            sys.modules.pop("sentry_sdk", None)


# ── is_worker_alive ───────────────────────────────────────────────────────────


def test_is_worker_alive_false_when_no_task():
    jobs._worker_task = None
    assert jobs.is_worker_alive() is False


def test_is_worker_alive_true_when_task_running():
    done_mock = MagicMock()
    done_mock.done.return_value = False
    jobs._worker_task = done_mock
    try:
        assert jobs.is_worker_alive() is True
    finally:
        jobs._worker_task = None


def test_is_worker_alive_false_when_task_done():
    done_mock = MagicMock()
    done_mock.done.return_value = True
    jobs._worker_task = done_mock
    try:
        assert jobs.is_worker_alive() is False
    finally:
        jobs._worker_task = None


# ── dispatch ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_routes_to_handler():
    seen = {}

    async def handler(settings, payload):
        seen["payload"] = payload

    jobs.register("unit-test-job", handler)
    await jobs._dispatch(Settings(), {"type": "unit-test-job", "payload": json.dumps({"x": 1})})
    assert seen["payload"] == {"x": 1}


@pytest.mark.asyncio
async def test_dispatch_unknown_type_is_noop():
    await jobs._dispatch(Settings(), {"type": "does-not-exist", "payload": "{}"})


@pytest.mark.asyncio
async def test_dispatch_bad_payload_skips_handler():
    calls = {"n": 0}

    async def handler(settings, payload):
        calls["n"] += 1

    jobs.register("bad-payload-job", handler)
    await jobs._dispatch(Settings(), {"type": "bad-payload-job", "payload": "{not-json"})
    assert calls["n"] == 0


# ── handlers ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_compress_delegates():
    cid = uuid4()
    with patch("app.core.jobs.compaction.compress_chat_history", AsyncMock()) as job:
        await jobs._handle_compress(Settings(), {"chat_id": str(cid)})
    job.assert_awaited_once()
    assert job.call_args.args[1] == cid


@pytest.mark.asyncio
async def test_handle_topic_delegates():
    with (
        _patch_session(),
        patch("app.core.jobs.topic_generation.generate_chat_title", AsyncMock()) as job,
    ):
        await jobs._handle_topic(
            Settings(),
            {"chat_id": str(uuid4()), "user_message": "hi", "assistant_message": "yo"},
        )
    job.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_memory_delegates():
    with (
        _patch_session(),
        patch("app.core.jobs.memory_extraction.extract_and_store_memories", AsyncMock()) as job,
    ):
        await jobs._handle_memory(
            Settings(),
            {"user_id": str(uuid4()), "chat_id": str(uuid4()), "transcript": "t"},
        )
    job.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_memory_consolidate_delegates():
    with (
        _patch_session(),
        patch(
            "app.core.jobs.memory_consolidation.consolidate_user_memory_sections",
            AsyncMock(),
        ) as job,
    ):
        await jobs._handle_memory_consolidate(Settings(), {"user_id": str(uuid4())})
    job.assert_awaited_once()


# ── worker ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_entries_dispatches_and_acks():
    redis = AsyncMock()
    seen = []

    async def handler(settings, payload):
        seen.append(payload)

    jobs.register("proc-job", handler)
    entries = [("1-0", {"type": "proc-job", "payload": json.dumps({"k": 1})})]
    await jobs._process_entries(redis, Settings(), entries)
    assert seen == [{"k": 1}]
    redis.xack.assert_awaited_once()
    redis.xadd.assert_not_called()


@pytest.mark.asyncio
async def test_process_entries_failed_job_goes_to_dlq():
    redis = AsyncMock()
    calls = {"n": 0}

    async def handler(_settings, _payload):
        calls["n"] += 1
        raise RuntimeError("boom")

    jobs.register("fail-job", handler)
    entries = [("2-0", {"type": "fail-job", "payload": "{}"})]
    # Retry backoff would slow the test; collapse sleeps to instant.
    with patch("app.core.jobs.asyncio.sleep", AsyncMock()):
        await jobs._process_entries(redis, Settings(), entries)
    # Handler retried up to _MAX_ATTEMPTS, then went to the DLQ.
    assert calls["n"] == jobs._MAX_ATTEMPTS
    redis.xadd.assert_awaited_once()
    assert redis.xadd.call_args.args[0] == jobs.JOBS_DLQ_STREAM
    redis.xack.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_entries_retries_then_succeeds_without_dlq():
    redis = AsyncMock()
    calls = {"n": 0}

    async def handler(_settings, _payload):
        calls["n"] += 1
        if calls["n"] < jobs._MAX_ATTEMPTS:
            raise RuntimeError("transient")
        # succeeds on the final attempt

    jobs.register("retry-then-ok", handler)
    entries = [("3-0", {"type": "retry-then-ok", "payload": "{}"})]
    with patch("app.core.jobs.asyncio.sleep", AsyncMock()):
        await jobs._process_entries(redis, Settings(), entries)
    assert calls["n"] == jobs._MAX_ATTEMPTS
    # No DLQ write when the job eventually succeeds.
    redis.xadd.assert_not_called()
    redis.xack.assert_awaited_once()


# ── DLQ inspection / replay ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_and_replay_dlq_roundtrip(fake_redis):
    # Seed a failed job into the DLQ directly.
    await fake_redis.xadd(
        jobs.JOBS_DLQ_STREAM,
        {
            "original_id": "9-0",
            "type": "memory",
            "payload": json.dumps({"user_id": "u", "chat_id": "c", "transcript": "t"}),
            "error": "RuntimeError: boom",
            "failed_at": "2026-07-02T00:00:00+00:00",
        },
    )

    listed = await jobs.list_dlq(fake_redis, count=10)
    assert len(listed) == 1
    assert listed[0]["type"] == "memory"
    assert "boom" in listed[0]["error"]

    # Replay moves it back onto the jobs stream and removes it from the DLQ.
    replayed = await jobs.replay_dlq(fake_redis, count=10, delete=True)
    assert replayed == 1
    assert await fake_redis.xlen(jobs.JOBS_STREAM) == 1
    assert await fake_redis.xlen(jobs.JOBS_DLQ_STREAM) == 0

    # The replayed entry preserves type + payload.
    main_entries = await fake_redis.xrange(jobs.JOBS_STREAM)
    assert main_entries[0][1]["type"] == "memory"
    assert json.loads(main_entries[0][1]["payload"])["transcript"] == "t"


@pytest.mark.asyncio
async def test_worker_loop_processes_then_cancels():
    redis = AsyncMock()
    redis.xgroup_create = AsyncMock()
    redis.xautoclaim = AsyncMock(return_value=("0-0", [], []))
    batch = [(jobs.JOBS_STREAM, [("1-0", {"type": "wl-job", "payload": "{}"})])]
    redis.xreadgroup = AsyncMock(side_effect=[batch, asyncio.CancelledError()])
    redis.xack = AsyncMock()

    seen = []

    async def handler(settings, payload):
        seen.append(payload)

    jobs.register("wl-job", handler)

    with patch("app.core.jobs.get_redis_client", return_value=redis):
        with pytest.raises(asyncio.CancelledError):
            await jobs._worker_loop(Settings())

    assert seen == [{}]


@pytest.mark.asyncio
async def test_start_and_stop_worker():
    with patch("app.core.jobs._worker_loop", AsyncMock()):
        await jobs.start_worker(Settings())
        await jobs.stop_worker()
    assert jobs._worker_task is None

"""Tests for the durable Redis-stream job queue."""

import asyncio
import json
import time
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


def test_is_worker_alive_true_when_task_running_and_heartbeat_fresh():
    done_mock = MagicMock()
    done_mock.done.return_value = False
    jobs._worker_task = done_mock
    jobs._last_heartbeat = time.monotonic()
    try:
        assert jobs.is_worker_alive() is True
    finally:
        jobs._worker_task = None
        jobs._last_heartbeat = 0.0


def test_is_worker_alive_true_when_task_running_and_heartbeat_never_set():
    """Before the loop's first iteration has had a chance to run, heartbeat is
    still 0.0 — that pre-first-iteration window is already covered by the
    task.done() check, so we must not flag staleness during it."""
    done_mock = MagicMock()
    done_mock.done.return_value = False
    jobs._worker_task = done_mock
    jobs._last_heartbeat = 0.0
    try:
        assert jobs.is_worker_alive() is True
    finally:
        jobs._worker_task = None


def test_is_worker_alive_false_when_task_done():
    done_mock = MagicMock()
    done_mock.done.return_value = True
    jobs._worker_task = done_mock
    jobs._last_heartbeat = time.monotonic()
    try:
        assert jobs.is_worker_alive() is False
    finally:
        jobs._worker_task = None
        jobs._last_heartbeat = 0.0


def test_is_worker_alive_false_when_heartbeat_stale_even_if_task_running():
    """A task that's genuinely hung (e.g. a handler awaiting something that
    never resolves) never becomes done() — the heartbeat is what catches it."""
    done_mock = MagicMock()
    done_mock.done.return_value = False
    jobs._worker_task = done_mock
    jobs._last_heartbeat = time.monotonic() - jobs._HEARTBEAT_STALE_THRESHOLD_S - 1
    try:
        assert jobs.is_worker_alive() is False
    finally:
        jobs._worker_task = None
        jobs._last_heartbeat = 0.0


def test_is_worker_alive_true_when_heartbeat_just_under_threshold():
    done_mock = MagicMock()
    done_mock.done.return_value = False
    jobs._worker_task = done_mock
    jobs._last_heartbeat = time.monotonic() - (jobs._HEARTBEAT_STALE_THRESHOLD_S - 1)
    try:
        assert jobs.is_worker_alive() is True
    finally:
        jobs._worker_task = None
        jobs._last_heartbeat = 0.0


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
async def test_dispatch_unknown_type_raises_discard():
    with pytest.raises(jobs.JobDiscardError, match="unknown job type"):
        await jobs._dispatch(Settings(), {"type": "does-not-exist", "payload": "{}"})


@pytest.mark.asyncio
async def test_dispatch_bad_payload_raises_discard():
    calls = {"n": 0}

    async def handler(settings, payload):
        calls["n"] += 1

    jobs.register("bad-payload-job", handler)
    with pytest.raises(jobs.JobDiscardError, match="bad payload"):
        await jobs._dispatch(Settings(), {"type": "bad-payload-job", "payload": "{not-json"})
    assert calls["n"] == 0


@pytest.mark.asyncio
async def test_process_entries_moves_unknown_type_to_dlq(fake_redis):
    await jobs._ensure_group(fake_redis)
    entry_id = await fake_redis.xadd(
        jobs.JOBS_STREAM,
        {"type": "no-such-handler", "payload": "{}"},
    )
    entries = [(entry_id, {"type": "no-such-handler", "payload": "{}"})]
    await jobs._process_entries(fake_redis, Settings(), entries)
    assert await fake_redis.xlen(jobs.JOBS_DLQ_STREAM) == 1


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
    jobs._last_heartbeat = 0.0
    await jobs._process_entries(redis, Settings(), entries)
    assert seen == [{"k": 1}]
    assert jobs._last_heartbeat > 0.0
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


# ── queue metrics / observability ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collect_queue_metrics_empty(fake_redis):
    metrics = await jobs.collect_queue_metrics(fake_redis)
    assert metrics == {"dlq_depth": 0, "pending_entries": 0}


@pytest.mark.asyncio
async def test_collect_queue_metrics_counts_dlq_depth(fake_redis):
    await fake_redis.xadd(jobs.JOBS_DLQ_STREAM, {"type": "memory", "error": "x"})
    await fake_redis.xadd(jobs.JOBS_DLQ_STREAM, {"type": "topic", "error": "y"})
    await fake_redis.xadd(jobs.JOBS_DLQ_STREAM, {"type": "todos", "error": "z"})
    metrics = await jobs.collect_queue_metrics(fake_redis)
    assert metrics["dlq_depth"] == 3


@pytest.mark.asyncio
async def test_collect_queue_metrics_tolerates_redis_errors():
    redis = AsyncMock()
    redis.xlen = AsyncMock(side_effect=RuntimeError("redis down"))
    redis.xpending = AsyncMock(side_effect=RuntimeError("redis down"))
    metrics = await jobs.collect_queue_metrics(redis)
    assert metrics == {"dlq_depth": 0, "pending_entries": 0}


@pytest.mark.asyncio
async def test_report_queue_metrics_warns_when_dlq_exceeds_threshold():
    """A DLQ depth at/above the alert threshold must capture a Sentry warning
    so queue growth is observable in prod (not just the dev-only admin endpoint)."""
    redis = AsyncMock()
    with (
        patch.object(
            jobs,
            "collect_queue_metrics",
            AsyncMock(
                return_value={
                    "dlq_depth": jobs._DLQ_ALERT_THRESHOLD,
                    "pending_entries": 0,
                }
            ),
        ),
        patch("sentry_sdk.add_breadcrumb") as breadcrumb,
        patch("sentry_sdk.capture_message") as capture,
    ):
        await jobs.report_queue_metrics(redis)

    breadcrumb.assert_called_once()
    capture.assert_called_once()
    assert "DLQ depth" in capture.call_args.args[0]
    assert capture.call_args.kwargs.get("level") == "warning"


@pytest.mark.asyncio
async def test_report_queue_metrics_warns_when_pending_exceeds_threshold():
    redis = AsyncMock()
    with (
        patch.object(
            jobs,
            "collect_queue_metrics",
            AsyncMock(
                return_value={
                    "dlq_depth": 0,
                    "pending_entries": jobs._PENDING_ALERT_THRESHOLD,
                }
            ),
        ),
        patch("sentry_sdk.add_breadcrumb"),
        patch("sentry_sdk.capture_message") as capture,
    ):
        await jobs.report_queue_metrics(redis)

    capture.assert_called_once()
    assert "pending entries" in capture.call_args.args[0]


@pytest.mark.asyncio
async def test_report_queue_metrics_quiet_below_thresholds():
    redis = AsyncMock()
    with (
        patch.object(
            jobs,
            "collect_queue_metrics",
            AsyncMock(
                return_value={
                    "dlq_depth": jobs._DLQ_ALERT_THRESHOLD - 1,
                    "pending_entries": jobs._PENDING_ALERT_THRESHOLD - 1,
                }
            ),
        ),
        patch("sentry_sdk.add_breadcrumb") as breadcrumb,
        patch("sentry_sdk.capture_message") as capture,
    ):
        await jobs.report_queue_metrics(redis)

    # Breadcrumb still records the periodic status, but no warning is captured.
    breadcrumb.assert_called_once()
    capture.assert_not_called()


@pytest.mark.asyncio
async def test_report_queue_metrics_noop_without_sentry():
    """If sentry-sdk isn't importable, report_queue_metrics still returns the
    metrics and never raises into the worker loop."""
    redis = AsyncMock()
    import sys

    original = sys.modules.get("sentry_sdk")
    sys.modules["sentry_sdk"] = None
    try:
        with patch.object(
            jobs,
            "collect_queue_metrics",
            AsyncMock(
                return_value={
                    "dlq_depth": jobs._DLQ_ALERT_THRESHOLD,
                    "pending_entries": 0,
                }
            ),
        ):
            metrics = await jobs.report_queue_metrics(redis)
    finally:
        if original is not None:
            sys.modules["sentry_sdk"] = original
        else:
            sys.modules.pop("sentry_sdk", None)
    assert metrics["dlq_depth"] == jobs._DLQ_ALERT_THRESHOLD


# ── periodic reclaim ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reclaim_pending_jobs_processes_claimed_entries():
    """_reclaim_pending_jobs must process entries returned by XAUTOCLAIM,
    so a crashed worker's stuck entries are picked up by a live peer."""
    redis = AsyncMock()
    claimed_entries = [("1-0", {"type": "reclaim-job", "payload": "{}"})]
    redis.xautoclaim = AsyncMock(return_value=("0-0", claimed_entries, []))
    redis.xack = AsyncMock()

    seen = []

    async def handler(settings, payload):
        seen.append(payload)

    jobs.register("reclaim-job", handler)

    with patch("app.core.jobs.get_redis_client", return_value=redis):
        await jobs._reclaim_pending_jobs(redis, Settings(), "worker-test")

    assert seen == [{}]
    redis.xautoclaim.assert_awaited_once()


@pytest.mark.asyncio
async def test_reclaim_pending_jobs_swallows_xautoclaim_errors():
    """A Redis error during reclaim must not crash the worker loop."""
    redis = AsyncMock()
    redis.xautoclaim = AsyncMock(side_effect=Exception("redis down"))

    with patch("app.core.jobs.get_redis_client", return_value=redis):
        # Must not raise.
        await jobs._reclaim_pending_jobs(redis, Settings(), "worker-test")

    redis.xautoclaim.assert_awaited_once()

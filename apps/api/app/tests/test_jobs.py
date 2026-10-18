"""Tests for the durable Redis-stream job queue."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.background import handlers as job_handlers
from app.core import jobs
from app.core.config import Settings
from app.core.jobs import admin, dedupe, queue, worker


class _FakeSessionCM:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *args):
        return False


def _patch_session():
    return patch("app.background.handlers.SessionLocal", lambda: _FakeSessionCM())


@pytest.fixture(autouse=True)
def _restore_handlers():
    # Handlers registered here must not leak into later tests' registry.
    with patch.dict(queue._HANDLERS):
        yield


def test_consumer_name_includes_hostname_and_pid():
    import os

    name = worker._consumer_name()
    assert name.startswith("worker-")
    assert str(os.getpid()) in name
    # Hostname segment keeps multi-container PID-1 workers distinct.
    assert name.count("-") >= 2


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
    worker._worker_task = None
    assert jobs.is_worker_alive() is False


def test_is_worker_alive_true_when_task_running_and_heartbeat_fresh():
    done_mock = MagicMock()
    done_mock.done.return_value = False
    worker._worker_task = done_mock
    worker._last_heartbeat = time.monotonic()
    try:
        assert jobs.is_worker_alive() is True
    finally:
        worker._worker_task = None
        worker._last_heartbeat = 0.0


def test_is_worker_alive_true_when_task_running_and_heartbeat_never_set():
    """Before the loop's first iteration has had a chance to run, heartbeat is
    still 0.0 — that pre-first-iteration window is already covered by the
    task.done() check, so we must not flag staleness during it."""
    done_mock = MagicMock()
    done_mock.done.return_value = False
    worker._worker_task = done_mock
    worker._last_heartbeat = 0.0
    try:
        assert jobs.is_worker_alive() is True
    finally:
        worker._worker_task = None


def test_is_worker_alive_false_when_task_done():
    done_mock = MagicMock()
    done_mock.done.return_value = True
    worker._worker_task = done_mock
    worker._last_heartbeat = time.monotonic()
    try:
        assert jobs.is_worker_alive() is False
    finally:
        worker._worker_task = None
        worker._last_heartbeat = 0.0


def test_is_worker_alive_false_when_heartbeat_stale_even_if_task_running():
    """A task that's genuinely hung (e.g. a handler awaiting something that
    never resolves) never becomes done() — the heartbeat is what catches it."""
    done_mock = MagicMock()
    done_mock.done.return_value = False
    worker._worker_task = done_mock
    worker._last_heartbeat = time.monotonic() - worker._HEARTBEAT_STALE_THRESHOLD_S - 1
    try:
        assert jobs.is_worker_alive() is False
    finally:
        worker._worker_task = None
        worker._last_heartbeat = 0.0


def test_is_worker_alive_true_when_heartbeat_just_under_threshold():
    done_mock = MagicMock()
    done_mock.done.return_value = False
    worker._worker_task = done_mock
    worker._last_heartbeat = time.monotonic() - (worker._HEARTBEAT_STALE_THRESHOLD_S - 1)
    try:
        assert jobs.is_worker_alive() is True
    finally:
        worker._worker_task = None
        worker._last_heartbeat = 0.0


# ── dispatch ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_routes_to_handler():
    seen = {}

    async def handler(settings, payload):
        seen["payload"] = payload

    jobs.register("unit-test-job", handler)
    await queue._dispatch(Settings(), {"type": "unit-test-job", "payload": json.dumps({"x": 1})})
    assert seen["payload"] == {"x": 1}


@pytest.mark.asyncio
async def test_dispatch_unknown_type_raises_discard():
    with pytest.raises(jobs.JobDiscardError, match="unknown job type"):
        await queue._dispatch(Settings(), {"type": "does-not-exist", "payload": "{}"})


@pytest.mark.asyncio
async def test_dispatch_bad_payload_raises_discard():
    calls = {"n": 0}

    async def handler(settings, payload):
        calls["n"] += 1

    jobs.register("bad-payload-job", handler)
    with pytest.raises(jobs.JobDiscardError, match="bad payload"):
        await queue._dispatch(Settings(), {"type": "bad-payload-job", "payload": "{not-json"})
    assert calls["n"] == 0


@pytest.mark.asyncio
async def test_process_entries_moves_unknown_type_to_dlq(fake_redis):
    await worker._ensure_group(fake_redis)
    entry_id = await fake_redis.xadd(
        jobs.JOBS_STREAM,
        {"type": "no-such-handler", "payload": "{}"},
    )
    entries = [(entry_id, {"type": "no-such-handler", "payload": "{}"})]
    await worker._process_entries(fake_redis, Settings(), entries)
    assert await fake_redis.xlen(jobs.JOBS_DLQ_STREAM) == 1


# ── handlers ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_compress_delegates():
    cid = uuid4()
    with patch("app.background.handlers.compaction.compress_chat_history", AsyncMock()) as job:
        await job_handlers._handle_compress(Settings(), {"chat_id": str(cid)})
    job.assert_awaited_once()
    assert job.call_args.args[1] == cid


@pytest.mark.asyncio
async def test_handle_topic_delegates():
    with (
        _patch_session(),
        patch("app.background.handlers.topic_generation.generate_chat_title", AsyncMock()) as job,
    ):
        await job_handlers._handle_topic(
            Settings(),
            {"chat_id": str(uuid4()), "user_message": "hi", "assistant_message": "yo"},
        )
    job.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_memory_delegates():
    with (
        _patch_session(),
        patch(
            "app.background.handlers.memory_extraction.extract_and_store_memories", AsyncMock()
        ) as job,
    ):
        await job_handlers._handle_memory(
            Settings(),
            {"user_id": str(uuid4()), "chat_id": str(uuid4()), "transcript": "t"},
        )
    job.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_memory_retries_skipped_lock_with_backoff():
    payload = {
        "user_id": str(uuid4()),
        "chat_id": str(uuid4()),
        "transcript": "t",
        "assistant_message_id": str(uuid4()),
    }
    with (
        _patch_session(),
        patch(
            "app.background.handlers.memory_extraction.extract_and_store_memories",
            AsyncMock(return_value="skipped_lock"),
        ),
        patch("app.background.handlers.enqueue", AsyncMock()) as enqueue_mock,
        patch("app.background.handlers.get_redis_client", MagicMock()),
        patch("app.background.handlers.asyncio.sleep", AsyncMock()) as sleep_mock,
    ):
        await job_handlers._handle_memory(Settings(), payload)

    sleep_mock.assert_awaited_once_with(2.0)
    enqueue_mock.assert_awaited_once()
    assert enqueue_mock.await_args.args[2]["lock_retries"] == 1
    assert enqueue_mock.await_args.kwargs["dedupe_key"] == (
        f"memory:{payload['assistant_message_id']}:lock1"
    )


@pytest.mark.asyncio
async def test_handle_memory_discards_after_lock_retries():
    payload = {
        "user_id": str(uuid4()),
        "chat_id": str(uuid4()),
        "transcript": "t",
        "lock_retries": 3,
    }
    with (
        _patch_session(),
        patch(
            "app.background.handlers.memory_extraction.extract_and_store_memories",
            AsyncMock(return_value="skipped_lock"),
        ),
        patch("app.background.handlers.enqueue", AsyncMock()) as enqueue_mock,
        patch("app.background.handlers.asyncio.sleep", AsyncMock()) as sleep_mock,
        pytest.raises(jobs.JobDiscardError, match="lock retries"),
    ):
        await job_handlers._handle_memory(Settings(), payload)

    sleep_mock.assert_not_awaited()
    enqueue_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_memory_consolidate_delegates():
    with (
        _patch_session(),
        patch(
            "app.background.handlers.memory_consolidation.consolidate_user_memory_sections",
            AsyncMock(return_value=True),
        ) as job,
    ):
        await job_handlers._handle_memory_consolidate(Settings(), {"user_id": str(uuid4())})
    job.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_memory_consolidate_retries_skipped_lock_with_backoff():
    payload = {"user_id": str(uuid4())}
    with (
        _patch_session(),
        patch(
            "app.background.handlers.memory_consolidation.consolidate_user_memory_sections",
            AsyncMock(return_value="skipped_lock"),
        ),
        patch("app.background.handlers.enqueue", AsyncMock()) as enqueue_mock,
        patch("app.background.handlers.get_redis_client", MagicMock()),
        patch("app.background.handlers.asyncio.sleep", AsyncMock()) as sleep_mock,
    ):
        await job_handlers._handle_memory_consolidate(Settings(), payload)

    sleep_mock.assert_awaited_once_with(2.0)
    enqueue_mock.assert_awaited_once()
    assert enqueue_mock.await_args.args[1] == "memory_consolidate"
    assert enqueue_mock.await_args.args[2]["lock_retries"] == 1
    assert enqueue_mock.await_args.kwargs["dedupe_key"] == (
        f"memory_consolidate:{payload['user_id']}:lock1"
    )


@pytest.mark.asyncio
async def test_handle_memory_consolidate_discards_after_lock_retries():
    payload = {"user_id": str(uuid4()), "lock_retries": 3}
    with (
        _patch_session(),
        patch(
            "app.background.handlers.memory_consolidation.consolidate_user_memory_sections",
            AsyncMock(return_value="skipped_lock"),
        ),
        patch("app.background.handlers.enqueue", AsyncMock()) as enqueue_mock,
        patch("app.background.handlers.asyncio.sleep", AsyncMock()) as sleep_mock,
        pytest.raises(jobs.JobDiscardError, match="lock retries"),
    ):
        await job_handlers._handle_memory_consolidate(Settings(), payload)

    sleep_mock.assert_not_awaited()
    enqueue_mock.assert_not_awaited()


# ── worker ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_process_entries_dispatches_and_acks():
    redis = AsyncMock()
    seen = []

    async def handler(settings, payload):
        seen.append(payload)

    jobs.register("proc-job", handler)
    entries = [("1-0", {"type": "proc-job", "payload": json.dumps({"k": 1})})]
    worker._last_heartbeat = 0.0
    await worker._process_entries(redis, Settings(), entries)
    assert seen == [{"k": 1}]
    assert worker._last_heartbeat > 0.0
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
    with patch("app.core.jobs.worker.asyncio.sleep", AsyncMock()):
        await worker._process_entries(redis, Settings(), entries)
    # Handler retried up to _MAX_ATTEMPTS, then went to the DLQ.
    assert calls["n"] == worker._MAX_ATTEMPTS
    redis.xadd.assert_awaited_once()
    assert redis.xadd.call_args.args[0] == jobs.JOBS_DLQ_STREAM
    redis.xack.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_entries_retries_then_succeeds_without_dlq():
    redis = AsyncMock()
    calls = {"n": 0}

    async def handler(_settings, _payload):
        calls["n"] += 1
        if calls["n"] < worker._MAX_ATTEMPTS:
            raise RuntimeError("transient")
        # succeeds on the final attempt

    jobs.register("retry-then-ok", handler)
    entries = [("3-0", {"type": "retry-then-ok", "payload": "{}"})]
    with patch("app.core.jobs.worker.asyncio.sleep", AsyncMock()):
        await worker._process_entries(redis, Settings(), entries)
    assert calls["n"] == worker._MAX_ATTEMPTS
    # No DLQ write when the job eventually succeeds.
    redis.xadd.assert_not_called()
    redis.xack.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_entries_runs_batch_concurrently():
    """A batch of slow jobs must overlap — not drain strictly sequentially."""
    redis = AsyncMock()
    started: list[int] = []
    release = asyncio.Event()

    async def handler(_settings, payload):
        started.append(int(payload["i"]))
        await release.wait()

    jobs.register("parallel-job", handler)
    entries = [
        (f"{i}-0", {"type": "parallel-job", "payload": json.dumps({"i": i})}) for i in range(5)
    ]
    task = asyncio.create_task(
        worker._process_entries(redis, Settings(jobs_worker_concurrency=8), entries)
    )
    for _ in range(100):
        if len(started) == 5:
            break
        await asyncio.sleep(0.01)
    assert sorted(started) == [0, 1, 2, 3, 4]
    release.set()
    await task
    assert redis.xack.await_count == 5


@pytest.mark.asyncio
async def test_process_entries_parallel_drain_faster_than_serial():
    """Drain-time smoke: 4x150ms jobs with concurrency 4 finish near one slot."""
    redis = AsyncMock()

    async def handler(_settings, _payload):
        await asyncio.sleep(0.15)

    jobs.register("slow-job", handler)
    entries = [(f"{i}-0", {"type": "slow-job", "payload": "{}"}) for i in range(4)]

    t0 = time.perf_counter()
    await worker._process_entries(redis, Settings(jobs_worker_concurrency=4), entries)
    parallel_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    await worker._process_entries(redis, Settings(jobs_worker_concurrency=1), entries)
    serial_s = time.perf_counter() - t1

    # Parallel should be closer to one sleep than four; leave headroom for CI.
    assert parallel_s < 0.45
    assert serial_s > 0.50
    assert parallel_s < serial_s * 0.7


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

    with patch("app.core.jobs.worker.get_jobs_redis_client", return_value=redis):
        with pytest.raises(asyncio.CancelledError):
            await worker._worker_loop(Settings())

    assert seen == [{}]


@pytest.mark.asyncio
async def test_start_and_stop_worker():
    with patch("app.core.jobs.worker._worker_loop", AsyncMock()):
        await jobs.start_worker(Settings())
        await jobs.stop_worker()
    assert worker._worker_task is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "owns_pending_entry, consumers_left",
    [
        (False, 0),  # clean stop: nothing of ours is pending
        (True, 1),  # deleting it would drop the entry XAUTOCLAIM still needs
    ],
)
async def test_stopped_worker_removes_its_consumer_from_the_group(
    fake_redis, monkeypatch, owns_pending_entry, consumers_left
):
    """Consumers are named per process (host + pid), so every restart, deploy
    and `--reload` added one to the group and nothing ever removed it."""
    processed = asyncio.Event()

    async def handler(settings, payload):
        processed.set()

    monkeypatch.setitem(queue._HANDLERS, "consumer-cleanup", handler)
    await fake_redis.xgroup_create(jobs.JOBS_STREAM, jobs.JOBS_GROUP, id="0", mkstream=True)
    if owns_pending_entry:
        # Delivered to this process earlier and never acked (crash mid-job).
        await fake_redis.xadd(jobs.JOBS_STREAM, {"type": "consumer-cleanup", "payload": "{}"})
        await fake_redis.xreadgroup(
            jobs.JOBS_GROUP, worker._consumer_name(), {jobs.JOBS_STREAM: ">"}, count=1
        )
    await fake_redis.xadd(jobs.JOBS_STREAM, {"type": "consumer-cleanup", "payload": "{}"})

    # fakeredis does not block on XREADGROUP BLOCK; poll without starving the loop.
    real_read = fake_redis.xreadgroup

    async def polling_read(*args, block=None, **kwargs):
        await asyncio.sleep(0.01)
        return await real_read(*args, **kwargs)

    fake_redis.xreadgroup = polling_read

    with patch("app.core.jobs.worker.get_jobs_redis_client", return_value=fake_redis):
        await jobs.start_worker(Settings(jobs_worker_concurrency=1))
        await asyncio.wait_for(processed.wait(), timeout=5)
        await asyncio.sleep(0.05)  # let the ack land
        await jobs.stop_worker()

    consumers = await fake_redis.xinfo_consumers(jobs.JOBS_STREAM, jobs.JOBS_GROUP)
    assert len(consumers) == consumers_left
    if owns_pending_entry:
        assert consumers[0]["pending"] == 1


# ── queue metrics / observability ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collect_queue_metrics_empty(fake_redis):
    await worker._ensure_group(fake_redis)
    metrics = await jobs.collect_queue_metrics(fake_redis)
    assert metrics == {"dlq_depth": 0, "pending_entries": 0, "metrics_error": None}


@pytest.mark.asyncio
async def test_collect_queue_metrics_counts_dlq_depth(fake_redis):
    await fake_redis.xadd(jobs.JOBS_DLQ_STREAM, {"type": "memory", "error": "x"})
    await fake_redis.xadd(jobs.JOBS_DLQ_STREAM, {"type": "topic", "error": "y"})
    await fake_redis.xadd(jobs.JOBS_DLQ_STREAM, {"type": "todos", "error": "z"})
    metrics = await jobs.collect_queue_metrics(fake_redis)
    assert metrics["dlq_depth"] == 3


@pytest.mark.asyncio
async def test_collect_queue_metrics_redis_error_is_unknown_not_zero():
    """Never raises into the worker loop, but a count it could not read is None."""
    redis = AsyncMock()
    redis.xlen = AsyncMock(side_effect=RuntimeError("redis down"))
    redis.xpending = AsyncMock(side_effect=RuntimeError("redis down"))
    metrics = await jobs.collect_queue_metrics(redis)
    assert metrics == {"dlq_depth": None, "pending_entries": None, "metrics_error": "RuntimeError"}


@pytest.mark.asyncio
async def test_report_queue_metrics_warns_when_dlq_exceeds_threshold():
    """A DLQ depth at/above the alert threshold must capture a Sentry warning
    so queue growth is observable in prod (not just the dev-only admin endpoint)."""
    redis = AsyncMock()
    with (
        patch.object(
            admin,
            "collect_queue_metrics",
            AsyncMock(
                return_value={
                    "dlq_depth": admin._DLQ_ALERT_THRESHOLD,
                    "pending_entries": 0,
                    "metrics_error": None,
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
            admin,
            "collect_queue_metrics",
            AsyncMock(
                return_value={
                    "dlq_depth": 0,
                    "pending_entries": admin._PENDING_ALERT_THRESHOLD,
                    "metrics_error": None,
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
            admin,
            "collect_queue_metrics",
            AsyncMock(
                return_value={
                    "dlq_depth": admin._DLQ_ALERT_THRESHOLD - 1,
                    "pending_entries": admin._PENDING_ALERT_THRESHOLD - 1,
                    "metrics_error": None,
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
            admin,
            "collect_queue_metrics",
            AsyncMock(
                return_value={
                    "dlq_depth": admin._DLQ_ALERT_THRESHOLD,
                    "pending_entries": 0,
                    "metrics_error": None,
                }
            ),
        ):
            metrics = await jobs.report_queue_metrics(redis)
    finally:
        if original is not None:
            sys.modules["sentry_sdk"] = original
        else:
            sys.modules.pop("sentry_sdk", None)
    assert metrics["dlq_depth"] == admin._DLQ_ALERT_THRESHOLD


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

    # _reclaim_pending_jobs takes redis as an argument; it never resolved a
    # client itself, so the old get_redis_client patch here was a no-op.
    await worker._reclaim_pending_jobs(redis, Settings(), "worker-test")

    assert seen == [{}]
    redis.xautoclaim.assert_awaited_once()


@pytest.mark.asyncio
async def test_reclaim_pending_jobs_swallows_xautoclaim_errors():
    """A Redis error during reclaim must not crash the worker loop."""
    redis = AsyncMock()
    redis.xautoclaim = AsyncMock(side_effect=Exception("redis down"))

    # Must not raise.
    await worker._reclaim_pending_jobs(redis, Settings(), "worker-test")

    redis.xautoclaim.assert_awaited_once()


# ── job idempotency (dedupe_key) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enqueue_stores_dedupe_key(fake_redis):
    await jobs.enqueue(fake_redis, "memory", {"a": 1}, dedupe_key="mem:1")
    _id, fields = (await fake_redis.xrange(jobs.JOBS_STREAM))[0]
    assert fields["dedupe_key"] == "mem:1"


@pytest.mark.asyncio
async def test_process_entries_skips_duplicate_dedupe_key(fake_redis):
    """Redelivery / duplicate enqueue with the same dedupe_key must not re-run."""
    calls = {"n": 0}

    async def handler(_settings, _payload):
        calls["n"] += 1

    jobs.register("dedupe-job", handler)
    await worker._ensure_group(fake_redis)
    fields = {
        "type": "dedupe-job",
        "payload": "{}",
        "dedupe_key": "todosync:chat:msg1",
    }
    entry_a = await fake_redis.xadd(jobs.JOBS_STREAM, fields)
    entry_b = await fake_redis.xadd(jobs.JOBS_STREAM, fields)
    await worker._process_entries(
        fake_redis,
        Settings(),
        [(entry_a, fields), (entry_b, dict(fields))],
    )
    assert calls["n"] == 1
    assert await fake_redis.get(jobs.job_done_key("todosync:chat:msg1")) == dedupe._DEDUPE_DONE


@pytest.mark.asyncio
async def test_process_entries_releases_dedupe_after_permanent_failure(fake_redis):
    """A exhausted retry must clear the claim so DLQ replay can run again."""

    async def handler(_settings, _payload):
        raise RuntimeError("boom")

    jobs.register("dedupe-fail-job", handler)
    await worker._ensure_group(fake_redis)
    fields = {
        "type": "dedupe-fail-job",
        "payload": "{}",
        "dedupe_key": "welcome:user-1",
    }
    entry_id = await fake_redis.xadd(jobs.JOBS_STREAM, fields)
    with patch("app.core.jobs.worker.asyncio.sleep", AsyncMock()):
        await worker._process_entries(fake_redis, Settings(), [(entry_id, fields)])
    assert await fake_redis.get(jobs.job_done_key("welcome:user-1")) is None
    assert await fake_redis.xlen(jobs.JOBS_DLQ_STREAM) == 1


@pytest.mark.asyncio
async def test_process_entries_claims_with_short_ttl_then_extends_on_success(fake_redis):
    """M2: dedupe claim uses a short TTL so a crash mid-handler lets the
    reclaim re-run; on success the TTL is extended to the full window."""
    calls = {"n": 0}

    async def handler(_settings, _payload):
        calls["n"] += 1

    jobs.register("dedupe-ttl-job", handler)
    await worker._ensure_group(fake_redis)
    fields = {
        "type": "dedupe-ttl-job",
        "payload": "{}",
        "dedupe_key": "ttl:test",
    }
    entry_id = await fake_redis.xadd(jobs.JOBS_STREAM, fields)
    await worker._process_entries(fake_redis, Settings(), [(entry_id, fields)])
    assert calls["n"] == 1
    ttl = await fake_redis.ttl(jobs.job_done_key("ttl:test"))
    # Success overwrites the running claim with the 24h done marker.
    assert await fake_redis.get(jobs.job_done_key("ttl:test")) == dedupe._DEDUPE_DONE
    assert ttl > dedupe._JOB_DONE_CLAIM_TTL_SECONDS


def _pending_count(summary: object) -> int:
    if isinstance(summary, dict):
        return int(summary.get("pending") or summary.get("count") or 0)
    if isinstance(summary, list | tuple) and summary:
        return int(summary[0] or 0)
    return 0


@pytest.mark.asyncio
async def test_process_entries_inflight_claim_does_not_ack(fake_redis):
    """A reclaim that loses NX while the running TTL is still held must leave
    the PEL entry so a later reclaim can run after the crashed worker's key
    expires — not skip+xack (which dropped the job forever)."""
    calls = {"n": 0}

    async def handler(_settings, _payload):
        calls["n"] += 1

    jobs.register("inflight-job", handler)
    await worker._ensure_group(fake_redis)
    fields = {
        "type": "inflight-job",
        "payload": "{}",
        "dedupe_key": "attach:index:1",
    }
    entry_id = await fake_redis.xadd(jobs.JOBS_STREAM, fields)
    await fake_redis.xreadgroup(jobs.JOBS_GROUP, "tester", {jobs.JOBS_STREAM: ">"}, count=1)
    await fake_redis.set(
        jobs.job_done_key("attach:index:1"),
        dedupe._DEDUPE_RUNNING,
        ex=dedupe._JOB_DONE_CLAIM_TTL_SECONDS,
    )
    await worker._process_entries(fake_redis, Settings(), [(entry_id, fields)])
    assert calls["n"] == 0
    pending = await fake_redis.xpending(jobs.JOBS_STREAM, jobs.JOBS_GROUP)
    assert _pending_count(pending) == 1


@pytest.mark.asyncio
async def test_process_entries_done_claim_skips_and_acks(fake_redis):
    """A duplicate enqueue after success must skip the handler and ack."""
    calls = {"n": 0}

    async def handler(_settings, _payload):
        calls["n"] += 1

    jobs.register("done-job", handler)
    await worker._ensure_group(fake_redis)
    fields = {
        "type": "done-job",
        "payload": "{}",
        "dedupe_key": "attach:index:2",
    }
    entry_id = await fake_redis.xadd(jobs.JOBS_STREAM, fields)
    await fake_redis.xreadgroup(jobs.JOBS_GROUP, "tester", {jobs.JOBS_STREAM: ">"}, count=1)
    await fake_redis.set(
        jobs.job_done_key("attach:index:2"),
        dedupe._DEDUPE_DONE,
        ex=dedupe._JOB_DONE_TTL_SECONDS,
    )
    await worker._process_entries(fake_redis, Settings(), [(entry_id, fields)])
    assert calls["n"] == 0
    pending = await fake_redis.xpending(jobs.JOBS_STREAM, jobs.JOBS_GROUP)
    assert _pending_count(pending) == 0


@pytest.mark.asyncio
async def test_process_entries_cancelled_job_stays_pending(fake_redis):
    """A worker stopped mid-job (deploy, SIGTERM) must not ack the entry:
    it stays pending, and its running claim is released, so a live worker's
    reclaim runs it again instead of the job being dropped."""
    started = asyncio.Event()

    async def handler(_settings, _payload):
        started.set()
        await asyncio.sleep(3600)

    jobs.register("shutdown-job", handler)
    await worker._ensure_group(fake_redis)
    fields = {"type": "shutdown-job", "payload": "{}", "dedupe_key": "memory:1"}
    entry_id = await fake_redis.xadd(jobs.JOBS_STREAM, fields)
    await fake_redis.xreadgroup(jobs.JOBS_GROUP, "tester", {jobs.JOBS_STREAM: ">"}, count=1)

    task = asyncio.create_task(
        worker._process_entries(fake_redis, Settings(), [(entry_id, fields)])
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    pending = await fake_redis.xpending(jobs.JOBS_STREAM, jobs.JOBS_GROUP)
    assert _pending_count(pending) == 1
    assert await fake_redis.get(jobs.job_done_key("memory:1")) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "held, ttl, pending_after_reclaim",
    [
        # Another worker is running the job: the entry waits for that run.
        (dedupe._DEDUPE_RUNNING, dedupe._JOB_DONE_CLAIM_TTL_SECONDS, 1),
        # Another worker finished it: the duplicate is acked.
        (dedupe._DEDUPE_DONE, dedupe._JOB_DONE_TTL_SECONDS, 0),
    ],
)
async def test_cancel_after_losing_the_claim_keeps_the_other_runs_key(
    fake_redis, held, ttl, pending_after_reclaim
):
    """A worker stopped while it reads why it lost the claim must not release
    the claim: it never owned it. Deleting another run's key (or the done
    marker) let the next reclaim win SET NX and run the job a second time."""
    calls = []

    async def handler(_settings, _payload):
        calls.append(1)

    jobs.register("lost-claim-job", handler)
    await worker._ensure_group(fake_redis)
    fields = {"type": "lost-claim-job", "payload": "{}", "dedupe_key": "memory:2"}
    entry_id = await fake_redis.xadd(jobs.JOBS_STREAM, fields)
    await fake_redis.xreadgroup(jobs.JOBS_GROUP, "w2", {jobs.JOBS_STREAM: ">"}, count=1)
    key = jobs.job_done_key("memory:2")
    await fake_redis.set(key, held, ex=ttl)

    reading = asyncio.Event()

    async def stalled_get(_name):
        # The state read after a lost SET NX is in flight when the deploy cancels.
        reading.set()
        await asyncio.Event().wait()

    with patch.object(fake_redis, "get", stalled_get):
        task = asyncio.create_task(
            worker._process_entries(fake_redis, Settings(), [(entry_id, fields)])
        )
        await reading.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    after_cancel = await fake_redis.get(key)
    with patch.object(worker, "_CLAIM_IDLE_MS", 0):
        await worker._reclaim_pending_jobs(fake_redis, Settings(), "w3")
    assert after_cancel == held, f"claim key after the cancel: {after_cancel!r}"
    assert calls == [], f"the reclaim ran the job {len(calls)} more time(s)"
    pending = await fake_redis.xpending(jobs.JOBS_STREAM, jobs.JOBS_GROUP)
    assert _pending_count(pending) == pending_after_reclaim

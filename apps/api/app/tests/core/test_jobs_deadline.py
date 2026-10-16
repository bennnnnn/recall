"""A job cannot hang or crash-loop the worker.

* No handler had a deadline. ``_process_entries`` awaits the whole batch, so
  one hung handler (a DB call waiting on a lock, a stalled socket) stopped
  the worker from reading anything else.
* The liveness heartbeat was only touched between attempts, so one healthy
  attempt longer than 120s (OCR index 120s, or a 60s LLM call plus its 60s
  fallback) reported the worker dead.
* An entry that kills the process (OOM in a PDF render) was reclaimed and run
  again after every restart: a crash loop with no delivery limit.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from unittest.mock import patch

import pytest

from app.core import jobs
from app.core.config import Settings
from app.core.jobs import queue, worker


@pytest.fixture(autouse=True)
def _fast_retries():
    with patch.object(worker, "_RETRY_BACKOFF_S", 0.0):
        yield


@pytest.fixture(autouse=True)
def _restore_handlers():
    """Handlers registered here must not leak into later tests."""
    with patch.dict(queue._HANDLERS):
        yield


async def _queued_entry(redis: Any, job_type: str) -> str:
    await worker._ensure_group(redis)
    entry_id = await redis.xadd(
        jobs.JOBS_STREAM, {"type": job_type, "payload": json.dumps({"n": 1})}
    )
    await redis.xreadgroup(jobs.JOBS_GROUP, "w1", {jobs.JOBS_STREAM: ">"}, count=1)
    return str(entry_id)


@pytest.mark.parametrize(
    "behaviour, expected_calls, expected_dlq",
    [
        ("hangs", 1, 1),
        ("inner_timeout", worker._MAX_ATTEMPTS, 1),
        ("ok", 1, 0),
    ],
)
async def test_job_deadline_moves_a_hung_job_to_the_dlq(
    fake_redis: Any, behaviour: str, expected_calls: int, expected_dlq: int
) -> None:
    calls: list[int] = []

    async def handler(_settings: Settings, _payload: dict[str, Any]) -> None:
        calls.append(1)
        if behaviour == "hangs":
            await asyncio.sleep(30)
        if behaviour == "inner_timeout":
            # A provider timeout inside the handler is an ordinary, retried failure.
            raise TimeoutError("provider timed out")

    jobs.register(f"deadline_{behaviour}", handler)
    entry_id = await _queued_entry(fake_redis, f"deadline_{behaviour}")
    settings = Settings(job_timeout_seconds=0.1)
    started = time.monotonic()
    await worker._process_entries(fake_redis, settings, [(entry_id, await _fields(fake_redis))])
    assert time.monotonic() - started < 5
    assert len(calls) == expected_calls
    assert await fake_redis.xlen(jobs.JOBS_DLQ_STREAM) == expected_dlq
    pending = await fake_redis.xpending(jobs.JOBS_STREAM, jobs.JOBS_GROUP)
    assert pending["pending"] == 0


async def _fields(redis: Any) -> dict[str, Any]:
    entries = await redis.xrange(jobs.JOBS_STREAM, count=1)
    return dict(entries[0][1])


async def test_heartbeat_stays_fresh_while_a_long_job_runs(fake_redis: Any) -> None:
    async def handler(_settings: Settings, _payload: dict[str, Any]) -> None:
        await asyncio.sleep(0.6)

    jobs.register("long_running", handler)
    entry_id = await _queued_entry(fake_redis, "long_running")
    fields = await _fields(fake_redis)

    alive_samples: list[bool] = []
    fake_task = asyncio.get_running_loop().create_future()

    async def sample() -> None:
        for _ in range(5):
            await asyncio.sleep(0.1)
            alive_samples.append(jobs.is_worker_alive())

    with (
        patch.object(worker, "_worker_task", fake_task),
        patch.object(worker, "_HEARTBEAT_STALE_THRESHOLD_S", 0.25),
        patch.object(worker, "_JOB_HEARTBEAT_TICK_S", 0.05),
    ):
        await asyncio.gather(
            worker._process_entries(fake_redis, Settings(), [(entry_id, fields)]),
            sample(),
        )
    fake_task.cancel()
    assert alive_samples == [True] * 5


@pytest.mark.parametrize(
    "earlier_deliveries, expected_calls, expected_dlq",
    [
        # The reclaim itself is one more delivery.
        (1, 1, 0),
        (jobs.MAX_JOB_DELIVERIES - 1, 1, 0),
        (jobs.MAX_JOB_DELIVERIES, 0, 1),
        (12, 0, 1),
    ],
)
async def test_reclaim_drops_an_entry_that_keeps_killing_the_worker(
    fake_redis: Any, earlier_deliveries: int, expected_calls: int, expected_dlq: int
) -> None:
    calls: list[int] = []

    async def handler(_settings: Settings, _payload: dict[str, Any]) -> None:
        calls.append(1)

    jobs.register("poison", handler)
    entry_id = await _queued_entry(fake_redis, "poison")
    # Each crash-restart reclaims the entry once more (XAUTOCLAIM bumps the
    # delivery counter); simulate the earlier deliveries.
    for _ in range(earlier_deliveries - 1):
        await fake_redis.xclaim(jobs.JOBS_STREAM, jobs.JOBS_GROUP, "w1", 0, [entry_id])
    with patch.object(worker, "_CLAIM_IDLE_MS", 0):
        await worker._reclaim_pending_jobs(fake_redis, Settings(), "w2")
    assert len(calls) == expected_calls
    assert await fake_redis.xlen(jobs.JOBS_DLQ_STREAM) == expected_dlq
    pending = await fake_redis.xpending(jobs.JOBS_STREAM, jobs.JOBS_GROUP)
    assert pending["pending"] == 0

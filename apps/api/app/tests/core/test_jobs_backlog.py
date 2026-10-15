"""The jobs stream stays bounded while the worker is down or wedged.

``_trim_jobs_stream`` trims to the oldest *pending* id so unacked work is
never erased. One entry left pending by a worker that died mid-job therefore
disabled trimming entirely: every later enqueue grew the stream without
bound (25,001 entries after 25k enqueues in a local proof against Redis 7).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.core import jobs
from app.core.config import Settings

_SOFT_CAP = 100
_HARD_CAP = 300
# Approximate trimming may keep up to one macro node past the cap.
_SLACK = 100


async def _leave_one_pending(redis: Any) -> None:
    await jobs.enqueue(redis, "topic", {"chat_id": "first"})
    await redis.xreadgroup(jobs.JOBS_GROUP, "dead-worker", {jobs.JOBS_STREAM: ">"}, count=1)


@pytest.mark.parametrize(
    "stale_pending, enqueues, max_len",
    [
        (False, 1_000, _SOFT_CAP),
        (True, 1_000, _HARD_CAP),
        (True, 50, 51),
    ],
)
async def test_jobs_stream_stays_bounded_with_a_stale_pending_entry(
    fake_redis: Any, stale_pending: bool, enqueues: int, max_len: int
) -> None:
    await jobs._ensure_group(fake_redis)
    if stale_pending:
        await _leave_one_pending(fake_redis)
    settings = Settings(jobs_stream_max_len=_HARD_CAP)
    with (
        patch.object(jobs, "_MAXLEN", _SOFT_CAP),
        patch.object(jobs, "get_settings", return_value=settings),
    ):
        for i in range(enqueues):
            await jobs.enqueue(fake_redis, "topic", {"chat_id": str(i)})
    length = await fake_redis.xlen(jobs.JOBS_STREAM)
    assert length <= max_len + _SLACK
    if max_len < _SOFT_CAP:
        # Below every cap nothing pending or queued is dropped.
        assert length == max_len


async def test_replay_dlq_does_not_trim_the_backlog_to_the_soft_cap(fake_redis: Any) -> None:
    await jobs._ensure_group(fake_redis)
    await _leave_one_pending(fake_redis)
    settings = Settings(jobs_stream_max_len=_HARD_CAP)
    with (
        patch.object(jobs, "_MAXLEN", _SOFT_CAP),
        patch.object(jobs, "get_settings", return_value=settings),
    ):
        for i in range(_SOFT_CAP * 2):
            await jobs.enqueue(fake_redis, "topic", {"chat_id": str(i)})
        await fake_redis.xadd(jobs.JOBS_DLQ_STREAM, {"type": "topic", "payload": "{}"})
        await jobs.replay_dlq(fake_redis, count=10)
    # The pending entry and the queued backlog survive a replay.
    assert await fake_redis.xlen(jobs.JOBS_STREAM) == _SOFT_CAP * 2 + 2


async def test_process_entries_acks_an_entry_trimmed_before_reclaim(fake_redis: Any) -> None:
    """XAUTOCLAIM on Redis 6.2 returns a trimmed entry as (id, None)."""
    await jobs._ensure_group(fake_redis)
    calls: list[dict[str, Any]] = []

    async def handler(_settings: Settings, payload: dict[str, Any]) -> None:
        calls.append(payload)

    jobs.register("topic", handler)
    entry_id = await fake_redis.xadd(jobs.JOBS_STREAM, {"type": "topic", "payload": "{}"})
    await fake_redis.xreadgroup(jobs.JOBS_GROUP, "w", {jobs.JOBS_STREAM: ">"}, count=1)
    entries: list[tuple[str, dict[str, Any] | None]] = [("0-1", None), (entry_id, None)]
    await jobs._process_entries(fake_redis, Settings(), entries)
    assert calls == []
    pending = await fake_redis.xpending(jobs.JOBS_STREAM, jobs.JOBS_GROUP)
    assert pending["pending"] == 0

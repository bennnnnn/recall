"""Tests for the durable Redis-stream job queue."""

import asyncio
import json
from unittest.mock import AsyncMock, patch
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

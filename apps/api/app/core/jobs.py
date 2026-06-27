"""Durable background jobs on a Redis Stream.

Title generation, memory extraction, and history compression are enqueued to a
Redis Stream and processed by an in-process consumer (started in the app
lifespan). Because the stream is persisted in Redis, jobs survive a process
restart, and a crash mid-processing leaves the entry in the consumer group's
pending list — reclaimed via XAUTOCLAIM on the next startup. At-least-once.
"""

import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any, cast
from uuid import UUID

from redis.asyncio import Redis

from app.background import compaction, memory_extraction, suggestion_generation, topic_generation
from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

JOBS_STREAM = "recall:jobs"
JOBS_GROUP = "workers"
_MAXLEN = 10_000
_BLOCK_MS = 5_000
_BATCH = 10
_CLAIM_IDLE_MS = 60_000

JobHandler = Callable[[Settings, dict[str, Any]], Awaitable[None]]
_HANDLERS: dict[str, JobHandler] = {}


def register(job_type: str, handler: JobHandler) -> None:
    _HANDLERS[job_type] = handler


async def enqueue(redis: Redis, job_type: str, payload: dict[str, Any]) -> None:
    """Persist a job. Best-effort — a failure here never breaks the chat path."""
    try:
        await redis.xadd(
            JOBS_STREAM,
            {"type": job_type, "payload": json.dumps(payload)},
            maxlen=_MAXLEN,
            approximate=True,
        )
    except Exception:
        logger.exception("Failed to enqueue job type=%s", job_type)


# ── handlers ─────────────────────────────────────────────────────────────────


async def _handle_topic(settings: Settings, payload: dict[str, Any]) -> None:
    async with SessionLocal() as session:
        await topic_generation.generate_chat_title(
            session,
            settings,
            UUID(payload["chat_id"]),
            payload.get("user_message", ""),
            payload.get("assistant_message", ""),
        )


async def _handle_memory(settings: Settings, payload: dict[str, Any]) -> None:
    async with SessionLocal() as session:
        await memory_extraction.extract_and_store_memories(
            session,
            settings,
            user_id=UUID(payload["user_id"]),
            chat_id=UUID(payload["chat_id"]),
            transcript=payload["transcript"],
        )


async def _handle_compress(settings: Settings, payload: dict[str, Any]) -> None:
    await compaction.compress_chat_history(settings, UUID(payload["chat_id"]))


register("topic", _handle_topic)
register("memory", _handle_memory)
register("compress", _handle_compress)


async def _handle_suggestions(settings: Settings, payload: dict[str, Any]) -> None:
    async with SessionLocal() as session:
        await suggestion_generation.generate_suggestions(
            session, settings, UUID(payload["user_id"])
        )


register("suggestions", _handle_suggestions)


# ── worker ───────────────────────────────────────────────────────────────────


async def _dispatch(settings: Settings, fields: dict[str, Any]) -> None:
    job_type = fields.get("type")
    handler = _HANDLERS.get(job_type or "")
    if handler is None:
        logger.warning("No handler for job type=%s", job_type)
        return
    try:
        payload = json.loads(fields.get("payload") or "{}")
    except json.JSONDecodeError:
        logger.warning("Discarding job with bad payload type=%s", job_type)
        return
    await handler(settings, payload)


async def _process_entries(redis: Redis, settings: Settings, entries: list) -> None:
    for entry_id, fields in entries:
        try:
            await _dispatch(settings, cast(dict[str, Any], fields))
        except Exception:
            logger.exception("Job failed id=%s", entry_id)
        finally:
            # Best-effort jobs: ack regardless so a poison entry can't loop forever.
            try:
                await redis.xack(JOBS_STREAM, JOBS_GROUP, entry_id)
            except Exception:
                logger.debug("xack failed id=%s", entry_id, exc_info=True)


async def _ensure_group(redis: Redis) -> None:
    try:
        await redis.xgroup_create(JOBS_STREAM, JOBS_GROUP, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def _worker_loop(settings: Settings) -> None:
    redis = get_redis_client()
    consumer = f"worker-{os.getpid()}"

    try:
        await _ensure_group(redis)
    except Exception:
        logger.exception("Jobs worker could not init (Redis unavailable?); staying idle")
        return

    # Reclaim entries left pending by a previously crashed worker.
    try:
        claimed = await redis.xautoclaim(
            JOBS_STREAM, JOBS_GROUP, consumer, min_idle_time=_CLAIM_IDLE_MS, count=_BATCH
        )
        entries = claimed[1] if len(claimed) > 1 else []
        if entries:
            await _process_entries(redis, settings, entries)
    except Exception:
        logger.debug("xautoclaim failed", exc_info=True)

    while True:
        try:
            resp = cast(
                list[tuple[str, list[tuple[str, dict[str, Any]]]]],
                await redis.xreadgroup(
                    JOBS_GROUP, consumer, {JOBS_STREAM: ">"}, count=_BATCH, block=_BLOCK_MS
                ),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("xreadgroup failed; backing off", exc_info=True)
            await asyncio.sleep(2)
            continue

        if not resp:
            continue
        for _stream, entries in resp:
            await _process_entries(redis, settings, entries)


_worker_task: asyncio.Task | None = None


async def start_worker(settings: Settings) -> None:
    global _worker_task
    if _worker_task is not None:
        return
    _worker_task = asyncio.create_task(_worker_loop(settings))


async def stop_worker() -> None:
    global _worker_task
    if _worker_task is None:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    _worker_task = None

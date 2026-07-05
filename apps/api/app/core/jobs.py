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
import traceback
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from redis.asyncio import Redis

from app.background import (
    compaction,
    gmail_sync,
    memory_consolidation,
    memory_extraction,
    project_sync,
    suggestion_generation,
    todo_sync,
    topic_generation,
)
from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.services import transactional_email as transactional_email_service

logger = logging.getLogger(__name__)

JOBS_STREAM = "recall:jobs"
JOBS_DLQ_STREAM = "recall:jobs:dlq"
JOBS_GROUP = "workers"
_MAXLEN = 10_000
_DLQ_MAXLEN = 5_000
_BLOCK_MS = 5_000
_BATCH = 10
_CLAIM_IDLE_MS = 60_000
# Retry a transient failure a few times before moving to the DLQ. Background
# jobs are not latency-sensitive, so a short backoff in-process is cheaper and
# safer than dropping the job on the first provider/DB blip.
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_S = 2.0

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


async def enqueue_welcome_email(redis: Redis, user_id: UUID) -> None:
    await enqueue(redis, "transactional_email", {"kind": "welcome", "user_id": str(user_id)})


async def enqueue_purchase_receipt(
    redis: Redis,
    user_id: UUID | str,
    *,
    event_type: str,
    store: str | None = None,
    product_id: str | None = None,
    expiration: str | None = None,
) -> None:
    await enqueue(
        redis,
        "transactional_email",
        {
            "kind": "receipt",
            "user_id": str(user_id),
            "event_type": event_type,
            "store": store,
            "product_id": product_id,
            "expiration": expiration,
        },
    )


# ── handlers ─────────────────────────────────────────────────────────────────


async def _handle_topic(settings: Settings, payload: dict[str, Any]) -> None:
    await topic_generation.generate_chat_title(
        settings,
        UUID(payload["chat_id"]),
        payload.get("user_message", ""),
        payload.get("assistant_message", ""),
    )


async def _handle_memory(settings: Settings, payload: dict[str, Any]) -> None:
    await memory_extraction.extract_and_store_memories(
        settings,
        user_id=UUID(payload["user_id"]),
        chat_id=UUID(payload["chat_id"]),
        transcript=payload["transcript"],
    )


async def _handle_memory_consolidate(settings: Settings, payload: dict[str, Any]) -> None:
    await memory_consolidation.consolidate_user_memory_sections(
        settings,
        user_id=UUID(payload["user_id"]),
    )


async def _handle_todos(settings: Settings, payload: dict[str, Any]) -> None:
    await todo_sync.sync_todos_from_chat(
        settings,
        user_id=UUID(payload["user_id"]),
        chat_id=UUID(payload["chat_id"]),
        transcript=payload["transcript"],
    )


async def _handle_projects(settings: Settings, payload: dict[str, Any]) -> None:
    await project_sync.sync_projects_from_chat(
        settings,
        user_id=UUID(payload["user_id"]),
        chat_id=UUID(payload["chat_id"]),
        transcript=payload["transcript"],
    )


async def _handle_compress(settings: Settings, payload: dict[str, Any]) -> None:
    await compaction.compress_chat_history(settings, UUID(payload["chat_id"]))


register("topic", _handle_topic)
register("memory", _handle_memory)
register("memory_consolidate", _handle_memory_consolidate)
register("todos", _handle_todos)
register("projects", _handle_projects)
register("compress", _handle_compress)


async def _handle_suggestions(settings: Settings, payload: dict[str, Any]) -> None:
    await suggestion_generation.generate_suggestions(
        settings,
        UUID(payload["user_id"]),
    )


register("suggestions", _handle_suggestions)


async def _handle_gmail_sync(settings: Settings, payload: dict[str, Any]) -> None:
    async with SessionLocal() as session:
        await gmail_sync.sync_gmail_for_user(
            session,
            settings,
            user_id=UUID(payload["user_id"]),
        )


register("gmail_sync", _handle_gmail_sync)


async def _handle_transactional_email(settings: Settings, payload: dict[str, Any]) -> None:
    """Best-effort outbound email (welcome / receipts). Never raises into chat."""
    from app.repositories import users as users_repo

    async with SessionLocal() as session:
        user = await users_repo.get_by_id(session, UUID(payload["user_id"]))
    if user is None:
        logger.warning("transactional_email: user not found id=%s", payload.get("user_id"))
        return
    kind = payload.get("kind")
    try:
        if kind == "welcome":
            await transactional_email_service.send_welcome(settings, user)
        elif kind == "receipt":
            await transactional_email_service.send_purchase_receipt(
                settings,
                user,
                event_type=str(payload.get("event_type") or ""),
                store=payload.get("store"),
                product_id=payload.get("product_id"),
                expiration=payload.get("expiration"),
            )
        else:
            logger.warning("transactional_email: unknown kind=%s", kind)
    except Exception:
        logger.exception(
            "transactional_email job failed kind=%s user=%s", kind, payload.get("user_id")
        )


register("transactional_email", _handle_transactional_email)


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


async def _move_to_dlq(
    redis: Redis,
    entry_id: str,
    fields: dict[str, Any],
    error: str,
) -> None:
    """Persist failed jobs for inspection/replay without blocking the worker."""
    try:
        await redis.xadd(
            JOBS_DLQ_STREAM,
            {
                "original_id": entry_id,
                "type": fields.get("type", ""),
                "payload": fields.get("payload", "{}"),
                "error": error[:2000],
                "failed_at": datetime.now(UTC).isoformat(),
            },
            maxlen=_DLQ_MAXLEN,
            approximate=True,
        )
    except Exception:
        logger.debug("Failed to write job to DLQ id=%s", entry_id, exc_info=True)


async def _process_entries(redis: Redis, settings: Settings, entries: list) -> None:
    for entry_id, fields in entries:
        cast_fields = cast(dict[str, Any], fields)
        try:
            for attempt in range(1, _MAX_ATTEMPTS + 1):
                try:
                    await _dispatch(settings, cast_fields)
                    break
                except Exception:
                    if attempt < _MAX_ATTEMPTS:
                        logger.warning(
                            "Job failed attempt=%s/%s id=%s; retrying",
                            attempt,
                            _MAX_ATTEMPTS,
                            entry_id,
                        )
                        await asyncio.sleep(_RETRY_BACKOFF_S * attempt)
                    else:
                        logger.exception(
                            "Job failed after %s attempts id=%s", _MAX_ATTEMPTS, entry_id
                        )
                        await _move_to_dlq(
                            redis, entry_id, cast_fields, traceback.format_exc(limit=8)
                        )
        finally:
            # Best-effort jobs: ack regardless so a poison entry can't loop forever.
            # Retry already happened above; the DLQ preserves the failed payload.
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


# ── DLQ inspection / replay ──────────────────────────────────────────────────


async def list_dlq(redis: Redis, *, count: int = 50) -> list[dict[str, Any]]:
    """Return up to `count` recent DLQ entries for inspection."""
    resp = await redis.xrevrange(JOBS_DLQ_STREAM, count=count)
    out: list[dict[str, Any]] = []
    if not resp:
        return out
    for entry in resp:
        entry_id, fields = entry  # type: ignore[misc]
        f = cast(dict[str, Any], fields)
        out.append(
            {
                "id": entry_id,
                "original_id": f.get("original_id", ""),
                "type": f.get("type", ""),
                "payload": f.get("payload", "{}"),
                "error": f.get("error", ""),
                "failed_at": f.get("failed_at", ""),
            }
        )
    return out


async def replay_dlq(redis: Redis, *, count: int = 50, delete: bool = True) -> int:
    """Re-enqueue up to `count` DLQ entries back onto the jobs stream.

    Returns the number of entries replayed. When ``delete`` is True (default),
    replayed entries are trimmed from the DLQ so they aren't replayed twice.
    """
    entries = await list_dlq(redis, count=count)
    replayed = 0
    for entry in entries:
        job_type = entry.get("type") or ""
        if not job_type:
            continue
        try:
            await redis.xadd(
                JOBS_STREAM,
                {"type": job_type, "payload": entry.get("payload", "{}")},
                maxlen=_MAXLEN,
                approximate=True,
            )
            if delete:
                await redis.xdel(JOBS_DLQ_STREAM, entry["id"])
            replayed += 1
        except Exception:
            logger.exception("Failed to replay DLQ entry id=%s", entry.get("id"))
    return replayed

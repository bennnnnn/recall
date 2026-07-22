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
import socket
import time
import traceback
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from redis.asyncio import Redis

from app.background import (
    attachment_indexing,
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
from app.core.redis import get_jobs_redis_client, get_redis_client
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
# Idempotency: SET NX before dispatch so reclaim/duplicate enqueue cannot
# double-apply side effects (duplicate todos, welcome emails, …). Released on
# permanent failure so a later re-enqueue can retry; success keeps the key.
_JOB_DONE_PREFIX = "jobdone:"
_JOB_DONE_TTL_SECONDS = 86_400


class JobDiscardError(Exception):
    """Non-retryable job — move to DLQ and ack (unknown type / bad payload)."""


# Observe queue health: report DLQ depth + pending entries to Sentry every
# _METRICS_INTERVAL_S, and capture a warning when either crosses its threshold
# so a backed-up queue or growing DLQ doesn't go unnoticed (the admin DLQ
# endpoint is dev-only, so prod had no signal before).
_METRICS_INTERVAL_S = 300
_DLQ_ALERT_THRESHOLD = 20
_PENDING_ALERT_THRESHOLD = 50
# Retry a transient failure a few times before moving to the DLQ. Background
# jobs are not latency-sensitive, so a short backoff in-process is cheaper and
# safer than dropping the job on the first provider/DB blip.
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_S = 2.0
# How stale the worker-loop heartbeat can get before is_worker_alive() reports
# the worker as dead even though its task hasn't crashed. Generous on purpose:
# comfortably longer than one full retry-backoff cycle in _process_one_entry
# (up to roughly _MAX_ATTEMPTS * _RETRY_BACKOFF_S * _MAX_ATTEMPTS seconds) plus
# a slow handler; heartbeat is touched per attempt so a concurrent batch of
# LLM jobs does not false-positive as "stuck".
_HEARTBEAT_STALE_THRESHOLD_S = 120.0

JobHandler = Callable[[Settings, dict[str, Any]], Awaitable[None]]
_HANDLERS: dict[str, JobHandler] = {}


def _capture_sentry_exception(message: str) -> None:
    """Report a best-effort failure to Sentry without raising if it's absent.

    Job enqueue/DLQ paths must never raise into the chat request, but silent
    failures should be observable in production. Falls back to a no-op when
    sentry-sdk isn't installed or initialized.
    """
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(Exception(message))
    except Exception:  # intentional swallow: never raise into chat
        logger.debug("sentry capture failed for %s", message, exc_info=True)


def register(job_type: str, handler: JobHandler) -> None:
    _HANDLERS[job_type] = handler


def job_done_key(dedupe_key: str) -> str:
    return f"{_JOB_DONE_PREFIX}{dedupe_key}"


async def enqueue(
    redis: Redis,
    job_type: str,
    payload: dict[str, Any],
    *,
    dedupe_key: str | None = None,
) -> None:
    """Persist a job. Best-effort — a failure here never breaks the chat path.

    A failed enqueue is logged AND reported to Sentry (when initialized) so
    silent job loss is observable — otherwise titles/memory/compression can
    quietly stop running with no signal.

    ``dedupe_key``, when set, is stored on the stream entry so the worker can
    skip redelivery / duplicate enqueue after a successful (or in-flight)
    run of the same logical job.
    """
    try:
        fields: dict[str, str] = {"type": job_type, "payload": json.dumps(payload)}
        if dedupe_key:
            fields["dedupe_key"] = dedupe_key
        # redis-py stubs type xadd fields as an invariant EncodedT dict; cast.
        await redis.xadd(JOBS_STREAM, cast(Any, fields))
        await _trim_jobs_stream(redis)
    except Exception:
        logger.exception("Failed to enqueue job type=%s", job_type)
        _capture_sentry_exception(f"enqueue_failed:{job_type}")


async def _trim_jobs_stream(redis: Redis) -> None:
    """Trim the jobs stream without dropping consumer-group pending entries.

    Prefer MINID at the oldest pending id so approximate MAXLEN cannot silently
    erase unacked work. Fall back to MAXLEN when the group has no pending list.
    """
    try:
        pending = await redis.xpending(JOBS_STREAM, JOBS_GROUP)
        min_id: str | None = None
        if isinstance(pending, dict):
            raw = pending.get("min")
            if raw:
                min_id = str(raw)
        elif isinstance(pending, list | tuple) and len(pending) >= 2 and pending[0]:
            # redis-py may return (count, min, max, consumers)
            min_id = str(pending[1]) if pending[1] else None
        if min_id:
            await redis.xtrim(JOBS_STREAM, minid=min_id, approximate=True)
        else:
            await redis.xtrim(JOBS_STREAM, maxlen=_MAXLEN, approximate=True)
    except Exception:
        logger.debug("jobs stream trim skipped", exc_info=True)


async def enqueue_welcome_email(redis: Redis, user_id: UUID) -> None:
    await enqueue(
        redis,
        "transactional_email",
        {"kind": "welcome", "user_id": str(user_id)},
        dedupe_key=f"welcome:{user_id}",
    )


async def enqueue_purchase_receipt(
    redis: Redis,
    user_id: UUID | str,
    *,
    event_type: str,
    store: str | None = None,
    product_id: str | None = None,
    expiration: str | None = None,
) -> None:
    uid = str(user_id)
    await enqueue(
        redis,
        "transactional_email",
        {
            "kind": "receipt",
            "user_id": uid,
            "event_type": event_type,
            "store": store,
            "product_id": product_id,
            "expiration": expiration,
        },
        dedupe_key=f"receipt:{uid}:{event_type}:{product_id or ''}",
    )


# ── handlers ─────────────────────────────────────────────────────────────────


async def _handle_topic(settings: Settings, payload: dict[str, Any]) -> None:
    await topic_generation.generate_chat_title(
        settings,
        UUID(payload["chat_id"]),
        payload.get("user_message", ""),
        payload.get("assistant_message", ""),
    )


_MEMORY_LOCK_MAX_RETRIES = 3


async def _handle_memory(settings: Settings, payload: dict[str, Any]) -> None:
    outcome = await memory_extraction.extract_and_store_memories(
        settings,
        user_id=UUID(payload["user_id"]),
        chat_id=UUID(payload["chat_id"]),
        transcript=payload["transcript"],
    )
    if outcome != "skipped_lock":
        return
    # Write lock busy (consolidation or sibling extraction). Re-enqueue a
    # bounded number of times so the turn's memory isn't silently dropped.
    try:
        retries = int(payload.get("lock_retries") or 0)
    except (TypeError, ValueError):
        retries = 0
    if retries >= _MEMORY_LOCK_MAX_RETRIES:
        logger.warning(
            "Memory extraction dropped after lock retries user_id=%s chat_id=%s",
            payload.get("user_id"),
            payload.get("chat_id"),
        )
        return

    await enqueue(
        get_redis_client(),
        "memory",
        {
            "user_id": payload["user_id"],
            "chat_id": payload["chat_id"],
            "transcript": payload["transcript"],
            "lock_retries": retries + 1,
        },
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
register("attachment_index", attachment_indexing.index_attachment_job)


# ── worker ───────────────────────────────────────────────────────────────────


async def _dispatch(settings: Settings, fields: dict[str, Any]) -> None:
    job_type = fields.get("type")
    handler = _HANDLERS.get(job_type or "")
    if handler is None:
        raise JobDiscardError(f"unknown job type={job_type!r}")
    try:
        payload = json.loads(fields.get("payload") or "{}")
    except json.JSONDecodeError as exc:
        raise JobDiscardError(f"bad payload type={job_type!r}") from exc
    await handler(settings, payload)


async def _move_to_dlq(
    redis: Redis,
    entry_id: str,
    fields: dict[str, Any],
    error: str,
) -> None:
    """Persist failed jobs for inspection/replay without blocking the worker."""
    try:
        dlq_fields: dict[str, str] = {
            "original_id": entry_id,
            "type": str(fields.get("type", "")),
            "payload": str(fields.get("payload", "{}")),
            "error": error[:2000],
            "failed_at": datetime.now(UTC).isoformat(),
        }
        dedupe_key = fields.get("dedupe_key")
        if dedupe_key:
            dlq_fields["dedupe_key"] = str(dedupe_key)
        await redis.xadd(
            JOBS_DLQ_STREAM,
            cast(Any, dlq_fields),
            maxlen=_DLQ_MAXLEN,
            approximate=True,
        )
    except Exception:
        logger.debug("Failed to write job to DLQ id=%s", entry_id, exc_info=True)
        _capture_sentry_exception("dlq_write_failed")


async def _claim_dedupe(redis: Redis, dedupe_key: str | None) -> bool:
    """Return True if this worker should run the job (or there is no dedupe)."""
    if not dedupe_key:
        return True
    try:
        claimed = await redis.set(
            job_done_key(dedupe_key),
            "1",
            ex=_JOB_DONE_TTL_SECONDS,
            nx=True,
        )
    except Exception:
        # Fail open: never drop work because Redis SET blipped.
        logger.debug("job dedupe claim failed key=%s", dedupe_key, exc_info=True)
        return True
    return bool(claimed)


async def _release_dedupe(redis: Redis, dedupe_key: str | None) -> None:
    if not dedupe_key:
        return
    try:
        await redis.delete(job_done_key(dedupe_key))
    except Exception:
        logger.debug("job dedupe release failed key=%s", dedupe_key, exc_info=True)


async def _process_one_entry(
    redis: Redis,
    settings: Settings,
    entry_id: str,
    fields: dict[str, Any],
) -> None:
    """Dispatch + retry + ack a single stream entry (safe to run concurrently)."""
    # Per-entry (and per-attempt) so a long LLM timeout / gmail batch cannot
    # trip the 120s stale health check while this worker is still healthy.
    _touch_heartbeat()
    dedupe_key = fields.get("dedupe_key") or None
    if isinstance(dedupe_key, str):
        dedupe_key = dedupe_key.strip() or None
    else:
        dedupe_key = None
    try:
        if not await _claim_dedupe(redis, dedupe_key):
            logger.info(
                "Skipping already-processed job id=%s dedupe_key=%s",
                entry_id,
                dedupe_key,
            )
            return
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            _touch_heartbeat()
            try:
                await _dispatch(settings, fields)
                break
            except JobDiscardError as exc:
                logger.warning("Discarding job id=%s: %s", entry_id, exc)
                await _release_dedupe(redis, dedupe_key)
                await _move_to_dlq(redis, entry_id, fields, str(exc))
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
                    logger.exception("Job failed after %s attempts id=%s", _MAX_ATTEMPTS, entry_id)
                    # Release so a future re-enqueue / DLQ replay can retry.
                    await _release_dedupe(redis, dedupe_key)
                    await _move_to_dlq(redis, entry_id, fields, traceback.format_exc(limit=8))
    finally:
        # Best-effort jobs: ack regardless so a poison entry can't loop forever.
        # Retry already happened above; the DLQ preserves the failed payload.
        try:
            await redis.xack(JOBS_STREAM, JOBS_GROUP, entry_id)
        except Exception:
            logger.debug("xack failed id=%s", entry_id, exc_info=True)


async def _process_entries(
    redis: Redis, settings: Settings, entries: list[tuple[str, dict[str, Any]]]
) -> None:
    """Process a stream batch with bounded concurrency.

    LLM jobs (memory/todos/…) can take tens of seconds; awaiting them
    sequentially head-of-line-blocks fast jobs (compress/topic). A semaphore
    lets up to ``settings.jobs_worker_concurrency`` entries run at once while
    still capping provider/DB load per worker process.
    """
    if not entries:
        return
    concurrency = max(1, int(settings.jobs_worker_concurrency))
    if concurrency == 1 or len(entries) == 1:
        for entry_id, fields in entries:
            await _process_one_entry(redis, settings, entry_id, fields)
        _touch_heartbeat()
        return

    sem = asyncio.Semaphore(concurrency)

    async def _run(entry_id: str, fields: dict[str, Any]) -> None:
        async with sem:
            await _process_one_entry(redis, settings, entry_id, fields)

    await asyncio.gather(*(_run(entry_id, fields) for entry_id, fields in entries))
    _touch_heartbeat()


async def _ensure_group(redis: Redis) -> None:
    try:
        await redis.xgroup_create(JOBS_STREAM, JOBS_GROUP, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def _touch_heartbeat() -> None:
    global _last_heartbeat
    _last_heartbeat = time.monotonic()


async def _reclaim_pending_jobs(redis: Redis, settings: Settings, consumer: str) -> None:
    """Reclaim entries left pending by a crashed/slow worker via XAUTOCLAIM.

    Called both on startup and periodically from the live worker loop. A
    crashed worker leaves its in-flight entries in the consumer group's
    pending list; XAUTOCLAIM transfers them to this consumer once they've
    been idle for ``_CLAIM_IDLE_MS``. Without periodic reclaim, a mid-run
    crash would leave jobs stuck until the next worker startup.
    """
    try:
        claimed = await redis.xautoclaim(
            JOBS_STREAM, JOBS_GROUP, consumer, min_idle_time=_CLAIM_IDLE_MS, count=_BATCH
        )
        entries = claimed[1] if len(claimed) > 1 else []
        if entries:
            await _process_entries(redis, settings, entries)
    except Exception:
        logger.debug("xautoclaim failed", exc_info=True)


def _consumer_name() -> str:
    """Unique per container — Docker replicas all see PID 1 without hostname."""
    host = (socket.gethostname() or "host").replace(" ", "-")[:64]
    return f"worker-{host}-{os.getpid()}"


async def _worker_loop(settings: Settings) -> None:
    # Longer socket_timeout than request-path Redis — XREADGROUP blocks 5s.
    redis = get_jobs_redis_client()
    consumer = _consumer_name()

    _touch_heartbeat()

    try:
        await _ensure_group(redis)
    except Exception:
        logger.exception("Jobs worker could not init (Redis unavailable?); staying idle")
        return

    # Reclaim entries left pending by a previously crashed worker.
    await _reclaim_pending_jobs(redis, settings, consumer)

    last_metrics_at = 0.0
    # Reclaim periodically, not just on startup: without this, a worker that
    # crashes mid-job while the system is running leaves the entry pending
    # until the *next* worker startup (could be hours/days). Reclaiming on a
    # cadence in the live loop means a crashed worker's stuck entries are
    # picked up by a live peer within ~_CLAIM_IDLE_MS + _RECLAIM_INTERVAL_S.
    last_reclaim_at = asyncio.get_event_loop().time()
    _RECLAIM_INTERVAL_S = 30.0
    while True:
        _touch_heartbeat()
        now = asyncio.get_event_loop().time()
        if now - last_metrics_at >= _METRICS_INTERVAL_S:
            last_metrics_at = now
            await report_queue_metrics(redis)
        if now - last_reclaim_at >= _RECLAIM_INTERVAL_S:
            last_reclaim_at = now
            await _reclaim_pending_jobs(redis, settings, consumer)
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
            _touch_heartbeat()


_worker_task: asyncio.Task[None] | None = None
_last_heartbeat: float = 0.0


def is_worker_alive() -> bool:
    """True when the job-loop background task exists, hasn't finished, and is
    still checking in.

    Used by the worker health endpoint so Fly can detect + restart a stuck
    worker (blocked event loop, deadlocked consumer) that hasn't crashed. A
    genuinely hung task (e.g. a handler awaiting something that never
    resolves) never becomes done(), so we also track a heartbeat that
    `_worker_loop` refreshes on every idle-poll iteration and after each
    processed batch; if it goes stale while the task is still "running", the
    worker is treated as dead. `_last_heartbeat` being unset (0.0) means the
    loop hasn't had a chance to run its first iteration yet, which the
    task.done() check already covers correctly, so we don't flag staleness
    in that window.
    """
    if _worker_task is None or _worker_task.done():
        return False
    if _last_heartbeat == 0.0:
        return True
    return time.monotonic() - _last_heartbeat < _HEARTBEAT_STALE_THRESHOLD_S


async def start_worker(settings: Settings) -> None:
    global _worker_task
    if _worker_task is not None:
        return
    _worker_task = asyncio.create_task(_worker_loop(settings))


async def stop_worker() -> None:
    global _worker_task, _last_heartbeat
    if _worker_task is None:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    _worker_task = None
    _last_heartbeat = 0.0


# ── DLQ inspection / replay ──────────────────────────────────────────────────


async def collect_queue_metrics(redis: Redis) -> dict[str, int]:
    """Return DLQ depth + jobs-stream pending count for observability.

    Both are best-effort: a Redis error yields 0 rather than raising, so the
    worker loop never breaks on a metrics collection blip.
    """
    try:
        dlq_depth = int(await redis.xlen(JOBS_DLQ_STREAM))
    except Exception:
        dlq_depth = 0
    try:
        pending = await redis.xpending(JOBS_STREAM, JOBS_GROUP)
        # xpending summary returns [count, min_id, max_id, [[consumer, count], ...]]
        pending_count = int(cast(list[Any], pending)[0]) if pending else 0
    except Exception:
        pending_count = 0
    return {"dlq_depth": dlq_depth, "pending_entries": pending_count}


async def report_queue_metrics(redis: Redis) -> dict[str, int]:
    """Collect queue metrics and report them to Sentry (when initialized).

    A breadcrumb is added every call (cheap, visible in event context), and a
    warning-level message is captured when DLQ depth or pending entries cross
    their threshold — so prod gets an actionable alert instead of silent
    queue growth. Falls back to a no-op when sentry-sdk is absent.
    """
    metrics = await collect_queue_metrics(redis)
    try:
        import sentry_sdk

        sentry_sdk.add_breadcrumb(
            category="jobs.queue",
            message=(
                f"queue metrics: dlq={metrics['dlq_depth']} pending={metrics['pending_entries']}"
            ),
            level="info",
            data=metrics,
        )
        if metrics["dlq_depth"] >= _DLQ_ALERT_THRESHOLD:
            sentry_sdk.capture_message(
                f"Jobs DLQ depth {metrics['dlq_depth']} >= {_DLQ_ALERT_THRESHOLD}",
                level="warning",
            )
        if metrics["pending_entries"] >= _PENDING_ALERT_THRESHOLD:
            sentry_sdk.capture_message(
                f"Jobs pending entries {metrics['pending_entries']} >= {_PENDING_ALERT_THRESHOLD}",
                level="warning",
            )
    except Exception:
        logger.debug("queue metrics report failed", exc_info=True)
    return metrics


async def list_dlq(redis: Redis, *, count: int = 50) -> list[dict[str, Any]]:
    """Return up to `count` recent DLQ entries for inspection."""
    resp = await redis.xrevrange(JOBS_DLQ_STREAM, count=count)
    out: list[dict[str, Any]] = []
    if not resp:
        return out
    for entry in resp:
        entry_id, fields = entry
        f = cast(dict[str, Any], fields)
        out.append(
            {
                "id": entry_id,
                "original_id": f.get("original_id", ""),
                "type": f.get("type", ""),
                "payload": f.get("payload", "{}"),
                "error": f.get("error", ""),
                "failed_at": f.get("failed_at", ""),
                "dedupe_key": f.get("dedupe_key", ""),
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
            fields: dict[str, str] = {
                "type": job_type,
                "payload": str(entry.get("payload", "{}")),
            }
            dedupe_key = entry.get("dedupe_key") or ""
            if dedupe_key:
                fields["dedupe_key"] = str(dedupe_key)
            await redis.xadd(
                JOBS_STREAM,
                cast(Any, fields),
                maxlen=_MAXLEN,
                approximate=True,
            )
            if delete:
                await redis.xdel(JOBS_DLQ_STREAM, entry["id"])
            replayed += 1
        except Exception:
            logger.exception("Failed to replay DLQ entry id=%s", entry.get("id"))
    return replayed

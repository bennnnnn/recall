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
from collections.abc import Awaitable, Callable, Collection
from datetime import UTC, datetime
from typing import Any, TypedDict, cast
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.redis import get_jobs_redis_client

logger = logging.getLogger(__name__)

JOBS_STREAM = "recall:jobs"
JOBS_DLQ_STREAM = "recall:jobs:dlq"
JOBS_GROUP = "workers"
# Soft cap, applied only while nothing is pending (see _trim_jobs_stream).
_MAXLEN = 10_000
_DLQ_MAXLEN = 5_000
_BLOCK_MS = 5_000
_BATCH = 10
_CLAIM_IDLE_MS = 60_000
# Idempotency: SET NX before dispatch so reclaim/duplicate enqueue cannot
# double-apply side effects (duplicate todos, welcome emails, …).
# In-flight value is _DEDUPE_RUNNING with a short TTL; success overwrites with
# _DEDUPE_DONE for 24h. A reclaim that loses NX must not xack while the key
# is still running — that was a guaranteed drop: reclaim idle is 60s and the
# running TTL is 300s, so skip+xack acknowledged the PEL entry forever.
_JOB_DONE_PREFIX = "jobdone:"
_JOB_DONE_TTL_SECONDS = 86_400
# Covers a normal handler (LLM / index batch). A keepalive refreshes this
# while the handler runs so a slow index does not expire and double-run.
# After a crash, the key expires and the next XAUTOCLAIM can NX-succeed.
_JOB_DONE_CLAIM_TTL_SECONDS = 300
_DEDUPE_RUNNING = "1"
_DEDUPE_DONE = "done"


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
# the worker as dead even though its task hasn't crashed. While a batch runs,
# a ticker touches the heartbeat every _JOB_HEARTBEAT_TICK_S, so a long but
# healthy job (OCR index, LLM call + fallback) does not read as dead. That is
# safe because every attempt has a deadline (``job_timeout_seconds``); the
# heartbeat now goes stale only when the event loop itself is blocked or the
# loop task is wedged outside a job.
_HEARTBEAT_STALE_THRESHOLD_S = 120.0
_JOB_HEARTBEAT_TICK_S = 15.0
# An entry delivered this many times without being acked keeps killing the
# process that runs it (OOM, segfault) or never finishes. Reclaim moves it to
# the DLQ instead of starting the crash loop again.
MAX_JOB_DELIVERIES = 5

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
        # The hard ceiling rides on XADD itself (no extra round trip) so the
        # stream stays bounded even while a stale pending entry pins the
        # MINID trim below — e.g. a worker that died mid-job and is down.
        hard_cap = _hard_maxlen()
        if hard_cap is None:
            await redis.xadd(JOBS_STREAM, cast(Any, fields))
        else:
            await redis.xadd(JOBS_STREAM, cast(Any, fields), maxlen=hard_cap, approximate=True)
        await _trim_jobs_stream(redis)
    except Exception:
        logger.exception("Failed to enqueue job type=%s", job_type)
        _capture_sentry_exception(f"enqueue_failed:{job_type}")


def _hard_maxlen() -> int | None:
    """Ceiling on the jobs stream regardless of pending entries (None = off).

    Never below the soft cap, so it only bites when a stale pending entry has
    disabled the soft trim. Dropping the oldest jobs past it is the price of
    keeping Redis (shared with quota, auth revocation and rate limits) alive.
    """
    configured = get_settings().jobs_stream_max_len
    if configured <= 0:
        return None
    return max(configured, _MAXLEN)


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


async def _claim_dedupe(
    redis: Redis, dedupe_key: str | None, *, ttl: int = _JOB_DONE_CLAIM_TTL_SECONDS
) -> bool:
    """Return True if this worker should run the job (or there is no dedupe).

    Uses a short TTL so a worker that crashes mid-handler doesn't pin the
    key for 24h — the claim expires and a later reclaim can NX-succeed.
    """
    if not dedupe_key:
        return True
    try:
        claimed = await redis.set(
            job_done_key(dedupe_key),
            _DEDUPE_RUNNING,
            ex=ttl,
            nx=True,
        )
    except Exception:
        # Fail open: never drop work because Redis SET blipped.
        logger.debug("job dedupe claim failed key=%s", dedupe_key, exc_info=True)
        return True
    return bool(claimed)


async def _dedupe_is_complete(redis: Redis, dedupe_key: str | None) -> bool:
    """True when a later duplicate should skip and ack (handler already succeeded)."""
    if not dedupe_key:
        return False
    key = job_done_key(dedupe_key)
    try:
        value = await redis.get(key)
        if value == _DEDUPE_DONE:
            return True
        if value != _DEDUPE_RUNNING:
            return False
        ttl = await redis.ttl(key)
        # Pre-fix success only EXPIREd "1" to 24h. Treat a long TTL as done so
        # a rolling deploy does not leave those duplicates pending for a day.
        return isinstance(ttl, int) and ttl > _JOB_DONE_CLAIM_TTL_SECONDS
    except Exception:
        logger.debug("job dedupe state read failed key=%s", dedupe_key, exc_info=True)
        return False


async def _extend_dedupe(redis: Redis, dedupe_key: str | None) -> None:
    """Mark the logical job done so later duplicates skip and ack."""
    if not dedupe_key:
        return
    try:
        await redis.set(
            job_done_key(dedupe_key),
            _DEDUPE_DONE,
            ex=_JOB_DONE_TTL_SECONDS,
        )
    except Exception:
        logger.debug("job dedupe extend failed key=%s", dedupe_key, exc_info=True)


async def _refresh_running_claim(redis: Redis, dedupe_key: str | None) -> None:
    """Keep an in-flight claim alive across a slow handler."""
    if not dedupe_key:
        return
    key = job_done_key(dedupe_key)
    try:
        current = await redis.get(key)
        if current == _DEDUPE_RUNNING:
            await redis.expire(key, _JOB_DONE_CLAIM_TTL_SECONDS)
    except Exception:
        logger.debug("job dedupe refresh failed key=%s", dedupe_key, exc_info=True)


async def _refresh_running_claim_loop(redis: Redis, dedupe_key: str) -> None:
    interval = max(1, _JOB_DONE_CLAIM_TTL_SECONDS // 2)
    while True:
        await asyncio.sleep(interval)
        await _refresh_running_claim(redis, dedupe_key)


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
    # Per-entry (and per-attempt) so a long LLM timeout / index batch cannot
    # trip the 120s stale health check while this worker is still healthy.
    _touch_heartbeat()
    dedupe_key = fields.get("dedupe_key") or None
    if isinstance(dedupe_key, str):
        dedupe_key = dedupe_key.strip() or None
    else:
        dedupe_key = None
    should_ack = True
    keepalive: asyncio.Task[None] | None = None
    try:
        if not await _claim_dedupe(redis, dedupe_key):
            if await _dedupe_is_complete(redis, dedupe_key):
                logger.info(
                    "Skipping already-processed job id=%s dedupe_key=%s",
                    entry_id,
                    dedupe_key,
                )
                return
            logger.info(
                "Skipping in-flight job id=%s dedupe_key=%s",
                entry_id,
                dedupe_key,
            )
            should_ack = False
            return
        if dedupe_key:
            keepalive = asyncio.create_task(_refresh_running_claim_loop(redis, dedupe_key))
        job_timeout = _job_timeout(settings)
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            _touch_heartbeat()
            await _refresh_running_claim(redis, dedupe_key)
            deadline = asyncio.timeout(job_timeout)
            try:
                async with deadline:
                    await _dispatch(settings, fields)
                # Success — overwrite the short running claim so a later
                # duplicate enqueue skips and acks. Crash before this line
                # leaves the running TTL; reclaim must not xack until it
                # expires (or this keepalive dies with the worker).
                await _extend_dedupe(redis, dedupe_key)
                break
            except JobDiscardError as exc:
                logger.warning("Discarding job id=%s: %s", entry_id, exc)
                await _release_dedupe(redis, dedupe_key)
                await _move_to_dlq(redis, entry_id, fields, str(exc))
                break
            except Exception as exc:
                if isinstance(exc, TimeoutError) and deadline.expired():
                    # Not retried: a handler that ran out its whole deadline
                    # would likely do it again, holding the batch each time.
                    logger.error(
                        "Job id=%s type=%s exceeded %ss; moving to DLQ",
                        entry_id,
                        fields.get("type"),
                        job_timeout,
                    )
                    _capture_sentry_exception(f"job_timeout:{fields.get('type')}")
                    await _release_dedupe(redis, dedupe_key)
                    await _move_to_dlq(redis, entry_id, fields, f"timed out after {job_timeout}s")
                    break
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
    except asyncio.CancelledError:
        # The worker is stopping (deploy, SIGTERM) mid-job. Leave the entry
        # pending so a live worker's reclaim runs it again; acking here
        # dropped every in-flight job on each deploy.
        should_ack = False
        await _release_dedupe(redis, dedupe_key)
        raise
    finally:
        if keepalive is not None:
            keepalive.cancel()
            try:
                await keepalive
            except asyncio.CancelledError:
                pass
        if should_ack:
            # Best-effort jobs: ack after we owned the run so a poison entry
            # can't loop forever. Do not ack an in-flight duplicate — the
            # PEL entry must survive until the running TTL expires.
            try:
                await redis.xack(JOBS_STREAM, JOBS_GROUP, entry_id)
            except Exception:
                logger.debug("xack failed id=%s", entry_id, exc_info=True)


async def _ack_trimmed_entries(
    redis: Redis, entries: list[tuple[str, dict[str, Any] | None]]
) -> list[tuple[str, dict[str, Any]]]:
    """Drop entries the stream cap trimmed before they ran; ack them.

    XAUTOCLAIM on Redis 6.2 returns a deleted entry as ``(id, None)`` and
    leaves it pending. Acking removes it so it cannot fail every reclaim.
    """
    live: list[tuple[str, dict[str, Any]]] = []
    for entry_id, fields in entries:
        if fields is not None:
            live.append((entry_id, fields))
            continue
        if not entry_id:
            continue
        logger.warning("Job id=%s was trimmed from the stream before it ran", entry_id)
        try:
            await redis.xack(JOBS_STREAM, JOBS_GROUP, entry_id)
        except Exception:
            logger.debug("xack of trimmed entry failed id=%s", entry_id, exc_info=True)
    return live


async def _process_entries(
    redis: Redis,
    settings: Settings,
    entries: list[tuple[str, dict[str, Any] | None]] | list[tuple[str, dict[str, Any]]],
) -> None:
    """Process a stream batch with bounded concurrency.

    LLM jobs (memory/todos/…) can take tens of seconds; awaiting them
    sequentially head-of-line-blocks fast jobs (compress/topic). A semaphore
    lets up to ``settings.jobs_worker_concurrency`` entries run at once while
    still capping provider/DB load per worker process.
    """
    if not entries:
        return
    live = await _ack_trimmed_entries(redis, cast(list[tuple[str, dict[str, Any] | None]], entries))
    if not live:
        return
    ticker = _HeartbeatTicker()
    ticker.start()
    try:
        concurrency = max(1, int(settings.jobs_worker_concurrency))
        if concurrency == 1 or len(live) == 1:
            for entry_id, fields in live:
                await _process_one_entry(redis, settings, entry_id, fields)
            return

        sem = asyncio.Semaphore(concurrency)

        async def _run(entry_id: str, fields: dict[str, Any]) -> None:
            async with sem:
                await _process_one_entry(redis, settings, entry_id, fields)

        await asyncio.gather(*(_run(entry_id, fields) for entry_id, fields in live))
    finally:
        ticker.stop()
        _touch_heartbeat()


class _HeartbeatTicker:
    """Keep the liveness heartbeat fresh while deadline-bounded jobs run.

    A loop timer rather than a sleeping task: it stops with one call (no task
    cancellation to get wrong) and only fires while the event loop is free,
    so a blocked loop still goes stale.
    """

    def __init__(self) -> None:
        self._handle: asyncio.TimerHandle | None = None

    def start(self) -> None:
        self._tick()

    def _tick(self) -> None:
        _touch_heartbeat()
        loop = asyncio.get_running_loop()
        self._handle = loop.call_later(_JOB_HEARTBEAT_TICK_S, self._tick)

    def stop(self) -> None:
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None


def _job_timeout(settings: Settings) -> float | None:
    """Per-attempt handler deadline in seconds (None = unbounded, tests only)."""
    timeout = float(settings.job_timeout_seconds)
    return timeout if timeout > 0 else None


async def _times_delivered(redis: Redis, entry_id: str) -> int:
    try:
        rows = await redis.xpending_range(
            JOBS_STREAM, JOBS_GROUP, min=entry_id, max=entry_id, count=1
        )
    except Exception:
        logger.debug("xpending_range failed id=%s", entry_id, exc_info=True)
        return 0
    if not rows:
        return 0
    try:
        return int(rows[0].get("times_delivered") or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


async def _drop_poison_entries(
    redis: Redis, entries: list[tuple[str, dict[str, Any] | None]]
) -> list[tuple[str, dict[str, Any] | None]]:
    """Move reclaimed entries past MAX_JOB_DELIVERIES to the DLQ and ack them.

    A handler exception is retried and dead-lettered in-process; only an entry
    that never gets acked (the process died or was killed while running it)
    reaches this count.
    """
    keep: list[tuple[str, dict[str, Any] | None]] = []
    for entry_id, fields in entries:
        if fields is None:
            keep.append((entry_id, fields))
            continue
        delivered = await _times_delivered(redis, entry_id)
        if delivered <= MAX_JOB_DELIVERIES:
            keep.append((entry_id, fields))
            continue
        logger.error(
            "Job id=%s type=%s delivered %s times without finishing; moving to DLQ",
            entry_id,
            fields.get("type"),
            delivered,
        )
        _capture_sentry_exception(f"job_poison:{fields.get('type')}")
        await _move_to_dlq(
            redis, entry_id, fields, f"delivered {delivered} times without finishing"
        )
        try:
            await redis.xack(JOBS_STREAM, JOBS_GROUP, entry_id)
        except Exception:
            logger.debug("xack of poison entry failed id=%s", entry_id, exc_info=True)
    return keep


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
            entries = await _drop_poison_entries(redis, entries)
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
    try:
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
    finally:
        await _forget_consumer(redis, consumer)


async def _forget_consumer(redis: Redis, consumer: str) -> None:
    """Remove this process's consumer from the group when its loop stops.

    Consumers are named per process (host + pid), so every restart, deploy and
    ``--reload`` added one to the group and nothing ever removed it. One that
    still owns pending entries stays: XGROUP DELCONSUMER would drop them from
    the pending list, and XAUTOCLAIM hands them to a live worker first.
    """
    try:
        owned = await redis.xpending_range(
            JOBS_STREAM, JOBS_GROUP, min="-", max="+", count=1, consumername=consumer
        )
        if not owned:
            await redis.xgroup_delconsumer(JOBS_STREAM, JOBS_GROUP, consumer)
    except Exception:
        logger.debug("jobs consumer cleanup skipped consumer=%s", consumer, exc_info=True)


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


class QueueMetrics(TypedDict):
    """A count Redis could not read is None, and ``metrics_error`` names why."""

    dlq_depth: int | None
    pending_entries: int | None
    metrics_error: str | None


async def collect_queue_metrics(redis: Redis) -> QueueMetrics:
    """Return DLQ depth + jobs-stream pending count for observability.

    Never raises into the worker loop, but an unreadable count is None, not 0:
    a failing Redis must not read as an empty, healthy queue.
    """
    metrics = QueueMetrics(dlq_depth=None, pending_entries=None, metrics_error=None)
    try:
        metrics["dlq_depth"] = int(await redis.xlen(JOBS_DLQ_STREAM))
        # redis-py parses the XPENDING summary into {"pending": n, "min", "max", "consumers"}.
        summary = cast(dict[str, Any], await redis.xpending(JOBS_STREAM, JOBS_GROUP))
        metrics["pending_entries"] = int(summary["pending"])
    except Exception as exc:
        metrics["metrics_error"] = type(exc).__name__
        logger.warning("jobs queue metrics unreadable: %s", metrics["metrics_error"])
    return metrics


async def report_queue_metrics(redis: Redis) -> QueueMetrics:
    """Report queue metrics to Sentry when it is installed: a breadcrumb every call, and a
    warning when a count crosses its threshold or could not be read at all.
    """
    metrics = await collect_queue_metrics(redis)
    dlq, pending, error = metrics["dlq_depth"], metrics["pending_entries"], metrics["metrics_error"]
    alerts = [f"Jobs queue metrics unreadable ({error})"] if error else []
    if dlq is not None and dlq >= _DLQ_ALERT_THRESHOLD:
        alerts.append(f"Jobs DLQ depth {dlq} >= {_DLQ_ALERT_THRESHOLD}")
    if pending is not None and pending >= _PENDING_ALERT_THRESHOLD:
        alerts.append(f"Jobs pending entries {pending} >= {_PENDING_ALERT_THRESHOLD}")
    try:
        import sentry_sdk

        sentry_sdk.add_breadcrumb(
            category="jobs.queue",
            message=f"queue metrics: dlq={dlq} pending={pending}",
            level="info",
            data=metrics,
        )
        for alert in alerts:
            sentry_sdk.capture_message(alert, level="warning")
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


# ── account delete ───────────────────────────────────────────────────────────

_PURGE_SCAN_BATCH = 500


def _payload_user_id(fields: dict[str, Any]) -> str | None:
    try:
        payload = json.loads(fields.get("payload") or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    raw = payload.get("user_id")
    return str(raw) if raw else None


def _after(entry_id: str) -> str:
    """The smallest stream id after *entry_id* (an exclusive XRANGE start)."""
    ms, _, seq = str(entry_id).partition("-")
    return f"{ms}-{int(seq or 0) + 1}"


async def purge_user_jobs(
    redis: Redis,
    user_id: UUID | str,
    *,
    keep_types: Collection[str] = (),
    batch: int = _PURGE_SCAN_BATCH,
) -> int:
    """XDEL every jobs-stream and DLQ entry whose payload names *user_id*.

    Acked and failed entries stay in both streams until the length cap trims
    them, and their payloads carry chat text. Walks each stream in bounded
    XRANGE pages and deletes only entries whose payload ``user_id`` equals
    this one; *keep_types* entries stay (the caller's own running job).
    Worker-only (account delete's sweep): never call it on a request path.
    """
    needle = str(user_id)
    page = max(1, batch)
    removed = 0
    for stream in (JOBS_STREAM, JOBS_DLQ_STREAM):
        start = "-"
        while True:
            entries = cast(
                list[tuple[str, dict[str, Any]]],
                await redis.xrange(stream, min=start, max="+", count=page),
            )
            if not entries:
                break
            doomed = [
                entry_id
                for entry_id, fields in entries
                if fields.get("type") not in keep_types and _payload_user_id(fields) == needle
            ]
            if doomed:
                removed += int(await redis.xdel(stream, *doomed) or 0)
            if len(entries) < page:
                break
            start = _after(entries[-1][0])
    if removed:
        logger.info("Jobs purge user_id=%s removed=%s", needle, removed)
    return removed


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
            # Same hard ceiling as enqueue: the soft cap here would trim
            # queued and pending work whenever a backlog exists.
            hard_cap = _hard_maxlen()
            if hard_cap is None:
                await redis.xadd(JOBS_STREAM, cast(Any, fields))
            else:
                await redis.xadd(
                    JOBS_STREAM,
                    cast(Any, fields),
                    maxlen=hard_cap,
                    approximate=True,
                )
            if delete:
                await redis.xdel(JOBS_DLQ_STREAM, entry["id"])
            replayed += 1
        except Exception:
            logger.exception("Failed to replay DLQ entry id=%s", entry.get("id"))
    return replayed

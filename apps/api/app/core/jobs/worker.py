"""The consumer: dispatch with retries and a deadline, ack or dead-letter, reclaim, liveness."""

import asyncio
import logging
import os
import socket
import time
import traceback
from typing import Any, Literal, cast

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.jobs.admin import _METRICS_INTERVAL_S, _move_to_dlq, report_queue_metrics
from app.core.jobs.dedupe import (
    _claim_dedupe,
    _dedupe_is_complete,
    _extend_dedupe,
    _refresh_running_claim,
    _refresh_running_claim_loop,
    _release_dedupe,
)
from app.core.jobs.queue import (
    JOBS_GROUP,
    JOBS_STREAM,
    JobDiscardError,
    _capture_sentry_exception,
    _dispatch,
)
from app.core.redis import get_jobs_redis_client

logger = logging.getLogger("app.core.jobs")

_BLOCK_MS = 5_000
_BATCH = 10
_CLAIM_IDLE_MS = 60_000
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


async def _process_one_entry(
    redis: Redis,
    settings: Settings,
    entry_id: str,
    fields: dict[str, Any],
) -> None:
    """Claim, dispatch, then ack or dead-letter a single stream entry (safe to run concurrently)."""
    # Per-entry (and per-attempt) so a long LLM timeout / index batch cannot
    # trip the 120s stale health check while this worker is still healthy.
    _touch_heartbeat()
    dedupe_key = fields.get("dedupe_key") or None
    if isinstance(dedupe_key, str):
        dedupe_key = dedupe_key.strip() or None
    else:
        dedupe_key = None
    should_ack = True
    owns_claim = False
    keepalive: asyncio.Task[None] | None = None
    try:
        claim = await _claim_entry(redis, entry_id, dedupe_key)
        if claim != "run":
            should_ack = claim == "done"
            return
        owns_claim = True
        if dedupe_key:
            keepalive = asyncio.create_task(_refresh_running_claim_loop(redis, dedupe_key))
        await _dispatch_with_retries(redis, settings, entry_id, fields, dedupe_key)
    except asyncio.CancelledError:
        # The worker is stopping (deploy, SIGTERM) mid-job. Leave the entry
        # pending so a live worker's reclaim runs it again; acking here
        # dropped every in-flight job on each deploy. Release only a claim
        # this run took: the key a lost SET NX found is another run's claim
        # or done marker, and deleting it let a reclaim run the job twice.
        should_ack = False
        if owns_claim:
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
            await _ack_entry(redis, entry_id)


async def _claim_entry(
    redis: Redis, entry_id: str, dedupe_key: str | None
) -> Literal["run", "done", "in_flight"]:
    """Own the run, or say why not: a duplicate already done, or one still in flight."""
    if await _claim_dedupe(redis, dedupe_key):
        return "run"
    if await _dedupe_is_complete(redis, dedupe_key):
        logger.info("Skipping already-processed job id=%s dedupe_key=%s", entry_id, dedupe_key)
        return "done"
    logger.info("Skipping in-flight job id=%s dedupe_key=%s", entry_id, dedupe_key)
    return "in_flight"


async def _dispatch_with_retries(
    redis: Redis,
    settings: Settings,
    entry_id: str,
    fields: dict[str, Any],
    dedupe_key: str | None,
) -> None:
    """Run the handler, retrying a transient failure; dead-letter what cannot finish."""
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
            # expires (or the keepalive dies with the worker).
            await _extend_dedupe(redis, dedupe_key)
            return
        except JobDiscardError as exc:
            logger.warning("Discarding job id=%s: %s", entry_id, exc)
            await _dead_letter(redis, entry_id, fields, dedupe_key, str(exc))
            return
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
                error = f"timed out after {job_timeout}s"
                await _dead_letter(redis, entry_id, fields, dedupe_key, error)
                return
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
                error = traceback.format_exc(limit=8)
                await _dead_letter(redis, entry_id, fields, dedupe_key, error)


async def _dead_letter(
    redis: Redis, entry_id: str, fields: dict[str, Any], dedupe_key: str | None, error: str
) -> None:
    # Release so a future re-enqueue / DLQ replay can retry.
    await _release_dedupe(redis, dedupe_key)
    await _move_to_dlq(redis, entry_id, fields, error)


async def _ack_entry(redis: Redis, entry_id: str) -> None:
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

"""The job contract: a handler per type, entries enqueued and dispatched, a bounded stream."""

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast

from redis.asyncio import Redis

from app.core.config import Settings, get_settings

logger = logging.getLogger("app.core.jobs")

JOBS_STREAM = "recall:jobs"
JOBS_DLQ_STREAM = "recall:jobs:dlq"
JOBS_GROUP = "workers"
# Soft cap, applied only while nothing is pending (see _trim_jobs_stream).
_MAXLEN = 10_000


class JobDiscardError(Exception):
    """Non-retryable job — move to DLQ and ack (unknown type / bad payload)."""


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

"""Queue health, the dead-letter queue, and the per-user purge."""

import json
import logging
from collections.abc import Collection
from datetime import UTC, datetime
from typing import Any, TypedDict, cast
from uuid import UUID

from redis.asyncio import Redis

from app.core import sentry
from app.core.jobs.queue import JOBS_DLQ_STREAM, JOBS_GROUP, JOBS_STREAM, append_entry

logger = logging.getLogger("app.core.jobs")

_DLQ_MAXLEN = 5_000
# Observe queue health: report DLQ depth + pending entries to Sentry every
# _METRICS_INTERVAL_S, and capture a warning when either crosses its threshold
# so a backed-up queue or growing DLQ doesn't go unnoticed (the admin DLQ
# endpoint is dev-only, so prod had no signal before).
_METRICS_INTERVAL_S = 300
_DLQ_ALERT_THRESHOLD = 20
_PENDING_ALERT_THRESHOLD = 50


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
        sentry.report_exception("dlq_write_failed")


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
    sentry.report_breadcrumb(
        "jobs.queue", f"queue metrics: dlq={dlq} pending={pending}", level="info", data=metrics
    )
    for alert in alerts:
        sentry.report_message(alert, level="warning")
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
            await append_entry(redis, fields)
            if delete:
                await redis.xdel(JOBS_DLQ_STREAM, entry["id"])
            replayed += 1
        except Exception:
            logger.exception("Failed to replay DLQ entry id=%s", entry.get("id"))
    return replayed

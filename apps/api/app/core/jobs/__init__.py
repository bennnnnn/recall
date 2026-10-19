"""Durable background jobs on a Redis Stream.

Title generation, memory extraction, and history compression are enqueued to a
Redis Stream and processed by a consumer in the worker process (``worker_main``).
Because the stream is persisted in Redis, jobs survive a process restart, and a
crash mid-processing leaves the entry in the consumer group's pending list —
reclaimed via XAUTOCLAIM by a live worker. At-least-once.

``queue`` registers handlers, enqueues and bounds the stream, ``dedupe`` keeps
a logical job from running twice, ``worker`` consumes, ``inflight`` runs the
held entries under the concurrency limits and leases them, ``pending`` handles
trimmed and poison entries, and ``admin`` holds queue metrics, the DLQ and the
per-user purge. Every submodule logs as ``app.core.jobs``.
"""

from app.core.jobs.admin import (
    collect_queue_metrics,
    list_dlq,
    purge_user_jobs,
    replay_dlq,
    report_queue_metrics,
)
from app.core.jobs.dedupe import job_done_key
from app.core.jobs.pending import MAX_JOB_DELIVERIES
from app.core.jobs.queue import (
    JOBS_DLQ_STREAM,
    JOBS_GROUP,
    JOBS_STREAM,
    JobDiscardError,
    enqueue,
    register,
)
from app.core.jobs.worker import is_worker_alive, start_worker, stop_worker

__all__ = [
    "JOBS_DLQ_STREAM",
    "JOBS_GROUP",
    "JOBS_STREAM",
    "MAX_JOB_DELIVERIES",
    "JobDiscardError",
    "collect_queue_metrics",
    "enqueue",
    "is_worker_alive",
    "job_done_key",
    "list_dlq",
    "purge_user_jobs",
    "register",
    "replay_dlq",
    "report_queue_metrics",
    "start_worker",
    "stop_worker",
]

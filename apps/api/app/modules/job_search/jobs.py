"""Durable queue registration for My Job searches."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.core.jobs import JobDiscardError, register
from app.core.redis import get_redis_client


async def _handle_job_search_run(settings: Settings, payload: dict[str, Any]) -> None:
    from app.modules.job_search.worker import execute_run

    try:
        run_id = UUID(str(payload.get("run_id")))
    except (TypeError, ValueError) as exc:
        # Old queued profile-only jobs must not bypass durable admission.
        raise JobDiscardError("job_search_run: durable run_id required") from exc
    await execute_run(settings, get_redis_client(), run_id)


async def _handle_job_notification(settings: Settings, payload: dict[str, Any]) -> None:
    from app.modules.job_search.notifications import deliver_event

    try:
        event_id = UUID(str(payload.get("event_id")))
    except (TypeError, ValueError) as exc:
        raise JobDiscardError("job_notification: event_id required") from exc
    await deliver_event(settings, get_redis_client(), event_id)


def register_job_search_jobs() -> None:
    register("job_search_run", _handle_job_search_run)
    register("job_notification", _handle_job_notification)

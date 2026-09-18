"""Durable queue registration for My Job searches."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.core.jobs import JobDiscardError, register
from app.core.redis import get_redis_client
from app.services import job_search_runner


async def _handle_job_search_run(
    settings: Settings,
    payload: dict[str, Any],
) -> None:
    raw_profile_id = payload.get("profile_id")
    try:
        profile_id = UUID(str(raw_profile_id))
    except (TypeError, ValueError) as exc:
        raise JobDiscardError(f"job_search_run: invalid profile_id={raw_profile_id!r}") from exc

    await job_search_runner.run_job_search(
        settings,
        get_redis_client(),
        profile_id=profile_id,
        manual=bool(payload.get("manual")),
    )


def register_job_search_jobs() -> None:
    register("job_search_run", _handle_job_search_run)

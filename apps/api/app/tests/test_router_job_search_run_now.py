from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers import job_search


@pytest.mark.asyncio
async def test_run_now_enqueues_a_manual_occurrence_immediately() -> None:
    profile = MagicMock()
    profile.id = uuid4()
    profile.last_run_at = datetime(2026, 9, 17, 8, tzinfo=UTC)
    dashboard = MagicMock()
    dashboard.profile = profile
    redis = AsyncMock()

    with (
        patch.object(
            job_search.job_search_run_now_service,
            "prepare_manual_run",
            AsyncMock(return_value=dashboard),
        ),
        patch.object(job_search, "enqueue", AsyncMock()) as enqueue,
    ):
        result = await job_search.run_job_search_now(
            user=MagicMock(),
            session=AsyncMock(),
            settings=MagicMock(),
            redis=redis,
        )

    assert result is dashboard
    enqueue.assert_awaited_once_with(
        redis,
        "automation_run",
        {"automation_id": str(profile.id)},
        dedupe_key=(f"automation_run_manual:{profile.id}:{profile.last_run_at.isoformat()}"),
    )


@pytest.mark.asyncio
async def test_run_now_uses_stable_first_run_dedupe_key() -> None:
    profile = MagicMock()
    profile.id = uuid4()
    profile.last_run_at = None
    dashboard = MagicMock()
    dashboard.profile = profile

    with (
        patch.object(
            job_search.job_search_run_now_service,
            "prepare_manual_run",
            AsyncMock(return_value=dashboard),
        ),
        patch.object(job_search, "enqueue", AsyncMock()) as enqueue,
    ):
        await job_search.run_job_search_now(
            user=MagicMock(),
            session=AsyncMock(),
            settings=MagicMock(),
            redis=AsyncMock(),
        )

    assert enqueue.await_args.kwargs["dedupe_key"] == (f"automation_run_manual:{profile.id}:never")


@pytest.mark.asyncio
async def test_run_now_reports_when_immediate_enqueue_fails() -> None:
    profile = MagicMock()
    profile.id = uuid4()
    profile.last_run_at = None
    dashboard = MagicMock()
    dashboard.profile = profile

    with (
        patch.object(
            job_search.job_search_run_now_service,
            "prepare_manual_run",
            AsyncMock(return_value=dashboard),
        ),
        patch.object(
            job_search,
            "enqueue",
            AsyncMock(side_effect=RuntimeError("redis unavailable")),
        ),
        pytest.raises(HTTPException) as exc,
    ):
        await job_search.run_job_search_now(
            user=MagicMock(),
            session=AsyncMock(),
            settings=MagicMock(),
            redis=AsyncMock(),
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "Could not start the job search. Try again."

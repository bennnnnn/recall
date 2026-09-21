"""HTTP orchestration for first-run and retryable My Job searches."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers import job_search


async def test_run_endpoint_queues_first_search() -> None:
    profile = MagicMock(id=uuid4(), last_run_at=None)
    redis = MagicMock()
    enqueue = AsyncMock()
    with (
        patch.object(
            job_search.job_search_service,
            "get_profile_for_user",
            new=AsyncMock(return_value=profile),
        ),
        patch.object(
            job_search.job_search_service,
            "can_request_manual_run",
            return_value=True,
        ),
        patch.object(job_search, "enqueue", new=enqueue),
    ):
        result = await job_search.run_job_search_now(
            user=MagicMock(id=uuid4()),
            session=AsyncMock(),
            redis=redis,
        )

    assert result.queued is True
    enqueue.assert_awaited_once_with(
        redis,
        "job_search_run",
        {"profile_id": str(profile.id), "manual": True},
        dedupe_key=f"job_search_retry:{profile.id}:never",
    )


async def test_run_endpoint_rejects_unavailable_on_demand_search() -> None:
    profile = MagicMock(id=uuid4(), last_run_at=MagicMock())
    with (
        patch.object(
            job_search.job_search_service,
            "get_profile_for_user",
            new=AsyncMock(return_value=profile),
        ),
        patch.object(
            job_search.job_search_service,
            "can_request_manual_run",
            return_value=False,
        ),
        pytest.raises(HTTPException) as excinfo,
    ):
        await job_search.run_job_search_now(
            user=MagicMock(id=uuid4()),
            session=AsyncMock(),
            redis=MagicMock(),
        )

    assert excinfo.value.status_code == 403


async def test_run_endpoint_requires_existing_profile() -> None:
    with (
        patch.object(
            job_search.job_search_service,
            "get_profile_for_user",
            new=AsyncMock(return_value=None),
        ),
        pytest.raises(HTTPException) as excinfo,
    ):
        await job_search.run_job_search_now(
            user=MagicMock(id=uuid4()),
            session=AsyncMock(),
            redis=MagicMock(),
        )

    assert excinfo.value.status_code == 404

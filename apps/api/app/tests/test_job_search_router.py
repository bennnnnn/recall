"""HTTP orchestration for first-run and retryable My Job searches."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers import job_search


async def test_dashboard_versions_bookmarks_from_client_header() -> None:
    dashboard = MagicMock()
    get_dashboard = AsyncMock(return_value=dashboard)
    user = MagicMock(id=uuid4())
    session = AsyncMock()
    settings = MagicMock()
    with patch.object(
        job_search.job_search_service,
        "get_dashboard",
        new=get_dashboard,
    ):
        legacy = await job_search.get_job_search(
            user=user,
            session=session,
            settings=settings,
            bookmark_model=None,
        )
        modern = await job_search.get_job_search(
            user=user,
            session=session,
            settings=settings,
            bookmark_model="separate-v1",
        )

    assert legacy is dashboard and modern is dashboard
    assert get_dashboard.await_args_list[0].kwargs["separate_bookmarks"] is False
    assert get_dashboard.await_args_list[1].kwargs["separate_bookmarks"] is True


async def test_run_endpoint_queues_first_search() -> None:
    profile = MagicMock(id=uuid4(), status="active", last_run_at=None)
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
    profile = MagicMock(id=uuid4(), status="active", last_run_at=MagicMock())
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


async def test_run_endpoint_rejects_paused_profile_without_queueing() -> None:
    profile = MagicMock(id=uuid4(), status="paused", last_run_at=None)
    enqueue = AsyncMock()
    with (
        patch.object(
            job_search.job_search_service,
            "get_profile_for_user",
            new=AsyncMock(return_value=profile),
        ),
        patch.object(job_search, "enqueue", new=enqueue),
        pytest.raises(HTTPException) as excinfo,
    ):
        await job_search.run_job_search_now(
            user=MagicMock(id=uuid4()),
            session=AsyncMock(),
            redis=MagicMock(),
        )

    assert excinfo.value.status_code == 409
    assert "Resume My Job" in str(excinfo.value.detail)
    enqueue.assert_not_awaited()


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

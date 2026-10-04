"""HTTP orchestration for first-run and retryable My Job searches."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.job_search import api as job_search


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


async def test_run_endpoint_queues_first_search(account, db_session, fake_redis) -> None:
    from app.core.config import Settings

    user, _ = account
    result = await job_search.run_job_search_now(
        user=user,
        session=db_session,
        redis=fake_redis,
        settings=Settings(job_search_premium_enabled=True),
        request_key="first-click",
    )
    assert result.queued and result.state == "queued" and result.run_id
    repeated = await job_search.run_job_search_now(
        user=user,
        session=db_session,
        redis=fake_redis,
        settings=Settings(job_search_premium_enabled=True),
        request_key="first-click",
    )
    assert repeated.run_id == result.run_id


async def test_run_endpoint_rejects_unavailable_on_demand_search(
    account, db_session, fake_redis
) -> None:
    from app.core.config import Settings

    user, _ = account
    user.plan = "free"
    with pytest.raises(HTTPException) as error:
        await job_search.run_job_search_now(
            user=user,
            session=db_session,
            redis=fake_redis,
            settings=Settings(job_search_premium_enabled=True),
            request_key="denied",
        )
    assert error.value.status_code == 403


async def test_run_endpoint_rejects_paused_profile_without_queueing(
    account, db_session, fake_redis
) -> None:
    from app.core.config import Settings

    user, profile = account
    profile.status = "paused"
    await db_session.commit()
    with pytest.raises(HTTPException) as error:
        await job_search.run_job_search_now(
            user=user,
            session=db_session,
            redis=fake_redis,
            settings=Settings(job_search_premium_enabled=True),
            request_key="paused",
        )
    assert error.value.status_code == 409 and "Resume My Job" in error.value.detail


async def test_run_endpoint_requires_existing_profile(account, db_session, fake_redis) -> None:
    from app.core.config import Settings

    user, profile = account
    await db_session.delete(profile)
    await db_session.commit()
    with pytest.raises(HTTPException) as error:
        await job_search.run_job_search_now(
            user=user,
            session=db_session,
            redis=fake_redis,
            settings=Settings(job_search_premium_enabled=True),
            request_key="missing",
        )
    assert error.value.status_code == 404

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.jobs import JobDiscardError
from app.modules.job_search import jobs as job_search_jobs
from app.modules.job_search import scheduler as job_search_scheduler


class _SessionCM:
    def __init__(self, session: object) -> None:
        self._session = session

    async def __aenter__(self) -> object:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_job_search_cycle_is_disabled_without_web_search(
    account, db_session, fake_redis, durable_session
) -> None:
    from app.modules.job_search.runs import submit_run

    user, _ = account
    run = await submit_run(db_session, user, Settings(job_search_premium_enabled=True), fake_redis)
    enqueue = AsyncMock()
    from app.tests.modules.job_search.test_jobs import _SessionCM

    with (
        patch.object(job_search_scheduler, "SessionLocal", return_value=_SessionCM(db_session)),
        patch.object(job_search_scheduler, "get_redis_client", return_value=fake_redis),
        patch.object(job_search_scheduler, "dispatch", enqueue),
    ):
        await job_search_scheduler._cycle(Settings(web_search_enabled=False))
    enqueue.assert_awaited_once_with(fake_redis, run)


@pytest.mark.asyncio
async def test_job_search_cycle_enqueues_due_profiles_with_stable_dedupe_keys(
    account, db_session, fake_redis, durable_session
) -> None:
    from sqlalchemy import select

    from app.modules.job_search.models import JobSearchRun

    _user, profile = account
    profile.next_run_at = datetime.now(UTC) - timedelta(minutes=2)
    await db_session.commit()
    expected = f"scheduled:{profile.next_run_at.isoformat()}"
    with (
        patch.object(job_search_scheduler, "SessionLocal", return_value=_SessionCM(db_session)),
        patch.object(job_search_scheduler, "get_redis_client", return_value=fake_redis),
    ):
        await job_search_scheduler._cycle(
            Settings(web_search_enabled=True, job_search_premium_enabled=True)
        )
        await job_search_scheduler._cycle(
            Settings(web_search_enabled=True, job_search_premium_enabled=True)
        )
    runs = list(
        (
            await db_session.scalars(
                select(JobSearchRun).where(JobSearchRun.profile_id == profile.id)
            )
        ).all()
    )
    assert len(runs) == 1 and runs[0].request_key == expected and runs[0].manual is False


@pytest.mark.asyncio
async def test_job_search_worker_forwards_scheduled_run_payload() -> None:
    run_id = uuid4()
    settings = Settings()
    redis = AsyncMock()
    execute = AsyncMock()
    with (
        patch("app.modules.job_search.jobs.get_redis_client", return_value=redis),
        patch("app.modules.job_search.worker.execute_run", execute),
    ):
        await job_search_jobs._handle_job_search_run(settings, {"run_id": str(run_id)})
    execute.assert_awaited_once_with(settings, redis, run_id)


@pytest.mark.asyncio
async def test_job_search_worker_discards_invalid_profile_id() -> None:
    with pytest.raises(JobDiscardError):
        await job_search_jobs._handle_job_search_run(
            Settings(),
            {"profile_id": "not-a-uuid", "manual": False},
        )

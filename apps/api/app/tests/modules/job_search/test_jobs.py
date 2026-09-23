from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
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
async def test_job_search_cycle_is_disabled_without_web_search() -> None:
    enqueue = AsyncMock()
    with (
        patch("app.modules.job_search.scheduler.SessionLocal") as session_local,
        patch("app.modules.job_search.scheduler.enqueue", enqueue),
    ):
        await job_search_scheduler._cycle(Settings(web_search_enabled=False))

    session_local.assert_not_called()
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_job_search_cycle_enqueues_due_profiles_with_stable_dedupe_keys() -> None:
    now = datetime.now(UTC)
    profiles = [
        SimpleNamespace(id=uuid4(), next_run_at=now - timedelta(minutes=2)),
        SimpleNamespace(id=uuid4(), next_run_at=now - timedelta(minutes=1)),
    ]
    session = AsyncMock()
    session.scalars.return_value = SimpleNamespace(all=lambda: profiles)
    redis = AsyncMock()
    enqueue = AsyncMock()

    with (
        patch(
            "app.modules.job_search.scheduler.SessionLocal",
            return_value=_SessionCM(session),
        ),
        patch(
            "app.modules.job_search.scheduler.get_redis_client",
            return_value=redis,
        ),
        patch("app.modules.job_search.scheduler.enqueue", enqueue),
    ):
        await job_search_scheduler._cycle(Settings(web_search_enabled=True))

    assert enqueue.await_count == 2
    for call, profile in zip(enqueue.await_args_list, profiles, strict=True):
        assert call.args == (
            redis,
            "job_search_run",
            {"profile_id": str(profile.id), "manual": False},
        )
        assert call.kwargs == {
            "dedupe_key": (f"job_search_run:{profile.id}:{profile.next_run_at.isoformat()}")
        }


@pytest.mark.asyncio
async def test_job_search_worker_forwards_scheduled_run_payload() -> None:
    profile_id = uuid4()
    settings = Settings()
    redis = AsyncMock()
    run = AsyncMock()
    with (
        patch("app.modules.job_search.jobs.get_redis_client", return_value=redis),
        patch("app.modules.job_search.jobs.job_search_runner.run_job_search", run),
    ):
        await job_search_jobs._handle_job_search_run(
            settings,
            {"profile_id": str(profile_id), "manual": False},
        )

    run.assert_awaited_once_with(
        settings,
        redis,
        profile_id=profile_id,
        manual=False,
        overrides=None,
        result_limit=None,
    )


@pytest.mark.asyncio
async def test_job_search_worker_discards_invalid_profile_id() -> None:
    with pytest.raises(JobDiscardError):
        await job_search_jobs._handle_job_search_run(
            Settings(),
            {"profile_id": "not-a-uuid", "manual": False},
        )

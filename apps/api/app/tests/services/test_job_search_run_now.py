from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services import job_search, job_search_run_now


def _user(*, pro: bool = True) -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    user.plan = "pro" if pro else "free"
    return user


def _automation(*, status: str = "active", last_run_at: datetime | None = None) -> MagicMock:
    automation = MagicMock()
    automation.id = uuid4()
    automation.status = status
    automation.next_run_at = datetime.now(UTC) + timedelta(days=4)
    automation.last_run_at = last_run_at
    return automation


@pytest.mark.asyncio
async def test_manual_run_preserves_the_future_recurring_schedule() -> None:
    session = AsyncMock()
    user = _user()
    automation = _automation()
    dashboard = MagicMock()

    with (
        patch.object(job_search_run_now.plan_service, "is_pro", return_value=True),
        patch.object(
            job_search_run_now.automations_repo,
            "get_job_search_for_user",
            AsyncMock(return_value=automation),
        ),
        patch.object(job_search_run_now.automations_repo, "update", AsyncMock()) as update,
        patch.object(
            job_search_run_now.job_search_service,
            "get_dashboard",
            AsyncMock(return_value=dashboard),
        ),
    ):
        result = await job_search_run_now.prepare_manual_run(
            session,
            user,
            MagicMock(automations_enabled=True),
        )

    assert result is dashboard
    update.assert_not_awaited()
    assert automation.next_run_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_manual_run_resumes_a_paused_search_without_rescheduling_it() -> None:
    session = AsyncMock()
    user = _user()
    automation = _automation(status="paused")
    scheduled_for = automation.next_run_at

    with (
        patch.object(job_search_run_now.plan_service, "is_pro", return_value=True),
        patch.object(
            job_search_run_now.automations_repo,
            "get_job_search_for_user",
            AsyncMock(return_value=automation),
        ),
        patch.object(job_search_run_now.automations_repo, "update", AsyncMock()) as update,
        patch.object(
            job_search_run_now.job_search_service,
            "get_dashboard",
            AsyncMock(return_value=MagicMock()),
        ),
    ):
        await job_search_run_now.prepare_manual_run(
            session,
            user,
            MagicMock(automations_enabled=True),
        )

    update.assert_awaited_once_with(session, automation, status="active")
    assert automation.next_run_at == scheduled_for


@pytest.mark.asyncio
async def test_manual_run_requires_pro() -> None:
    with (
        patch.object(job_search_run_now.plan_service, "is_pro", return_value=False),
        pytest.raises(job_search.JobSearchError) as exc,
    ):
        await job_search_run_now.prepare_manual_run(
            AsyncMock(),
            _user(pro=False),
            MagicMock(automations_enabled=True),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_manual_run_rejects_a_recently_completed_search() -> None:
    automation = _automation(last_run_at=datetime.now(UTC) - timedelta(minutes=2))

    with (
        patch.object(job_search_run_now.plan_service, "is_pro", return_value=True),
        patch.object(
            job_search_run_now.automations_repo,
            "get_job_search_for_user",
            AsyncMock(return_value=automation),
        ),
        pytest.raises(job_search.JobSearchError) as exc,
    ):
        await job_search_run_now.prepare_manual_run(
            AsyncMock(),
            _user(),
            MagicMock(automations_enabled=True),
        )

    assert exc.value.status_code == 429

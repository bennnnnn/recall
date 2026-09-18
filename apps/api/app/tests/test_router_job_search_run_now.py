from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.routers import job_search


@pytest.mark.asyncio
async def test_run_now_enqueues_the_due_search_immediately() -> None:
    profile = MagicMock()
    profile.id = uuid4()
    profile.next_run_at = datetime(2026, 9, 18, 8, tzinfo=UTC)
    dashboard = MagicMock()
    dashboard.profile = profile
    redis = AsyncMock()

    with (
        patch.object(
            job_search.job_search_service,
            "run_now",
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
        dedupe_key=(
            f"automation_run:{profile.id}:{profile.next_run_at.isoformat()}"
        ),
    )


@pytest.mark.asyncio
async def test_run_now_keeps_scheduler_fallback_when_immediate_enqueue_fails() -> None:
    profile = MagicMock()
    profile.id = uuid4()
    profile.next_run_at = datetime(2026, 9, 18, 8, tzinfo=UTC)
    dashboard = MagicMock()
    dashboard.profile = profile

    with (
        patch.object(
            job_search.job_search_service,
            "run_now",
            AsyncMock(return_value=dashboard),
        ),
        patch.object(
            job_search,
            "enqueue",
            AsyncMock(side_effect=RuntimeError("redis unavailable")),
        ),
    ):
        result = await job_search.run_job_search_now(
            user=MagicMock(),
            session=AsyncMock(),
            settings=MagicMock(),
            redis=AsyncMock(),
        )

    assert result is dashboard

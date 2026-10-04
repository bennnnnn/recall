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


async def _history_match(session, profile, found_at, *, checked_at=None, status="new", saved=False):
    from app.modules.job_search.models import JobMatch

    identity = str(uuid4())
    match = JobMatch(
        profile_id=profile.id,
        title=f"Engineer {identity}",
        company="Example",
        url=f"https://jobs.example.com/{identity}",
        canonical_url=f"https://jobs.example.com/{identity}",
        canonical_url_hash=identity,
        found_at=found_at,
        checked_at=checked_at,
        status=status,
        is_saved=saved,
        match_reasons=[],
    )
    session.add(match)
    await session.flush()
    return match


async def _history_run(session, profile, finished_at, matches, state="completed"):
    from datetime import timedelta

    from app.modules.job_search.models import JobSearchRun

    run = JobSearchRun(
        profile_id=profile.id,
        request_key=str(uuid4()),
        profile_revision=profile.revision,
        manual=True,
        local_day="2026-10-03",
        state=state,
        created_at=finished_at - timedelta(minutes=2),
        started_at=finished_at - timedelta(minutes=1),
        finished_at=finished_at,
        match_ids=[str(match.id) for match in matches],
    )
    session.add(run)
    await session.flush()
    return run


async def test_all_pages_by_search_date_and_retains_bookmarks(account, db_session):
    from datetime import UTC, datetime, timedelta

    user, profile = account
    now = datetime.now(UTC)
    older = await _history_match(
        db_session, profile, now - timedelta(days=2), checked_at=now, saved=True
    )
    newer = await _history_match(db_session, profile, now - timedelta(days=1))
    await _history_match(db_session, profile, now + timedelta(days=1), status="hidden")
    first = await job_search.list_matches(user=user, session=db_session, view="all", limit=1)
    second = await job_search.list_matches(
        user=user, session=db_session, view="all", limit=1, offset=first.next_offset
    )
    assert [match.id for match in first.matches] == [older.id]
    assert first.matches[0].is_saved and first.next_offset == 1
    assert [match.id for match in second.matches] == [newer.id]
    assert second.next_offset is None


async def test_new_uses_latest_success_and_excludes_rediscovered_jobs(account, db_session):
    from datetime import UTC, datetime, timedelta

    user, profile = account
    now = datetime.now(UTC)
    old = await _history_match(db_session, profile, now - timedelta(days=1), checked_at=now)
    new = await _history_match(db_session, profile, now, status="applied", saved=True)
    previous = await _history_match(db_session, profile, now - timedelta(hours=1))
    await _history_run(db_session, profile, previous.found_at, [previous])
    latest = await _history_run(db_session, profile, now, [old, new])
    await _history_run(db_session, profile, now + timedelta(minutes=1), [], state="failed")
    result = await job_search.list_matches(user=user, session=db_session, view="new")
    assert [match.id for match in result.matches] == [new.id]
    assert result.matches[0].status == "applied" and result.matches[0].is_saved
    notification = await job_search.list_matches(
        user=user, session=db_session, view="new", run_id=latest.id
    )
    assert [match.id for match in notification.matches] == [new.id]
    await _history_run(db_session, profile, now + timedelta(minutes=2), [])
    empty = await job_search.list_matches(user=user, session=db_session, view="new")
    assert empty.matches == []
    history = await job_search.list_matches(user=user, session=db_session, view="all")
    assert len(history.matches) == 3


async def test_new_retains_latest_legacy_batch(account, db_session):
    from datetime import UTC, datetime, timedelta

    user, profile = account
    now = datetime.now(UTC)
    await _history_match(db_session, profile, now - timedelta(days=1))
    latest = await _history_match(db_session, profile, now)
    result = await job_search.list_matches(user=user, session=db_session, view="new")
    assert [match.id for match in result.matches] == [latest.id]


async def test_applied_pages_include_only_applied_jobs(account, db_session):
    from datetime import UTC, datetime

    user, profile = account
    now = datetime.now(UTC)
    await _history_match(db_session, profile, now)
    applications = [
        await _history_match(db_session, profile, now, status="applied", saved=saved)
        for saved in (True, False, True, False)
    ]
    result = await job_search.list_matches(user=user, session=db_session, view="applied", limit=2)
    rest = await job_search.list_matches(
        user=user, session=db_session, view="applied", limit=2, offset=result.next_offset
    )
    assert {match.id for match in result.matches + rest.matches} == {
        match.id for match in applications
    }
    assert result.next_offset == 2 and rest.next_offset is None


async def test_run_pages_enforce_ownership_and_validate_view(account, db_session):
    from datetime import UTC, datetime

    from app.models.orm import User

    user, profile = account
    run = await _history_run(db_session, profile, datetime.now(UTC), [])
    stranger = User(id=uuid4(), email=f"stranger-{uuid4()}@example.com", plan="free")
    # Ownership must be checked even when a user has no job profile.
    with pytest.raises(HTTPException) as error:
        await job_search.list_matches(user=stranger, session=db_session, run_id=run.id)
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as invalid:
        await job_search.list_matches(user=user, session=db_session, view="saved")
    assert invalid.value.status_code == 422

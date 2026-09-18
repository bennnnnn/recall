"""Tests for app.services.automations.run — the automation_run job handler body."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.exceptions import QuotaExceededError
from app.services.automations import run as automations_run


class _FakeSessionCM:
    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


def _session_local(session: AsyncMock):
    return MagicMock(side_effect=lambda: _FakeSessionCM(session))


def _automation(**overrides: object) -> MagicMock:
    automation = MagicMock()
    automation.id = overrides.get("id", uuid4())
    automation.user_id = overrides.get("user_id", uuid4())
    automation.chat_id = overrides.get("chat_id", uuid4())
    automation.title = overrides.get("title", "Backend Job Watch")
    automation.prompt = overrides.get("prompt", "Find L3 backend jobs")
    automation.frequency = overrides.get("frequency", "daily")
    # Comfortably in the past relative to real "now" — run_automation itself
    # takes now=datetime.now(UTC), so a due automation's next_run_at must be
    # earlier than that for _advance_or_complete to actually advance it.
    automation.next_run_at = overrides.get("next_run_at", datetime(2020, 1, 1, 8, tzinfo=UTC))
    automation.status = overrides.get("status", "active")
    return automation


def _user(*, plan: str = "pro", timezone: str = "UTC") -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    user.plan = plan
    user.timezone = timezone
    return user


def _session_returning(automation, user) -> AsyncMock:
    session = AsyncMock()

    async def _get(model, _id):
        from app.models.orm import Automation, User

        if model is Automation:
            return automation
        if model is User:
            return user
        return None

    session.get = AsyncMock(side_effect=_get)
    return session


def _fake_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.incr = AsyncMock()
    redis.expire = AsyncMock()
    return redis


@pytest.mark.asyncio
async def test_run_automation_returns_when_automation_gone():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    redis = _fake_redis()

    with (
        patch.object(automations_run, "SessionLocal", _session_local(session)),
        patch.object(
            automations_run, "stream_chat_response", AsyncMock(side_effect=AssertionError())
        ),
    ):
        await automations_run.run_automation(Settings(), redis, automation_id=uuid4())

    session.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_automation_returns_when_not_active():
    automation = _automation(status="paused")
    user = _user()
    session = _session_returning(automation, user)
    redis = _fake_redis()

    def _boom(*_a, **_k):
        raise AssertionError("must not run a turn")

    with (
        patch.object(automations_run, "SessionLocal", _session_local(session)),
        patch.object(automations_run, "stream_chat_response", _boom),
    ):
        await automations_run.run_automation(Settings(), redis, automation_id=automation.id)


@pytest.mark.asyncio
async def test_run_automation_pauses_active_automation_on_plan_downgrade():
    automation = _automation()
    user = _user(plan="free")
    session = _session_returning(automation, user)
    redis = _fake_redis()

    def _boom(*_a, **_k):
        raise AssertionError("must not run a turn")

    with (
        patch.object(automations_run, "SessionLocal", _session_local(session)),
        patch.object(automations_run, "stream_chat_response", _boom),
        patch.object(
            automations_run.automations_repo, "update", AsyncMock(return_value=automation)
        ) as update,
    ):
        await automations_run.run_automation(Settings(), redis, automation_id=automation.id)

    assert update.await_args.kwargs["status"] == "paused"
    assert update.await_args.kwargs["last_run_status"] == "error"


@pytest.mark.asyncio
async def test_run_automation_skipped_when_daily_cap_reached():
    automation = _automation(frequency="daily")
    user = _user()
    session = _session_returning(automation, user)
    redis = _fake_redis()
    redis.get = AsyncMock(return_value=b"6")

    def _boom(*_a, **_k):
        raise AssertionError("must not run a turn")

    with (
        patch.object(automations_run, "SessionLocal", _session_local(session)),
        patch.object(automations_run, "stream_chat_response", _boom),
        patch.object(
            automations_run.automations_repo, "update", AsyncMock(return_value=automation)
        ) as update,
    ):
        await automations_run.run_automation(
            Settings(automations_daily_run_cap=6), redis, automation_id=automation.id
        )

    assert update.await_args.kwargs["last_run_status"] == "skipped_quota"
    assert update.await_args.kwargs["status"] == "active"
    assert update.await_args.kwargs["next_run_at"] > automation.next_run_at


@pytest.mark.asyncio
async def test_run_automation_happy_path_advances_schedule_and_notifies():
    automation = _automation(frequency="daily")
    user = _user()
    gating_session = _session_returning(automation, user)
    finalize_automation = _automation(
        id=automation.id,
        user_id=automation.user_id,
        chat_id=automation.chat_id,
        frequency="daily",
        next_run_at=automation.next_run_at,
        status="active",
    )
    finalize_session = _session_returning(finalize_automation, user)
    notify_session = AsyncMock()
    sessions = iter([gating_session, finalize_session, notify_session])

    def _next_session():
        return _FakeSessionCM(next(sessions))

    redis = _fake_redis()

    async def _fake_stream(*_args, **kwargs):
        result = kwargs.get("result")
        if result is not None:
            result["final_content"] = "Found 3 job postings"
        yield "chunk"

    with (
        patch.object(automations_run, "SessionLocal", MagicMock(side_effect=_next_session)),
        patch.object(automations_run, "stream_chat_response", _fake_stream),
        patch.object(
            automations_run.automations_repo, "update", AsyncMock(return_value=finalize_automation)
        ) as update,
        patch.object(
            automations_run.push_notifications, "notify_automation_run", AsyncMock()
        ) as notify,
    ):
        await automations_run.run_automation(Settings(), redis, automation_id=automation.id)

    assert update.await_args.kwargs["last_run_status"] == "ok"
    assert update.await_args.kwargs["status"] == "active"
    assert update.await_args.kwargs["next_run_at"] > automation.next_run_at
    notify.assert_awaited_once()
    redis.incr.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_automation_once_frequency_completes_after_success():
    automation = _automation(frequency="once")
    user = _user()
    gating_session = _session_returning(automation, user)
    finalize_automation = _automation(
        id=automation.id,
        user_id=automation.user_id,
        chat_id=automation.chat_id,
        frequency="once",
        next_run_at=automation.next_run_at,
        status="active",
    )
    finalize_session = _session_returning(finalize_automation, user)
    notify_session = AsyncMock()
    sessions = iter([gating_session, finalize_session, notify_session])

    def _next_session():
        return _FakeSessionCM(next(sessions))

    redis = _fake_redis()

    async def _fake_stream(*_args, **kwargs):
        yield "chunk"

    with (
        patch.object(automations_run, "SessionLocal", MagicMock(side_effect=_next_session)),
        patch.object(automations_run, "stream_chat_response", _fake_stream),
        patch.object(
            automations_run.automations_repo, "update", AsyncMock(return_value=finalize_automation)
        ) as update,
        patch.object(automations_run.push_notifications, "notify_automation_run", AsyncMock()),
    ):
        await automations_run.run_automation(Settings(), redis, automation_id=automation.id)

    assert update.await_args.kwargs["status"] == "completed"
    assert update.await_args.kwargs["next_run_at"] == automation.next_run_at


@pytest.mark.asyncio
async def test_run_automation_quota_exceeded_marks_skipped_and_does_not_notify():
    automation = _automation()
    user = _user()
    gating_session = _session_returning(automation, user)
    finalize_session = _session_returning(automation, user)
    sessions = iter([gating_session, finalize_session])

    def _next_session():
        return _FakeSessionCM(next(sessions))

    redis = _fake_redis()

    async def _raises_quota(*_args, **_kwargs):
        raise QuotaExceededError("out of quota")
        yield  # pragma: no cover - unreachable, keeps this an async generator

    with (
        patch.object(automations_run, "SessionLocal", MagicMock(side_effect=_next_session)),
        patch.object(automations_run, "stream_chat_response", _raises_quota),
        patch.object(
            automations_run.automations_repo, "update", AsyncMock(return_value=automation)
        ) as update,
        patch.object(
            automations_run.push_notifications, "notify_automation_run", AsyncMock()
        ) as notify,
    ):
        await automations_run.run_automation(Settings(), redis, automation_id=automation.id)

    assert update.await_args.kwargs["last_run_status"] == "skipped_quota"
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_automation_unexpected_error_marks_error_and_does_not_notify():
    automation = _automation()
    user = _user()
    gating_session = _session_returning(automation, user)
    finalize_session = _session_returning(automation, user)
    sessions = iter([gating_session, finalize_session])

    def _next_session():
        return _FakeSessionCM(next(sessions))

    redis = _fake_redis()

    async def _raises(*_args, **_kwargs):
        raise RuntimeError("provider down")
        yield  # pragma: no cover - unreachable, keeps this an async generator

    with (
        patch.object(automations_run, "SessionLocal", MagicMock(side_effect=_next_session)),
        patch.object(automations_run, "stream_chat_response", _raises),
        patch.object(
            automations_run.automations_repo, "update", AsyncMock(return_value=automation)
        ) as update,
        patch.object(
            automations_run.push_notifications, "notify_automation_run", AsyncMock()
        ) as notify,
    ):
        await automations_run.run_automation(Settings(), redis, automation_id=automation.id)

    assert update.await_args.kwargs["last_run_status"] == "error"
    notify.assert_not_awaited()


@pytest.mark.parametrize(
    "frequency",
    ["daily", "weekdays", "weekly", "monthly"],
)
def test_advance_or_complete_stays_active_for_recurring_frequencies(frequency):
    automation = _automation(frequency=frequency, next_run_at=datetime(2026, 9, 18, 8, tzinfo=UTC))
    user = _user()
    next_at, status = automations_run._advance_or_complete(
        automation, user, now=datetime(2026, 9, 18, 9, tzinfo=UTC)
    )
    assert status == "active"
    assert next_at > automation.next_run_at


def test_advance_or_complete_completes_once():
    automation = _automation(frequency="once", next_run_at=datetime(2026, 9, 18, 8, tzinfo=UTC))
    user = _user()
    next_at, status = automations_run._advance_or_complete(
        automation, user, now=datetime(2026, 9, 18, 9, tzinfo=UTC)
    )
    assert status == "completed"
    assert next_at == automation.next_run_at


def test_advance_or_complete_defensively_completes_unknown_frequency():
    automation = _automation(frequency="hourly", next_run_at=datetime(2026, 9, 18, 8, tzinfo=UTC))
    user = _user()
    next_at, status = automations_run._advance_or_complete(
        automation, user, now=datetime(2026, 9, 18, 9, tzinfo=UTC)
    )
    assert status == "completed"
    assert next_at == automation.next_run_at


@pytest.mark.asyncio
async def test_daily_run_count_round_trips_through_redis():
    redis = _fake_redis()
    now = datetime(2026, 9, 18, 8, tzinfo=UTC)
    redis.get = AsyncMock(return_value=None)
    assert await automations_run._daily_run_count(redis, uuid4(), now=now) == 0

    automation_id = uuid4()
    await automations_run._bump_daily_run_count(redis, automation_id, now=now)
    redis.incr.assert_awaited_once_with(automations_run._daily_run_count_key(automation_id, now))
    redis.expire.assert_awaited_once()

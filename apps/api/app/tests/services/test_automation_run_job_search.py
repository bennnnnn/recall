"""Focused coverage for the free My Job scheduled-run path."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import Automation, User
from app.services.automations import run as automations_run


class _SessionContext:
    def __init__(self, session: AsyncMock) -> None:
        self.session = session

    async def __aenter__(self) -> AsyncMock:
        return self.session

    async def __aexit__(self, *_args: object) -> None:
        return None


def _session(automation: MagicMock, user: MagicMock) -> AsyncMock:
    session = AsyncMock()

    async def get(model, _id):
        if model is Automation:
            return automation
        if model is User:
            return user
        return None

    session.get = AsyncMock(side_effect=get)
    return session


@pytest.mark.asyncio
async def test_free_weekly_job_search_routes_within_free_model_pool() -> None:
    automation = MagicMock()
    automation.id = uuid4()
    automation.user_id = uuid4()
    automation.chat_id = uuid4()
    automation.prompt = "Run My Job"
    automation.frequency = "weekly"
    automation.next_run_at = datetime(2020, 1, 1, 8, tzinfo=UTC)
    automation.status = "active"
    automation.kind = "job_search"
    automation.config_json = '{"result_count":5}'

    user = MagicMock()
    user.id = automation.user_id
    user.plan = "free"
    user.timezone = "UTC"

    gate_session = _session(automation, user)
    finalize_session = _session(automation, user)
    notify_session = AsyncMock()
    sessions = iter([gate_session, finalize_session, notify_session])

    def session_local():
        return _SessionContext(next(sessions))

    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    seen: dict[str, object] = {}

    async def stream(*_args, **kwargs):
        seen.update(kwargs)
        yield "done"

    with (
        patch.object(automations_run, "SessionLocal", MagicMock(side_effect=session_local)),
        patch.object(automations_run, "stream_chat_response", stream),
        patch.object(
            automations_run.automations_repo,
            "update",
            AsyncMock(return_value=automation),
        ),
        patch.object(
            automations_run.push_notifications,
            "notify_automation_run",
            AsyncMock(),
        ),
    ):
        await automations_run.run_automation(Settings(), redis, automation_id=automation.id)

    assert seen["model_alias"] is None
    assert seen["is_automation"] is True
    redis.incr.assert_awaited_once()

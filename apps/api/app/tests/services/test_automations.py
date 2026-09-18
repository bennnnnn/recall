"""Tests for app.services.automations.crud."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.automations import crud as automations_crud


def _user(*, plan: str = "pro", timezone: str = "UTC"):
    user = MagicMock()
    user.id = uuid4()
    user.plan = plan
    user.timezone = timezone
    return user


def _settings(**overrides) -> Settings:
    return Settings(automations_enabled=True, **overrides)


@pytest.mark.asyncio
async def test_list_automations_404s_when_disabled():
    session = AsyncMock()
    user = _user()
    with pytest.raises(automations_crud.AutomationsError) as exc:
        await automations_crud.list_automations(session, user, Settings(automations_enabled=False))
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_list_automations_delegates_to_repo():
    session = AsyncMock()
    user = _user()
    items = [MagicMock()]
    with patch.object(
        automations_crud.automations_repo, "list_for_user", AsyncMock(return_value=items)
    ) as list_for_user:
        result = await automations_crud.list_automations(session, user, _settings())
    assert result is items
    list_for_user.assert_awaited_once_with(session, user.id)


@pytest.mark.asyncio
async def test_get_automation_raises_404_when_missing():
    session = AsyncMock()
    user = _user()
    with patch.object(automations_crud.automations_repo, "get_by_id", AsyncMock(return_value=None)):
        with pytest.raises(automations_crud.AutomationsError) as exc:
            await automations_crud.get_automation(session, user, _settings(), uuid4())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_create_automation_requires_pro():
    session = AsyncMock()
    user = _user(plan="free")
    with pytest.raises(automations_crud.AutomationsError) as exc:
        await automations_crud.create_automation(
            session,
            user,
            _settings(),
            prompt="Find L3 jobs",
            frequency="daily",
            next_run_at=datetime(2026, 9, 18, 8, tzinfo=UTC),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_automation_enforces_active_cap():
    session = AsyncMock()
    user = _user()
    with patch.object(
        automations_crud.automations_repo, "count_active_for_user", AsyncMock(return_value=5)
    ):
        with pytest.raises(automations_crud.AutomationsError) as exc:
            await automations_crud.create_automation(
                session,
                user,
                _settings(automations_max_active_per_user=5),
                prompt="Find L3 jobs",
                frequency="daily",
                next_run_at=datetime(2026, 9, 18, 8, tzinfo=UTC),
            )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_create_automation_creates_dedicated_chat_and_commits_once():
    session = AsyncMock()
    user = _user()
    chat = MagicMock()
    chat.id = uuid4()
    automation = MagicMock()

    with (
        patch.object(
            automations_crud.automations_repo, "count_active_for_user", AsyncMock(return_value=0)
        ),
        patch.object(
            automations_crud.chats_repo, "create", AsyncMock(return_value=chat)
        ) as create_chat,
        patch.object(
            automations_crud.automations_repo, "create", AsyncMock(return_value=automation)
        ) as create_automation,
    ):
        result = await automations_crud.create_automation(
            session,
            user,
            _settings(),
            prompt="  Find L3 jobs  ",
            frequency="daily",
            next_run_at=datetime(2026, 9, 18, 8, tzinfo=UTC),
        )

    assert result is automation
    create_chat.assert_awaited_once_with(session, user_id=user.id, model="smart-chat", commit=False)
    assert create_automation.await_args.kwargs["chat_id"] == chat.id
    assert create_automation.await_args.kwargs["commit"] is False
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(automation)


@pytest.mark.asyncio
async def test_update_automation_normalizes_next_run_at():
    session = AsyncMock()
    user = _user()
    automation = MagicMock()
    with (
        patch.object(
            automations_crud.automations_repo, "get_by_id", AsyncMock(return_value=automation)
        ),
        patch.object(
            automations_crud.automations_repo, "update", AsyncMock(return_value=automation)
        ) as update,
    ):
        await automations_crud.update_automation(
            session,
            user,
            _settings(),
            uuid4(),
            {"status": "paused", "next_run_at": datetime(2026, 9, 18, 8)},
        )
    assert update.await_args.kwargs["status"] == "paused"
    assert update.await_args.kwargs["next_run_at"].tzinfo is not None


@pytest.mark.asyncio
async def test_update_automation_404s_when_missing():
    session = AsyncMock()
    user = _user()
    with patch.object(automations_crud.automations_repo, "get_by_id", AsyncMock(return_value=None)):
        with pytest.raises(automations_crud.AutomationsError) as exc:
            await automations_crud.update_automation(session, user, _settings(), uuid4(), {})
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_automation_deletes_the_dedicated_chat():
    session = AsyncMock()
    user = _user()
    settings = _settings()
    automation = MagicMock()
    automation.chat_id = uuid4()
    with (
        patch.object(
            automations_crud.automations_repo, "get_by_id", AsyncMock(return_value=automation)
        ),
        patch.object(automations_crud.chats_service, "delete_chat", AsyncMock()) as delete_chat,
    ):
        await automations_crud.delete_automation(session, user, settings, uuid4())
    delete_chat.assert_awaited_once_with(session, user, automation.chat_id, settings=settings)


@pytest.mark.asyncio
async def test_delete_automation_404s_when_missing():
    session = AsyncMock()
    user = _user()
    with patch.object(automations_crud.automations_repo, "get_by_id", AsyncMock(return_value=None)):
        with pytest.raises(automations_crud.AutomationsError) as exc:
            await automations_crud.delete_automation(session, user, _settings(), uuid4())
    assert exc.value.status_code == 404

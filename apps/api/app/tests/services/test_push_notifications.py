from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services import push_notifications as push_service


@pytest.mark.asyncio
async def test_process_todo_reminders_due_soon():
    session = AsyncMock()
    user_id = uuid4()
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)

    todo = MagicMock()
    todo.user_id = user_id
    todo.id = uuid4()
    todo.content = "Call dentist"
    todo.due_at = now + timedelta(minutes=5)
    todo.notification_sent_at = None

    user = MagicMock()
    user.push_notifications_enabled = True
    user.reminder_lead_minutes = 10

    token = MagicMock()
    token.expo_push_token = "ExponentPushToken[abc]"

    session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[(todo, user)])))

    with patch.object(
        push_service.push_repo,
        "list_for_user",
        AsyncMock(return_value=[token]),
    ):
        messages = await push_service.process_todo_reminders(session, now=now)

    assert len(messages) == 1
    assert messages[0]["title"] == "Reminder"
    assert messages[0]["body"] == "Call dentist"
    assert messages[0]["data"]["todo_id"] == str(todo.id)
    session.commit.assert_awaited_once()
    assert todo.notification_sent_at == now


@pytest.mark.asyncio
async def test_process_todo_reminders_respects_user_lead():
    session = AsyncMock()
    user_id = uuid4()
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)

    todo = MagicMock()
    todo.user_id = user_id
    todo.id = uuid4()
    todo.content = "Stretch"
    todo.due_at = now + timedelta(minutes=20)
    todo.notification_sent_at = None

    user = MagicMock()
    user.push_notifications_enabled = True
    user.reminder_lead_minutes = 5

    session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[(todo, user)])))

    with patch.object(
        push_service.push_repo,
        "list_for_user",
        AsyncMock(return_value=[]),
    ):
        messages = await push_service.process_todo_reminders(session, now=now)

    assert messages == []
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_todo_reminders_skips_when_push_disabled():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    messages = await push_service.process_todo_reminders(session)
    assert messages == []


@pytest.mark.asyncio
async def test_process_email_suggestions_batches_per_user():
    session = AsyncMock()
    user_id = uuid4()
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)

    reminder_a = MagicMock()
    reminder_a.user_id = user_id
    reminder_a.title = "Flight to NYC"
    reminder_b = MagicMock()
    reminder_b.user_id = user_id
    reminder_b.title = "Interview at Acme"
    user = MagicMock()
    user.push_notifications_enabled = True
    token = MagicMock()
    token.expo_push_token = "ExponentPushToken[abc]"

    session.execute = AsyncMock(
        return_value=MagicMock(all=MagicMock(return_value=[(reminder_a, user), (reminder_b, user)]))
    )

    with patch.object(
        push_service.push_repo,
        "list_for_user",
        AsyncMock(return_value=[token]),
    ):
        messages = await push_service.process_email_suggestions(session, now=now)

    assert len(messages) == 1
    assert "2 reminders" in messages[0]["body"]
    assert messages[0]["data"]["type"] == "email_suggestion"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_learning_nudges_respects_daily_dedup():
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings(push_learning_hour=9)
    user_id = uuid4()

    user = MagicMock()
    user.id = user_id
    user.timezone = "UTC"
    user.push_notifications_enabled = True

    session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[(user_id,)])))
    session.get = AsyncMock(return_value=user)
    redis.set = AsyncMock(return_value=False)

    messages = await push_service.process_learning_nudges(session, redis, settings)
    assert messages == []


@pytest.mark.asyncio
async def test_run_push_cycle_skips_expo_in_dev_mock():
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings(mock_llm_enabled=True, environment="development", push_enabled=True)

    with (
        patch.object(
            push_service,
            "process_todo_reminders",
            AsyncMock(return_value=[{"to": "token"}]),
        ),
        patch.object(push_service, "process_email_suggestions", AsyncMock(return_value=[])),
        patch.object(push_service, "process_learning_nudges", AsyncMock(return_value=[])),
        patch.object(
            push_service.expo_push_gateway, "send_push_messages", AsyncMock()
        ) as send_mock,
    ):
        count = await push_service.run_push_cycle(session, redis, settings)

    assert count == 1
    send_mock.assert_not_awaited()

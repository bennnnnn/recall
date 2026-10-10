from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.notifications import push as push_service


def test_android_channel_follows_push_type():
    assert push_service.android_channel_id({"type": "todo_reminder"}) == "recall-reminders"
    assert push_service.android_channel_id({"type": "digest"}) == "recall-reminders"
    assert push_service.android_channel_id({"type": "email_suggestion"}) == "recall-inbox"


def test_channel_id_stays_off_until_the_install_opts_in():
    legacy = MagicMock(platform="android", android_channels=None)
    assert push_service.channel_id_for_token(legacy, {"type": "todo_reminder"}) is None
    opted_in = MagicMock(platform="android", android_channels="split")
    assert (
        push_service.channel_id_for_token(opted_in, {"type": "todo_reminder"}) == "recall-reminders"
    )
    tone = MagicMock(platform="android", android_channels="tone")
    assert (
        push_service.channel_id_for_token(tone, {"type": "todo_reminder"}) == "recall-reminders-v2"
    )
    ios = MagicMock(platform="ios", android_channels="split")
    assert push_service.channel_id_for_token(ios, {"type": "todo_reminder"}) is None


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
    token.user_id = user_id
    token.expo_push_token = "ExponentPushToken[abc]"
    token.platform = "android"
    token.android_channels = "split"

    session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[(todo, user)])))

    with patch.object(
        push_service.push_repo,
        "list_for_users",
        AsyncMock(return_value=[token]),
    ):
        messages = await push_service.process_todo_reminders(session, now=now)

    assert len(messages) == 1
    assert messages[0].message["title"] == "Reminder"
    assert messages[0].message["body"] == "Call dentist"
    assert messages[0].message["data"]["todo_id"] == str(todo.id)
    assert messages[0].message["channelId"] == "recall-reminders"
    assert messages[0].message["sound"] == "recall_notify.wav"
    session.commit.assert_not_awaited()
    assert todo.notification_sent_at is None


@pytest.mark.asyncio
async def test_process_todo_reminders_skips_quiet_hours():
    session = AsyncMock()
    user_id = uuid4()
    now = datetime(2026, 6, 28, 23, 0, tzinfo=UTC)

    todo = MagicMock()
    todo.user_id = user_id
    todo.id = uuid4()
    todo.content = "Call dentist"
    todo.due_at = now + timedelta(minutes=5)
    todo.notification_sent_at = None

    user = MagicMock()
    user.push_notifications_enabled = True
    user.reminder_lead_minutes = 10
    user.quiet_hours_enabled = True
    user.quiet_hours_start_minute = 1320
    user.quiet_hours_end_minute = 420
    user.timezone = "UTC"

    session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[(todo, user)])))

    with patch.object(
        push_service.push_repo,
        "list_for_users",
        AsyncMock(return_value=[]),
    ):
        messages = await push_service.process_todo_reminders(session, now=now)

    assert messages == []
    assert todo.notification_sent_at is None


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
        "list_for_users",
        AsyncMock(return_value=[]),
    ):
        messages = await push_service.process_todo_reminders(session, now=now)

    assert messages == []
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_log_aged_unsent_reminders_warns_when_count_positive(caplog):
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=4)
    with caplog.at_level("WARNING", logger="app.modules.notifications.push"):
        count = await push_service.log_aged_unsent_reminders(
            session, now=datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
        )
    assert count == 4
    assert "Aged unsent reminders count=4" in caplog.text
    assert "older_than_hours=48" in caplog.text


@pytest.mark.asyncio
async def test_log_aged_unsent_reminders_silent_when_none():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=0)
    count = await push_service.log_aged_unsent_reminders(session)
    assert count == 0


@pytest.mark.asyncio
async def test_process_todo_reminders_logs_when_user_has_no_token(caplog):
    session = AsyncMock()
    user_id = uuid4()
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)

    todo = MagicMock()
    todo.user_id = user_id
    todo.id = uuid4()
    todo.content = "Call dentist"
    todo.due_at = now + timedelta(minutes=5)
    todo.notification_sent_at = None
    todo.recurrence_rule = None

    user = MagicMock()
    user.push_notifications_enabled = True
    user.reminder_lead_minutes = 10
    user.timezone = "UTC"

    session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[(todo, user)])))

    with (
        patch.object(
            push_service.push_repo,
            "list_for_users",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            push_service.todos_crud,
            "_advance_past_recurring",
            AsyncMock(return_value=False),
        ) as advance,
        caplog.at_level("WARNING"),
    ):
        messages = await push_service.process_todo_reminders(session, now=now)

    assert messages == []
    advance.assert_not_awaited()
    assert "no push token" in caplog.text
    assert str(todo.id) in caplog.text
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_todo_reminders_advances_tokenless_overdue_recurring():
    session = AsyncMock()
    user_id = uuid4()
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)

    todo = MagicMock()
    todo.user_id = user_id
    todo.id = uuid4()
    todo.content = "Standup"
    todo.due_at = now - timedelta(minutes=5)
    todo.notification_sent_at = None
    todo.recurrence_rule = "daily"

    user = MagicMock()
    user.push_notifications_enabled = True
    user.reminder_lead_minutes = 10
    user.timezone = "UTC"

    session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[(todo, user)])))

    with (
        patch.object(
            push_service.push_repo,
            "list_for_users",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            push_service.todos_crud,
            "_advance_past_recurring",
            AsyncMock(return_value=True),
        ) as advance,
    ):
        messages = await push_service.process_todo_reminders(session, now=now)

    assert messages == []
    advance.assert_awaited_once()
    assert advance.await_args.args[1] == [todo]
    assert advance.await_args.kwargs["timezone"] == "UTC"
    assert advance.await_args.kwargs["now"] == now


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
    token.user_id = user_id
    token.expo_push_token = "ExponentPushToken[abc]"
    token.platform = "android"
    token.android_channels = "split"

    session.execute = AsyncMock(
        return_value=MagicMock(all=MagicMock(return_value=[(reminder_a, user), (reminder_b, user)]))
    )

    with patch.object(
        push_service.push_repo,
        "list_for_users",
        AsyncMock(return_value=[token]),
    ):
        messages = await push_service.process_email_suggestions(session, now=now)

    assert len(messages) == 1
    assert "2 reminders" in messages[0].message["body"]
    assert messages[0].message["data"]["type"] == "email_suggestion"
    assert messages[0].message["channelId"] == "recall-inbox"
    session.commit.assert_not_awaited()
    assert push_service.EMAIL_SUGGESTION_PUSH_LIMIT == 200
    # Cap is applied on the select (token-less users excluded via EXISTS).
    stmt = session.execute.await_args.args[0]
    assert stmt._limit_clause is not None


@pytest.mark.asyncio
async def test_process_email_suggestions_sanitizes_single_title():
    session = AsyncMock()
    user_id = uuid4()
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    reminder = MagicMock()
    reminder.user_id = user_id
    reminder.title = "  Buy tickets\n\x00now  " + ("x" * 200)
    user = MagicMock()
    user.push_notifications_enabled = True
    token = MagicMock()
    token.user_id = user_id
    token.expo_push_token = "ExponentPushToken[abc]"

    session.execute = AsyncMock(
        return_value=MagicMock(all=MagicMock(return_value=[(reminder, user)]))
    )

    with patch.object(
        push_service.push_repo,
        "list_for_users",
        AsyncMock(return_value=[token]),
    ):
        messages = await push_service.process_email_suggestions(session, now=now)

    assert len(messages) == 1
    body = messages[0].message["body"]
    assert "\x00" not in body
    assert "\n" not in body
    assert len(body) <= 120
    assert body.startswith("Buy tickets now")

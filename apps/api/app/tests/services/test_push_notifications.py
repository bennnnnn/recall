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
    assert messages[0].message["title"] == "Reminder"
    assert messages[0].message["body"] == "Call dentist"
    assert messages[0].message["data"]["todo_id"] == str(todo.id)
    session.commit.assert_not_awaited()
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
    assert "2 reminders" in messages[0].message["body"]
    assert messages[0].message["data"]["type"] == "email_suggestion"
    session.commit.assert_not_awaited()


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

    session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=lambda: [user])))
    )
    redis.set = AsyncMock(return_value=False)

    messages = await push_service.process_learning_nudges(session, redis, settings)
    assert messages == []


@pytest.mark.asyncio
async def test_run_push_cycle_skips_expo_in_dev_mock():
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings(
        mock_llm_enabled=True,
        environment="development",
        push_enabled=True,
        server_todo_push_enabled=True,
    )

    with (
        patch.object(
            push_service,
            "process_todo_reminders",
            AsyncMock(
                return_value=[
                    push_service.OutboundPush(message={"to": "token"}),
                ]
            ),
        ),
        patch.object(push_service, "process_email_suggestions", AsyncMock(return_value=[])),
        patch.object(push_service, "process_learning_nudges", AsyncMock(return_value=[])),
        patch.object(push_service, "process_calendar_nudges", AsyncMock(return_value=[])),
        patch.object(
            push_service.expo_push_gateway, "send_push_messages", AsyncMock()
        ) as send_mock,
    ):
        count = await push_service.run_push_cycle(session, redis, settings)

    assert count == 1
    send_mock.assert_not_awaited()


def _users_execute_result(users):
    return MagicMock(scalars=MagicMock(return_value=MagicMock(all=lambda: users)))


@pytest.mark.asyncio
async def test_process_learning_nudges_language_review():
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings(push_learning_hour=0)
    user_id = uuid4()

    user = MagicMock()
    user.id = user_id
    user.timezone = "UTC"
    user.push_notifications_enabled = True
    user.locale = "en"

    project = MagicMock()
    project.id = uuid4()
    project.user_id = user_id
    project.title = "Spanish"
    project.kind = "language"

    token = MagicMock()
    token.user_id = user_id
    token.expo_push_token = "ExponentPushToken[abc]"

    session.execute = AsyncMock(return_value=_users_execute_result([user]))
    redis.set = AsyncMock(return_value=True)

    with (
        patch.object(
            push_service.projects_repo,
            "list_for_users",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            push_service.project_items_repo,
            "count_stats_by_project",
            AsyncMock(
                return_value={
                    project.id: {
                        "total": 5,
                        "due_for_review": 2,
                        "new_count": 1,
                        "learning_count": 2,
                        "mastered_count": 0,
                    }
                }
            ),
        ),
        patch.object(
            push_service.push_repo,
            "list_for_users",
            AsyncMock(return_value=[token]),
        ),
    ):
        messages = await push_service.process_learning_nudges(session, redis, settings)

    assert len(messages) == 1
    assert "Spanish" in messages[0].message["body"]
    assert messages[0].message["data"]["type"] == "learning_review"


@pytest.mark.asyncio
async def test_process_learning_nudges_batches_across_users():
    """This loop runs every minute across every opted-in user — projects,
    item stats, and tokens must each be fetched in one query regardless of
    how many candidate users there are, not one query per user."""
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings(push_learning_hour=0)

    users = []
    projects = []
    tokens = []
    stats_by_project = {}
    for _ in range(3):
        uid = uuid4()
        user = MagicMock()
        user.id = uid
        user.timezone = "UTC"
        user.push_notifications_enabled = True
        user.locale = "en"
        users.append(user)

        project = MagicMock()
        project.id = uuid4()
        project.user_id = uid
        project.title = "Spanish"
        project.kind = "language"
        projects.append(project)
        stats_by_project[project.id] = {
            "total": 3,
            "due_for_review": 1,
            "new_count": 0,
            "learning_count": 2,
            "mastered_count": 0,
        }

        token = MagicMock()
        token.user_id = uid
        token.expo_push_token = f"ExponentPushToken[{uid}]"
        tokens.append(token)

    session.execute = AsyncMock(return_value=_users_execute_result(users))
    redis.set = AsyncMock(return_value=True)

    with (
        patch.object(
            push_service.projects_repo,
            "list_for_users",
            AsyncMock(return_value=projects),
        ) as list_projects_mock,
        patch.object(
            push_service.project_items_repo,
            "count_stats_by_project",
            AsyncMock(return_value=stats_by_project),
        ) as count_stats_mock,
        patch.object(
            push_service.push_repo,
            "list_for_users",
            AsyncMock(return_value=tokens),
        ) as list_tokens_mock,
    ):
        messages = await push_service.process_learning_nudges(session, redis, settings)

    assert len(messages) == 3
    list_projects_mock.assert_awaited_once()
    count_stats_mock.assert_awaited_once()
    list_tokens_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_learning_nudges_skips_programming_projects():
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings(push_learning_hour=0)
    user_id = uuid4()

    user = MagicMock()
    user.id = user_id
    user.timezone = "UTC"
    user.push_notifications_enabled = True
    user.locale = "en"

    project = MagicMock()
    project.id = uuid4()
    project.user_id = user_id
    project.title = "Python"
    project.kind = "programming"

    token = MagicMock()
    token.user_id = user_id
    token.expo_push_token = "ExponentPushToken[abc]"

    session.execute = AsyncMock(return_value=_users_execute_result([user]))
    redis.set = AsyncMock(return_value=True)

    with (
        patch.object(
            push_service.projects_repo,
            "list_for_users",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            push_service.project_items_repo,
            "count_stats_by_project",
            AsyncMock(return_value={}),
        ),
        patch.object(
            push_service.push_repo,
            "list_for_users",
            AsyncMock(return_value=[token]),
        ),
    ):
        messages = await push_service.process_learning_nudges(session, redis, settings)

    assert messages == []
    redis.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_push_cycle_disabled():
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings(push_enabled=False)

    count = await push_service.run_push_cycle(session, redis, settings)
    assert count == 0


@pytest.mark.asyncio
async def test_run_push_cycle_sends_expo_in_production():
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings(
        push_enabled=True,
        mock_llm_enabled=False,
        environment="production",
        server_todo_push_enabled=True,
    )

    with (
        patch.object(
            push_service,
            "process_todo_reminders",
            AsyncMock(
                return_value=[
                    push_service.OutboundPush(message={"to": "token"}),
                ]
            ),
        ),
        patch.object(push_service, "process_email_suggestions", AsyncMock(return_value=[])),
        patch.object(push_service, "process_learning_nudges", AsyncMock(return_value=[])),
        patch.object(push_service, "process_calendar_nudges", AsyncMock(return_value=[])),
        patch.object(
            push_service.expo_push_gateway,
            "send_push_messages",
            AsyncMock(
                return_value=push_service.expo_push_gateway.PushSendResult(
                    invalid_tokens=[],
                    delivered=[True],
                )
            ),
        ) as send_mock,
    ):
        count = await push_service.run_push_cycle(session, redis, settings)

    assert count == 1
    send_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_push_cycle_marks_todo_sent_only_after_expo_ok():
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings(
        push_enabled=True,
        mock_llm_enabled=False,
        environment="production",
        server_todo_push_enabled=True,
    )
    todo = MagicMock()
    todo.notification_sent_at = None

    outbound = [
        push_service.OutboundPush(
            message={"to": "ExponentPushToken[abc]"},
            todos=[todo],
        )
    ]

    with (
        patch.object(
            push_service,
            "process_todo_reminders",
            AsyncMock(return_value=outbound),
        ),
        patch.object(push_service, "process_email_suggestions", AsyncMock(return_value=[])),
        patch.object(push_service, "process_learning_nudges", AsyncMock(return_value=[])),
        patch.object(push_service, "process_calendar_nudges", AsyncMock(return_value=[])),
        patch.object(
            push_service.expo_push_gateway,
            "send_push_messages",
            AsyncMock(
                return_value=push_service.expo_push_gateway.PushSendResult(
                    invalid_tokens=[],
                    delivered=[True],
                )
            ),
        ),
    ):
        await push_service.run_push_cycle(session, redis, settings)

    assert todo.notification_sent_at is not None
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_push_cycle_does_not_mark_todo_when_expo_fails():
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings(
        push_enabled=True,
        mock_llm_enabled=False,
        environment="production",
        server_todo_push_enabled=True,
    )
    todo = MagicMock()
    todo.notification_sent_at = None

    outbound = [
        push_service.OutboundPush(
            message={"to": "ExponentPushToken[abc]"},
            todos=[todo],
        )
    ]

    with (
        patch.object(
            push_service,
            "process_todo_reminders",
            AsyncMock(return_value=outbound),
        ),
        patch.object(push_service, "process_email_suggestions", AsyncMock(return_value=[])),
        patch.object(push_service, "process_learning_nudges", AsyncMock(return_value=[])),
        patch.object(push_service, "process_calendar_nudges", AsyncMock(return_value=[])),
        patch.object(
            push_service.expo_push_gateway,
            "send_push_messages",
            AsyncMock(
                return_value=push_service.expo_push_gateway.PushSendResult(
                    invalid_tokens=[],
                    delivered=[False],
                )
            ),
        ),
    ):
        await push_service.run_push_cycle(session, redis, settings)

    assert todo.notification_sent_at is None
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_enqueue_push_receipts_stores_ticket_and_token():
    redis = AsyncMock()
    pipe = MagicMock()
    pipe.set = MagicMock()
    pipe.zadd = MagicMock()
    pipe.execute = AsyncMock()
    redis.pipeline = MagicMock(return_value=pipe)

    with patch("app.services.push_notifications.time.time", return_value=1000.0):
        await push_service.enqueue_push_receipts(
            redis,
            [("ticket-1", "ExponentPushToken[abc]")],
        )

    pipe.set.assert_called_once()
    pipe.zadd.assert_called_once_with(
        push_service.RECEIPT_PENDING_ZSET,
        {"ticket-1": 1000.0},
    )
    pipe.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_deferred_push_receipts_prunes_invalid_token():
    session = AsyncMock()
    redis = AsyncMock()
    redis.zrangebyscore = AsyncMock(side_effect=[[], ["ticket-1"]])
    redis.get = AsyncMock(return_value=b"ExponentPushToken[dead]")
    redis.delete = AsyncMock()
    redis.zrem = AsyncMock()

    with (
        patch(
            "app.services.push_notifications.expo_push_gateway.fetch_push_receipts",
            AsyncMock(
                return_value={
                    "ticket-1": {
                        "status": "error",
                        "details": {"error": "DeviceNotRegistered"},
                    }
                }
            ),
        ),
        patch.object(
            push_service.push_repo,
            "delete_by_token",
            AsyncMock(),
        ) as delete_mock,
        patch("app.services.push_notifications.time.time", return_value=10_000.0),
    ):
        await push_service.poll_deferred_push_receipts(session, redis)

    delete_mock.assert_awaited_once_with(session, "ExponentPushToken[dead]")
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_deferred_push_receipts_keeps_pending_receipts():
    session = AsyncMock()
    redis = AsyncMock()
    redis.zrangebyscore = AsyncMock(side_effect=[[], ["ticket-1"]])
    redis.get = AsyncMock()
    redis.delete = AsyncMock()
    redis.zrem = AsyncMock()

    with (
        patch(
            "app.services.push_notifications.expo_push_gateway.fetch_push_receipts",
            AsyncMock(return_value={"ticket-1": {"status": "pending"}}),
        ),
        patch.object(push_service.push_repo, "delete_by_token", AsyncMock()) as delete_mock,
        patch("app.services.push_notifications.time.time", return_value=10_000.0),
    ):
        await push_service.poll_deferred_push_receipts(session, redis)

    delete_mock.assert_not_awaited()
    redis.zrem.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_push_cycle_enqueues_receipt_tickets():
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings(
        push_enabled=True,
        mock_llm_enabled=False,
        environment="production",
        server_todo_push_enabled=True,
    )

    with (
        patch.object(
            push_service,
            "poll_deferred_push_receipts",
            AsyncMock(),
        ),
        patch.object(
            push_service,
            "process_todo_reminders",
            AsyncMock(
                return_value=[
                    push_service.OutboundPush(message={"to": "ExponentPushToken[abc]"}),
                ]
            ),
        ),
        patch.object(push_service, "process_email_suggestions", AsyncMock(return_value=[])),
        patch.object(push_service, "process_learning_nudges", AsyncMock(return_value=[])),
        patch.object(push_service, "process_calendar_nudges", AsyncMock(return_value=[])),
        patch.object(
            push_service.expo_push_gateway,
            "send_push_messages",
            AsyncMock(
                return_value=push_service.expo_push_gateway.PushSendResult(
                    invalid_tokens=[],
                    delivered=[True],
                    receipt_tickets=[("ticket-1", "ExponentPushToken[abc]")],
                )
            ),
        ),
        patch.object(
            push_service,
            "enqueue_push_receipts",
            AsyncMock(),
        ) as enqueue_mock,
    ):
        await push_service.run_push_cycle(session, redis, settings)

    enqueue_mock.assert_awaited_once_with(
        redis,
        [("ticket-1", "ExponentPushToken[abc]")],
    )


@pytest.mark.asyncio
async def test_run_push_cycle_marks_sent_on_ticket_without_receipt_poll():
    """Ticket accept marks delivery; receipt polling is deferred for token pruning only."""
    session = AsyncMock()
    redis = AsyncMock()
    settings = Settings(
        push_enabled=True,
        mock_llm_enabled=False,
        environment="production",
        server_todo_push_enabled=True,
    )
    todo = MagicMock()
    todo.id = uuid4()
    todo.content = "Call dentist"
    todo.notification_sent_at = None

    with (
        patch.object(push_service, "poll_deferred_push_receipts", AsyncMock()),
        patch.object(
            push_service,
            "process_todo_reminders",
            AsyncMock(
                return_value=[
                    push_service.OutboundPush(
                        message={"to": "ExponentPushToken[abc]"},
                        todos=[todo],
                    ),
                ]
            ),
        ),
        patch.object(push_service, "process_email_suggestions", AsyncMock(return_value=[])),
        patch.object(push_service, "process_learning_nudges", AsyncMock(return_value=[])),
        patch.object(push_service, "process_calendar_nudges", AsyncMock(return_value=[])),
        patch.object(
            push_service.expo_push_gateway,
            "send_push_messages",
            AsyncMock(
                return_value=push_service.expo_push_gateway.PushSendResult(
                    invalid_tokens=[],
                    delivered=[True],
                    receipt_tickets=[("ticket-1", "ExponentPushToken[abc]")],
                )
            ),
        ),
        patch.object(push_service, "enqueue_push_receipts", AsyncMock()) as enqueue_mock,
    ):
        await push_service.run_push_cycle(session, redis, settings)

    assert todo.notification_sent_at is not None
    enqueue_mock.assert_awaited_once()
    session.commit.assert_awaited()


def test_append_outbound_dedupes_duplicate_tokens():
    out: list[push_service.OutboundPush] = []
    token_a = MagicMock()
    token_a.expo_push_token = "ExponentPushToken[abc]"
    token_b = MagicMock()
    token_b.expo_push_token = "ExponentPushToken[abc]"

    push_service._append_outbound(
        out,
        [token_a, token_b],
        title="Reminder",
        body="Call dentist",
        data={"type": "todo_reminder"},
    )

    assert len(out) == 1
    assert out[0].message["to"] == "ExponentPushToken[abc]"


@pytest.mark.asyncio
async def test_upsert_prunes_stale_tokens_for_device():
    from app.repositories import push_tokens as repo

    session = AsyncMock()
    user_id = uuid4()
    existing = MagicMock()
    session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=existing))

    await repo.upsert(
        session,
        user_id=user_id,
        expo_push_token="ExponentPushToken[new]",
        platform="ios",
        device_id="device-1",
    )

    assert session.execute.await_count == 2
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_process_calendar_nudges_sends_once_per_event():
    from datetime import UTC, datetime, timedelta

    from app.gateways.google_calendar_gateway import CalendarEvent

    session = AsyncMock()
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    user_id = uuid4()
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)

    user = MagicMock()
    user.id = user_id
    user.push_notifications_enabled = True
    user.locale = "en"
    user.timezone = "UTC"

    token = MagicMock()
    token.expo_push_token = "ExponentPushToken[cal]"

    event = CalendarEvent(
        id="evt-42",
        title="Standup",
        start=now + timedelta(minutes=12),
        end=now + timedelta(minutes=42),
    )

    settings = Settings(calendar_nudge_enabled=True, calendar_nudge_lead_minutes=15)

    session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[user])))
        )
    )

    with (
        patch.object(
            push_service.calendar_service,
            "fetch_upcoming_events",
            AsyncMock(return_value=[event]),
        ),
        patch.object(
            push_service.push_repo,
            "list_for_user",
            AsyncMock(return_value=[token]),
        ),
        patch.object(
            push_service.google_calendar_gateway,
            "is_configured",
            MagicMock(return_value=True),
        ),
    ):
        messages = await push_service.process_calendar_nudges(
            session,
            redis,
            settings,
            now=now,
        )

    assert len(messages) == 1
    assert messages[0].message["title"] == "Upcoming meeting"
    assert "Standup" in messages[0].message["body"]
    assert messages[0].message["data"]["type"] == "calendar_nudge"
    redis.set.assert_awaited()

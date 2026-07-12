from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services import reminder_emails


def _settings(**kwargs: object) -> Settings:
    s = Settings()
    for key, value in kwargs.items():
        setattr(s, key, value)
    return s


def _user(*, email_reminders: bool = True, email: str = "u@test.local") -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    user.email = email
    user.name = "Ada"
    user.locale = "en"
    user.timezone = "UTC"
    user.email_reminders_enabled = email_reminders
    user.reminder_lead_minutes = 10
    return user


def _todo(*, due_at: datetime, user_id=None) -> MagicMock:
    todo = MagicMock()
    todo.id = uuid4()
    todo.user_id = user_id or uuid4()
    todo.content = "Call mom"
    todo.due_at = due_at
    todo.checked = False
    todo.email_sent_at = None
    return todo


@pytest.mark.asyncio
async def test_process_todo_reminder_emails_sends_and_marks():
    now = datetime.now(UTC)
    user = _user()
    todo = _todo(due_at=now + timedelta(minutes=5), user_id=user.id)
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = [(todo, user)]
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()

    with patch(
        "app.services.reminder_emails.tx_email.send_todo_reminder",
        AsyncMock(return_value=True),
    ) as send:
        count = await reminder_emails.process_todo_reminder_emails(session, _settings(), now=now)

    assert count == 1
    assert todo.email_sent_at == now
    send.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_todo_reminder_emails_skips_when_opted_out():
    now = datetime.now(UTC)
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    count = await reminder_emails.process_todo_reminder_emails(session, _settings(), now=now)
    assert count == 0
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_run_email_reminder_cycle_respects_kill_switch():
    session = AsyncMock()
    redis = AsyncMock()
    count = await reminder_emails.run_email_reminder_cycle(
        session, redis, _settings(email_reminders_scheduler_enabled=False)
    )
    assert count == 0


@pytest.mark.asyncio
async def test_process_learning_nudge_emails_sends_when_due():
    user = _user()
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [user]
    session.execute = AsyncMock(return_value=result)
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock()

    project = MagicMock()
    project.id = uuid4()
    project.user_id = user.id
    project.kind = "language"
    project.title = "Spanish"

    with (
        patch(
            "app.services.reminder_emails.user_local_hour",
            return_value=10,
        ),
        patch(
            "app.services.reminder_emails.projects_repo.list_for_users",
            AsyncMock(return_value=[project]),
        ),
        patch(
            "app.services.reminder_emails.project_items_repo.count_stats_by_project",
            AsyncMock(
                return_value={
                    project.id: {
                        "total": 5,
                        "due_for_review": 2,
                        "new_count": 0,
                    }
                }
            ),
        ),
        patch(
            "app.services.reminder_emails.tx_email.send_learning_nudge",
            AsyncMock(return_value=True),
        ) as send,
    ):
        count = await reminder_emails.process_learning_nudge_emails(session, redis, _settings())

    assert count == 1
    send.assert_awaited_once()

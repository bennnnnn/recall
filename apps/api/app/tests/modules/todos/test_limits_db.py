"""One account can neither keep an endless list nor fill a reminder cycle (security
review, 2026-11-25): open to-dos stop at ``OPEN_TODOS_MAX``, and each channel's cycle
sends one account at most ``REMINDERS_PER_ACCOUNT_PER_CYCLE`` before the rest wait.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import insert

from app.core.config import Settings
from app.gateways.email_gateway import EmailOutcome, EmailResult
from app.models.orm import PushToken, TodoItem
from app.modules.notifications import push as push_service
from app.modules.notifications import reminder_email
from app.modules.todos import repository as todos_repo
from app.modules.todos.limits import (
    OPEN_TODOS_MAX,
    REMINDERS_PER_ACCOUNT_PER_CYCLE,
    AccountShare,
    TodoLimitError,
)
from app.repositories import users as users_repo

# Far from any row another test may leave behind; the reminder scans are global.
NOW = datetime(2032, 5, 3, 12, 0, tzinfo=UTC)


async def _user(session):
    user = await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Limits",
        avatar_url=None,
        google_sub=str(uuid4()),
    )
    user.email_reminders_enabled = True
    session.add(
        PushToken(user_id=user.id, expo_push_token=f"ExponentPushToken[{uuid4()}]", platform="ios")
    )
    await session.flush()
    return user


async def _open_todos(session, user_id, count: int, *, due_at: datetime | None = None) -> None:
    await session.execute(
        insert(TodoItem),
        [
            {
                "id": uuid4(),
                "user_id": user_id,
                "content": f"Row {n}",
                "topic": "General",
                "due_at": due_at,
                "due_has_time": True,
                "due_set_at": due_at - timedelta(hours=2) if due_at else None,
            }
            for n in range(count)
        ],
    )


def test_an_accounts_share_is_its_own() -> None:
    share = AccountShare(per_account=2)
    a, b = uuid4(), uuid4()
    assert [share.take(a), share.take(a), share.take(a)] == [True, True, False]
    assert share.take(b) is True


async def test_an_add_past_the_cap_is_refused_and_a_completed_one_makes_room(db_session):
    user = await _user(db_session)
    await _open_todos(db_session, user.id, OPEN_TODOS_MAX - 1)
    last = await todos_repo.create(db_session, user_id=user.id, content="The last", commit=False)
    with pytest.raises(TodoLimitError) as refused:
        await todos_repo.create(db_session, user_id=user.id, content="One more", commit=False)
    assert refused.value.status_code == 409
    assert refused.value.code == "todo_limit"
    # Done ones do not count; reopening one at the cap is an add, refused too.
    await todos_repo.update(db_session, last, checked=True, commit=False)
    await db_session.flush()
    added = await todos_repo.create(db_session, user_id=user.id, content="Room", commit=False)
    with pytest.raises(TodoLimitError):
        await todos_repo.update(db_session, last, checked=False, commit=False)
    await todos_repo.update(db_session, added, content="Renamed", commit=False)  # an edit is fine


async def test_another_accounts_list_never_counts(db_session):
    full, other = await _user(db_session), await _user(db_session)
    await _open_todos(db_session, full.id, OPEN_TODOS_MAX)
    assert await todos_repo.create(db_session, user_id=other.id, content="Mine", commit=False)


async def test_one_accounts_backlog_never_holds_back_anothers_push(db_session):
    flood, other = await _user(db_session), await _user(db_session)
    # The flood is due first, so the queue's order alone would send all of it first.
    await _open_todos(db_session, flood.id, REMINDERS_PER_ACCOUNT_PER_CYCLE + 30, due_at=NOW)
    await _open_todos(db_session, other.id, 1, due_at=NOW + timedelta(seconds=1))
    await db_session.flush()

    page = await push_service.collect_push_page(db_session, now=NOW)
    kept = push_service.within_share(AccountShare(), page.messages)
    owners = [item.todos[0].user_id for item in kept]
    assert owners.count(flood.id) == REMINDERS_PER_ACCOUNT_PER_CYCLE
    assert owners.count(other.id) == 1


async def test_a_held_push_never_takes_a_sendable_ones_share(db_session):
    """Reminders under a hold are passed by first: the account's next 20 still go."""
    flood = await _user(db_session)
    await _open_todos(db_session, flood.id, REMINDERS_PER_ACCOUNT_PER_CYCLE * 2, due_at=NOW)
    await db_session.flush()
    page = await push_service.collect_push_page(db_session, now=NOW)
    first = {push_service._todo_key(item.todos[0]) for item in page.messages[:20]}
    backoff = MagicMock(held=AsyncMock(return_value=first))
    sendable = await push_service.without_held(backoff, page.messages)
    kept = push_service.within_share(AccountShare(), sendable)
    assert len(kept) == REMINDERS_PER_ACCOUNT_PER_CYCLE
    assert not {push_service._todo_key(item.todos[0]) for item in kept} & first


def test_a_reminder_on_two_devices_counts_once() -> None:
    user_id, todo = uuid4(), MagicMock(id=uuid4())
    todo.user_id = user_id
    phone, tablet = MagicMock(todos=[todo]), MagicMock(todos=[todo])
    assert push_service.within_share(AccountShare(per_account=1), [phone, tablet]) == [
        phone,
        tablet,
    ]


async def test_one_accounts_backlog_never_holds_back_anothers_email(db_session):
    flood, other = await _user(db_session), await _user(db_session)
    await _open_todos(db_session, flood.id, REMINDERS_PER_ACCOUNT_PER_CYCLE + 30, due_at=NOW)
    await _open_todos(db_session, other.id, 1, due_at=NOW + timedelta(seconds=1))
    await db_session.flush()
    flood_email, other_email = flood.email, other.email  # the cycle's rollback expires rows

    sent_to: list[str] = []

    async def send(_settings: object, recipient: MagicMock, **_kwargs: object) -> EmailResult:
        sent_to.append(recipient.email)
        return EmailResult(EmailOutcome.SENT)

    with (
        patch.object(reminder_email.tx_email, "send_todo_reminder", send),
        patch.object(reminder_email, "mark_reminder_emailed", AsyncMock(return_value=True)),
    ):
        await reminder_email.process_todo_reminder_emails(db_session, Settings(), now=NOW)
    assert sent_to.count(flood_email) == REMINDERS_PER_ACCOUNT_PER_CYCLE
    assert sent_to.count(other_email) == 1


async def test_a_held_email_never_takes_a_sendable_ones_share(db_session):
    flood = await _user(db_session)
    await _open_todos(db_session, flood.id, REMINDERS_PER_ACCOUNT_PER_CYCLE * 2, due_at=NOW)
    await db_session.flush()
    sent: list[str] = []

    async def held(keys: list[str]) -> set[str]:
        return set(keys[:REMINDERS_PER_ACCOUNT_PER_CYCLE])  # the first 20 wait out a hold

    async def send(_settings: object, _recipient: MagicMock, **kwargs: object) -> EmailResult:
        sent.append(str(kwargs["idempotency_key"]))
        return EmailResult(EmailOutcome.SENT)

    with (
        patch.object(reminder_email.tx_email, "send_todo_reminder", send),
        patch.object(reminder_email, "mark_reminder_emailed", AsyncMock(return_value=True)),
    ):
        await reminder_email.process_todo_reminder_emails(
            db_session, Settings(), now=NOW, backoff=MagicMock(held=held)
        )
    assert len(sent) == REMINDERS_PER_ACCOUNT_PER_CYCLE

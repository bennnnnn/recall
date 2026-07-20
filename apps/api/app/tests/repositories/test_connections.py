"""Tests for connection and reminder repositories."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def fake_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_suggested_reminders_crud(fake_session):
    from app.repositories import suggested_reminders as repo

    user_id = uuid4()
    reminder_id = uuid4()
    row = MagicMock()
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[row])))
    )

    pending = await repo.list_pending_for_user(fake_session, user_id)
    assert pending == [row]

    fake_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=row))
    assert await repo.get_by_id(fake_session, reminder_id, user_id) is row
    assert await repo.get_by_message_id(fake_session, user_id, "g1") is row

    fake_session.execute.return_value = MagicMock(all=MagicMock(return_value=[("g1",), ("g2",)]))
    assert await repo.existing_message_ids(fake_session, user_id, ["g1", "g2", "g3"]) == {
        "g1",
        "g2",
    }
    assert await repo.existing_message_ids(fake_session, user_id, []) == set()

    created = await repo.create(
        fake_session,
        user_id=user_id,
        gmail_message_id="g1",
        title="Interview",
        due_at=None,
        notes=None,
        confidence=0.8,
        source_snippet="snippet",
    )
    fake_session.add.assert_called_once()
    assert created is not None

    todo_id = uuid4()
    marked = await repo.mark_added(fake_session, row, todo_id)
    assert marked.status == "added"
    assert marked.todo_id == todo_id

    dismissed = await repo.mark_dismissed(fake_session, row)
    assert dismissed.status == "dismissed"

    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[row])))
    )
    deleted = await repo.delete_for_user(fake_session, user_id)
    assert deleted == 1


@pytest.mark.asyncio
async def test_push_tokens_upsert_and_delete(fake_session):
    from app.repositories import push_tokens as repo

    user_id = uuid4()
    token = "ExponentPushToken[abc]"
    existing = MagicMock()
    fake_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=existing)
    )

    updated = await repo.upsert(
        fake_session,
        user_id=user_id,
        expo_push_token=token,
        platform="ios",
    )
    assert updated.user_id == user_id
    fake_session.commit.assert_awaited()

    fake_session.execute.return_value = MagicMock(rowcount=1)
    assert await repo.delete_token(fake_session, user_id, token) is True
    assert await repo.delete_by_token(fake_session, token) == 1

    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[existing])))
    )
    rows = await repo.list_for_user(fake_session, user_id)
    assert rows == [existing]


@pytest.mark.asyncio
async def test_calendar_connection_upsert_and_delete(fake_session):
    from app.repositories import calendar_connections as repo

    user_id = uuid4()
    fake_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    created = await repo.upsert(
        fake_session,
        user_id=user_id,
        google_email="me@example.com",
        refresh_token="rt",
        scopes="calendar.readonly",
    )
    fake_session.add.assert_called_once()
    assert created.google_email == "me@example.com"

    fake_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=created)
    )
    assert await repo.delete_for_user(fake_session, user_id) is True
    fake_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    assert await repo.delete_for_user(fake_session, user_id) is False


@pytest.mark.asyncio
async def test_gmail_connection_repo(fake_session):
    from app.repositories import gmail_connections as repo

    user_id = uuid4()
    row = MagicMock()
    fake_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=row))

    assert await repo.get_for_user(fake_session, user_id) is row

    fake_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    created = await repo.upsert(
        fake_session,
        user_id=user_id,
        google_email="me@example.com",
        refresh_token="rt",
        scopes="gmail.readonly",
    )
    fake_session.add.assert_called_once()

    fake_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=created)
    )
    await repo.update_last_sync(fake_session, user_id)
    assert created.last_sync_at is not None

    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[created])))
    )
    assert await repo.list_all(fake_session) == [created]

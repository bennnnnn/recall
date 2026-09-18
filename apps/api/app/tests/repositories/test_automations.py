"""Mocked-session unit tests for app.repositories.automations."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.repositories import automations as repo


@pytest.fixture
def fake_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_create_flushes_only_when_commit_false(fake_session):
    user_id, chat_id = uuid4(), uuid4()

    automation = await repo.create(
        fake_session,
        user_id=user_id,
        chat_id=chat_id,
        prompt="  Find L3 backend jobs  ",
        frequency="daily",
        next_run_at=datetime(2026, 9, 18, 8, tzinfo=UTC),
        commit=False,
    )

    assert automation.prompt == "Find L3 backend jobs"  # stripped
    assert automation.status == "active"
    fake_session.add.assert_called_once_with(automation)
    fake_session.flush.assert_awaited_once()
    fake_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_create_commits_and_refreshes_by_default(fake_session):
    automation = await repo.create(
        fake_session,
        user_id=uuid4(),
        chat_id=uuid4(),
        prompt="Find jobs",
        frequency="once",
        next_run_at=datetime(2026, 9, 18, 8, tzinfo=UTC),
    )

    fake_session.commit.assert_awaited_once()
    fake_session.refresh.assert_awaited_once_with(automation)


@pytest.mark.asyncio
async def test_get_by_id_scopes_to_user(fake_session):
    result = MagicMock()
    fake_session.execute = AsyncMock(return_value=result)

    await repo.get_by_id(fake_session, uuid4(), uuid4())

    fake_session.execute.assert_awaited_once()
    result.scalar_one_or_none.assert_called_once()


@pytest.mark.asyncio
async def test_update_only_sets_known_attributes(fake_session):
    automation = MagicMock()
    automation.status = "active"

    updated = await repo.update(fake_session, automation, status="paused", bogus_field="x")

    assert updated.status == "paused"
    assert not hasattr(automation, "bogus_field") or automation.bogus_field == "x"
    fake_session.commit.assert_awaited_once()
    fake_session.refresh.assert_awaited_once_with(automation)


@pytest.mark.asyncio
async def test_delete_by_id_returns_false_when_missing(fake_session, monkeypatch):
    monkeypatch.setattr(repo, "get_by_id", AsyncMock(return_value=None))

    deleted = await repo.delete_by_id(fake_session, uuid4(), uuid4())

    assert deleted is False
    fake_session.delete.assert_not_called()
    fake_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_delete_by_id_deletes_and_commits_when_found(fake_session, monkeypatch):
    automation = MagicMock()
    monkeypatch.setattr(repo, "get_by_id", AsyncMock(return_value=automation))

    deleted = await repo.delete_by_id(fake_session, uuid4(), uuid4())

    assert deleted is True
    fake_session.delete.assert_awaited_once_with(automation)
    fake_session.commit.assert_awaited_once()

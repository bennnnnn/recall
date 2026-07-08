"""Tests for app.repositories.todos."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.repositories import todos as repo


def _todo(todo_id, *, sort_order=None, topic="General"):
    item = MagicMock()
    item.id = todo_id
    item.sort_order = sort_order
    item.topic = topic
    return item


@pytest.fixture
def fake_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_reorder_returns_empty_list_without_querying(fake_session):
    result = await repo.reorder(fake_session, uuid4(), [])

    assert result == []
    fake_session.execute.assert_not_called()
    fake_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_reorder_bulk_fetches_and_commits_once(fake_session):
    user_id = uuid4()
    id_a, id_b = uuid4(), uuid4()
    todo_a, todo_b = _todo(id_a), _todo(id_b)

    fetch_result = MagicMock()
    fetch_result.scalars.return_value.all.return_value = [todo_a, todo_b]
    refresh_result = MagicMock()
    refresh_result.scalars.return_value.all.return_value = [todo_a, todo_b]
    fake_session.execute = AsyncMock(side_effect=[fetch_result, refresh_result])

    updated = await repo.reorder(fake_session, user_id, [(id_a, 2, "work"), (id_b, 1, None)])

    assert [t.id for t in updated] == [id_a, id_b]
    assert todo_a.sort_order == 2
    assert todo_a.topic == "work"
    assert todo_b.sort_order == 1
    assert todo_b.topic == "General"  # untouched — topic was None in the request
    # Exactly one commit for the whole batch, not one per item.
    fake_session.commit.assert_awaited_once()
    assert fake_session.execute.await_count == 2


@pytest.mark.asyncio
async def test_reorder_skips_ids_not_found_or_owned_by_another_user(fake_session):
    user_id = uuid4()
    id_a, missing_id = uuid4(), uuid4()
    todo_a = _todo(id_a)

    fetch_result = MagicMock()
    fetch_result.scalars.return_value.all.return_value = [todo_a]
    refresh_result = MagicMock()
    refresh_result.scalars.return_value.all.return_value = [todo_a]
    fake_session.execute = AsyncMock(side_effect=[fetch_result, refresh_result])

    updated = await repo.reorder(fake_session, user_id, [(id_a, 1, None), (missing_id, 2, None)])

    assert [t.id for t in updated] == [id_a]
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reorder_no_matches_skips_commit(fake_session):
    fetch_result = MagicMock()
    fetch_result.scalars.return_value.all.return_value = []
    fake_session.execute = AsyncMock(return_value=fetch_result)

    updated = await repo.reorder(fake_session, uuid4(), [(uuid4(), 1, None)])

    assert updated == []
    fake_session.commit.assert_not_called()
    fake_session.execute.assert_awaited_once()

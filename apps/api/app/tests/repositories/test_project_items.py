"""Tests for app.repositories.project_items."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.repositories import project_items as repo


def _item(
    *,
    content: str = "hello",
    list_title: str = "General",
    status: str | None = "new",
    mastered: bool = False,
    created_at: datetime | None = None,
    last_reviewed_at: datetime | None = None,
):
    item = MagicMock()
    item.content = content
    item.list_title = list_title
    item.status = status
    item.mastered = mastered
    item.mastered_at = None
    item.last_incorrect_at = None
    item.created_at = created_at or datetime.now(UTC)
    item.last_reviewed_at = last_reviewed_at
    item.due_at = None
    return item


@pytest.fixture
def fake_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_list_for_user_returns_items(fake_session):
    mock_item = _item()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_item]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    fake_session.execute.return_value = mock_result

    result = await repo.list_for_user(fake_session, uuid4(), project_id=uuid4())

    assert result == [mock_item]


@pytest.mark.asyncio
async def test_list_recent_for_user_returns_items(fake_session):
    mock_item = _item()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_item]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    fake_session.execute.return_value = mock_result

    result = await repo.list_recent_for_user(fake_session, uuid4(), project_id=uuid4())

    assert result == [mock_item]


@pytest.mark.asyncio
async def test_list_quiz_exclusion_contents_queries_mastered(fake_session):
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = ["Treaty of Versailles", "Colossus of Rhodes"]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    fake_session.execute.return_value = mock_result

    result = await repo.list_quiz_exclusion_contents(
        fake_session, uuid4(), uuid4(), include_learning=True, limit=50
    )

    assert result == ["Treaty of Versailles", "Colossus of Rhodes"]
    fake_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_find_quiz_candidates_queries_project_content(fake_session):
    mock_item = _item(content="Colossus")
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_item]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    fake_session.execute.return_value = mock_result

    result = await repo.find_quiz_candidates(fake_session, uuid4(), uuid4(), "Colossus")

    assert result == [mock_item]
    fake_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_id_returns_item(fake_session):
    mock_item = _item()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_item
    fake_session.execute.return_value = mock_result

    result = await repo.get_by_id(fake_session, uuid4(), uuid4())

    assert result is mock_item


@pytest.mark.asyncio
async def test_count_for_project_returns_scalar_count(fake_session):
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 42
    fake_session.execute.return_value = mock_result

    result = await repo.count_for_project(fake_session, uuid4(), uuid4())

    assert result == 42
    fake_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_count_stats_aggregates_statuses(fake_session):
    project_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)
    items = [
        _item(status="new", created_at=now),
        _item(status="learning", created_at=now - timedelta(days=8)),
        _item(status="mastered", mastered=True, created_at=now),
        _item(status="learning", last_reviewed_at=now - timedelta(hours=30)),
    ]
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=items)))
    )

    stats = await repo.count_stats(fake_session, project_id, user_id)

    assert stats["total"] == 4
    assert stats["new_count"] == 1
    assert stats["learning_count"] == 2
    assert stats["mastered_count"] == 1
    assert stats["added_this_week"] == 3
    assert stats["due_for_review"] >= 2


@pytest.mark.asyncio
async def test_list_for_projects_returns_empty_without_querying(fake_session):
    result = await repo.list_for_projects(fake_session, [])

    assert result == []
    fake_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_count_stats_by_project_groups_items_per_project(fake_session):
    project_a = uuid4()
    project_b = uuid4()
    now = datetime.now(UTC)

    item_a = _item(status="new", created_at=now)
    item_a.project_id = project_a
    item_b1 = _item(status="mastered", mastered=True, created_at=now)
    item_b1.project_id = project_b
    item_b2 = _item(status="learning", created_at=now)
    item_b2.project_id = project_b

    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[item_a, item_b1, item_b2]))
        )
    )

    stats = await repo.count_stats_by_project(fake_session, [project_a, project_b])

    assert fake_session.execute.await_count == 1
    assert stats[project_a]["total"] == 1
    assert stats[project_a]["new_count"] == 1
    assert stats[project_b]["total"] == 2
    assert stats[project_b]["mastered_count"] == 1


@pytest.mark.asyncio
async def test_count_stats_by_project_includes_projects_with_no_items(fake_session):
    project_id = uuid4()
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    )

    stats = await repo.count_stats_by_project(fake_session, [project_id])

    assert stats[project_id]["total"] == 0


@pytest.mark.asyncio
async def test_list_by_activity_date_queries_mastered_window(fake_session):
    matched = [_item(content="book", status="mastered", mastered=True)]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = matched
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    fake_session.execute.return_value = mock_result

    from datetime import date

    page = await repo.list_by_activity_date(
        fake_session,
        uuid4(),
        uuid4(),
        date(2026, 7, 1),
        timezone_name="UTC",
        limit=25,
        offset=0,
    )

    fake_session.execute.assert_awaited_once()
    assert page == matched


@pytest.mark.asyncio
async def test_list_missed_by_activity_date_queries_incorrect_window(fake_session):
    matched = [_item(content="book", status="learning", mastered=False)]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = matched
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    fake_session.execute.return_value = mock_result

    from datetime import date

    page = await repo.list_missed_by_activity_date(
        fake_session,
        uuid4(),
        uuid4(),
        date(2026, 7, 1),
        timezone_name="UTC",
        limit=25,
        offset=0,
    )

    fake_session.execute.assert_awaited_once()
    assert page == matched


@pytest.mark.asyncio
async def test_create_normalizes_list_title(fake_session):
    created = await repo.create(
        fake_session,
        user_id=uuid4(),
        project_id=uuid4(),
        content="  hello  ",
        list_title=" Travel ",
    )

    fake_session.add.assert_called_once()
    fake_session.commit.assert_awaited_once()
    assert created.list_title == "Travel"


@pytest.mark.asyncio
async def test_update_syncs_mastered_fields(fake_session):
    item = _item(status="new")
    item.status = "new"
    item.mastered = False
    item.mastered_at = None

    updated = await repo.update(fake_session, item, status="mastered")

    assert updated.status == "mastered"
    assert updated.mastered is True
    assert updated.mastered_at is not None


@pytest.mark.asyncio
async def test_delete_by_id_returns_rowcount(fake_session):
    mock_result = MagicMock()
    mock_result.rowcount = 1
    fake_session.execute.return_value = mock_result

    deleted = await repo.delete_by_id(fake_session, uuid4(), uuid4())

    assert deleted is True


@pytest.mark.asyncio
async def test_delete_by_list_empty_title_returns_zero(fake_session):
    deleted = await repo.delete_by_list(fake_session, uuid4(), uuid4(), "   ")

    assert deleted == 0
    fake_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_update_records_review_on_status_change(fake_session):
    item = _item(status="new")
    item.review_count = 0
    item.last_reviewed_at = None
    item.mastered = False

    await repo.update(fake_session, item, status="mastered")

    assert item.status == "mastered"
    assert item.mastered is True
    assert item.review_count == 1
    assert item.last_reviewed_at is not None
    fake_session.commit.assert_awaited()

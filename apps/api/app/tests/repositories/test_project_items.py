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
async def test_list_for_projects_returns_empty_without_querying(fake_session):
    result = await repo.list_for_projects(fake_session, [])

    assert result == []
    fake_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_list_by_activity_date_queries_mastered_window(fake_session):
    matched = [_item(content="book", status="mastered", mastered=True)]
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = matched
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    fake_session.execute.return_value = mock_result

    start = datetime(2026, 7, 1, tzinfo=UTC)
    end = start + timedelta(days=1)
    page = await repo.list_by_activity_date(
        fake_session,
        uuid4(),
        uuid4(),
        start=start,
        end=end,
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

    start = datetime(2026, 7, 1, tzinfo=UTC)
    end = start + timedelta(days=1)
    page = await repo.list_missed_by_activity_date(
        fake_session,
        uuid4(),
        uuid4(),
        start=start,
        end=end,
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
async def test_update_item_records_review_on_status_change(fake_session):
    from app.services.projects.items import update_item

    item = _item(status="new")
    item.review_count = 0
    item.last_reviewed_at = None
    item.mastered = False
    item.ease_factor = 2.5
    item.interval_days = 0

    await update_item(fake_session, item, status="mastered")

    assert item.status == "mastered"
    assert item.mastered is True
    assert item.review_count == 1
    assert item.last_reviewed_at is not None
    fake_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_update_item_learning_registers_miss_for_failed_count(fake_session):
    """Manual Needs review / Failed must stamp a miss so missed_today is not stuck at 0."""
    from app.models.orm import QuizMissEvent
    from app.services.projects.items import update_item

    item = _item(status="mastered")
    item.mastered = True
    item.review_count = 2
    item.last_incorrect_at = None
    item.ease_factor = 2.5
    item.interval_days = 6

    await update_item(fake_session, item, status="learning")

    assert item.status == "learning"
    assert item.mastered is False
    assert item.last_incorrect_at is not None
    added = [call.args[0] for call in fake_session.add.call_args_list]
    assert any(isinstance(obj, QuizMissEvent) for obj in added)

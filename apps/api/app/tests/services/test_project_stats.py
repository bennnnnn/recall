"""Tests for project item stats aggregation (moved out of the repository)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.projects import stats as stats_service


def _item(
    *,
    content: str = "hello",
    status: str | None = "new",
    mastered: bool = False,
    created_at: datetime | None = None,
    last_reviewed_at: datetime | None = None,
):
    item = MagicMock()
    item.content = content
    item.status = status
    item.mastered = mastered
    item.mastered_at = None
    item.last_incorrect_at = None
    item.created_at = created_at or datetime.now(UTC)
    item.last_reviewed_at = last_reviewed_at
    item.due_at = None
    return item


@pytest.mark.asyncio
async def test_count_stats_aggregates_statuses():
    project_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)
    items = [
        _item(status="new", created_at=now),
        _item(status="learning", created_at=now - timedelta(days=8)),
        _item(status="mastered", mastered=True, created_at=now),
        _item(status="learning", last_reviewed_at=now - timedelta(hours=30)),
    ]
    fake_session = AsyncMock()
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=items)))
    )

    stats = await stats_service.count_stats(fake_session, project_id, user_id)

    assert stats["total"] == 4
    assert stats["new_count"] == 1
    assert stats["learning_count"] == 2
    assert stats["mastered_count"] == 1
    assert stats["added_this_week"] == 3
    assert stats["due_for_review"] >= 2


@pytest.mark.asyncio
async def test_count_stats_by_project_groups_items_per_project():
    project_a = uuid4()
    project_b = uuid4()
    now = datetime.now(UTC)

    item_a = _item(status="new", created_at=now)
    item_a.project_id = project_a
    item_b1 = _item(status="mastered", mastered=True, created_at=now)
    item_b1.project_id = project_b
    item_b2 = _item(status="learning", created_at=now)
    item_b2.project_id = project_b

    fake_session = AsyncMock()
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[item_a, item_b1, item_b2]))
        )
    )

    stats = await stats_service.count_stats_by_project(fake_session, [project_a, project_b])

    assert fake_session.execute.await_count == 1
    assert stats[project_a]["total"] == 1
    assert stats[project_a]["new_count"] == 1
    assert stats[project_b]["total"] == 2
    assert stats[project_b]["mastered_count"] == 1


@pytest.mark.asyncio
async def test_count_stats_by_project_includes_projects_with_no_items():
    project_id = uuid4()
    fake_session = AsyncMock()
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    )

    stats = await stats_service.count_stats_by_project(fake_session, [project_id])

    assert stats[project_id]["total"] == 0

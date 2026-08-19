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
async def test_count_stats_aggregates_statuses(monkeypatch):
    """count_stats delegates to the SQL repo function."""
    project_id = uuid4()
    user_id = uuid4()
    expected = {
        "total": 4,
        "new_count": 1,
        "learning_count": 2,
        "mastered_count": 1,
        "added_this_week": 3,
        "due_for_review": 2,
        "mastered_today": 0,
        "missed_today": 0,
        "pending_today": 0,
        "last_mastery_at": None,
    }
    fake_session = AsyncMock()

    async def _count_stats_sql(session, pid, uid, *, timezone_name="UTC"):
        assert session is fake_session
        assert pid == project_id
        assert uid == user_id
        return expected

    monkeypatch.setattr(
        "app.services.projects.stats.project_items_repo.count_stats_sql",
        _count_stats_sql,
    )

    stats = await stats_service.count_stats(fake_session, project_id, user_id)
    assert stats == expected


@pytest.mark.asyncio
async def test_count_stats_by_project_groups_items_per_project(monkeypatch):
    """count_stats_by_project delegates to the SQL repo function."""
    project_a = uuid4()
    project_b = uuid4()
    expected = {
        project_a: {"total": 1, "new_count": 1, "mastered_count": 0},
        project_b: {"total": 2, "mastered_count": 1},
    }
    fake_session = AsyncMock()

    async def _by_project_sql(session, project_ids, *, timezone_by_project=None):
        assert session is fake_session
        assert set(project_ids) == {project_a, project_b}
        return expected

    monkeypatch.setattr(
        "app.services.projects.stats.project_items_repo.count_stats_by_project_sql",
        _by_project_sql,
    )

    stats = await stats_service.count_stats_by_project(fake_session, [project_a, project_b])
    assert stats[project_a]["total"] == 1
    assert stats[project_a]["new_count"] == 1
    assert stats[project_b]["total"] == 2
    assert stats[project_b]["mastered_count"] == 1


@pytest.mark.asyncio
async def test_count_stats_by_project_includes_projects_with_no_items(monkeypatch):
    project_id = uuid4()
    expected = {project_id: {"total": 0}}
    fake_session = AsyncMock()

    async def _by_project_sql(session, project_ids, *, timezone_by_project=None):
        return expected

    monkeypatch.setattr(
        "app.services.projects.stats.project_items_repo.count_stats_by_project_sql",
        _by_project_sql,
    )

    stats = await stats_service.count_stats_by_project(fake_session, [project_id])
    assert stats[project_id]["total"] == 0


def test_stats_from_items_aggregates_statuses():
    """stats_from_items (used by other callers) still works correctly."""
    now = datetime.now(UTC)
    items = [
        _item(status="new", created_at=now),
        _item(status="learning", created_at=now - timedelta(days=8)),
        _item(status="mastered", mastered=True, created_at=now),
        _item(status="learning", last_reviewed_at=now - timedelta(hours=30)),
    ]
    stats = stats_service.stats_from_items(items)
    assert stats["total"] == 4
    assert stats["new_count"] == 1
    assert stats["learning_count"] == 2
    assert stats["mastered_count"] == 1
    assert stats["added_this_week"] == 3
    assert stats["due_for_review"] >= 2

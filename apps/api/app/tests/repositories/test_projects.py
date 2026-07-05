"""Tests for app.repositories.projects."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def fake_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_projects_list_excludes_archived_by_default(fake_session):
    from app.repositories.projects import list_for_user

    mock_project = MagicMock()
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_project])))
    )

    result = await list_for_user(fake_session, uuid4())

    assert result == [mock_project]


@pytest.mark.asyncio
async def test_list_for_users_returns_empty_without_querying(fake_session):
    from app.repositories.projects import list_for_users

    result = await list_for_users(fake_session, [])

    assert result == []
    fake_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_list_for_users_issues_a_single_batched_query(fake_session):
    from app.repositories.projects import list_for_users

    projects = [MagicMock(), MagicMock()]
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=projects)))
    )

    result = await list_for_users(fake_session, [uuid4(), uuid4(), uuid4()])

    assert result == projects
    fake_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_find_language_by_target(fake_session):
    from app.repositories.projects import find_language_by_target

    project = MagicMock()
    fake_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=project)
    )

    result = await find_language_by_target(fake_session, uuid4(), "EN")

    assert result is project


@pytest.mark.asyncio
async def test_projects_create_normalizes_vocabulary_kind(fake_session):
    from app.repositories.projects import create

    project = await create(
        fake_session,
        user_id=uuid4(),
        title="Spanish",
        kind="vocabulary",
    )

    assert project.kind == "language"
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_projects_delete_by_id_not_found(fake_session):
    from app.repositories.projects import delete_by_id

    fake_session.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))

    deleted = await delete_by_id(fake_session, uuid4(), uuid4())

    assert deleted is False


@pytest.mark.asyncio
async def test_projects_delete_by_id_success(fake_session):
    from app.repositories.projects import delete_by_id

    project = MagicMock()
    fake_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=project)
    )

    deleted = await delete_by_id(fake_session, uuid4(), uuid4())

    assert deleted is True
    fake_session.delete.assert_awaited_once_with(project)

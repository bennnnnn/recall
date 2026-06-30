"""Tests for app.repositories.templates and projects."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def fake_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_templates_list_for_user(fake_session):
    from app.repositories.templates import list_for_user

    mock_tpl = MagicMock()
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_tpl])))
    )

    result = await list_for_user(fake_session, uuid4())

    assert result == [mock_tpl]


@pytest.mark.asyncio
async def test_templates_get_by_id(fake_session):
    from app.repositories.templates import get_by_id

    mock_tpl = MagicMock()
    fake_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=mock_tpl)
    )

    result = await get_by_id(fake_session, uuid4(), user_id=uuid4())

    assert result is mock_tpl


@pytest.mark.asyncio
async def test_templates_create(fake_session):
    from app.repositories.templates import create

    tpl = await create(
        fake_session,
        user_id=uuid4(),
        title="Daily standup",
        content="Summarize blockers",
    )

    fake_session.add.assert_called_once()
    fake_session.commit.assert_awaited_once()
    assert tpl.title == "Daily standup"


@pytest.mark.asyncio
async def test_templates_update_skips_none_fields(fake_session):
    from app.repositories.templates import update

    tpl = MagicMock(title="Old")
    updated = await update(fake_session, tpl, title=None, content="New body")

    assert updated.content == "New body"
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_templates_delete_by_id(fake_session):
    from app.repositories.templates import delete_by_id

    fake_session.execute.return_value = MagicMock(rowcount=1)

    deleted = await delete_by_id(fake_session, uuid4(), uuid4())

    assert deleted is True


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

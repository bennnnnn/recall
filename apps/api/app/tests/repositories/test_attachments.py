"""Tests for app.repositories.attachments."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def fake_session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_create_pending_attachment(fake_session):
    from app.repositories.attachments import create_pending

    attachment_id = uuid4()
    row = await create_pending(
        fake_session,
        attachment_id=attachment_id,
        user_id=uuid4(),
        storage_key="uploads/a",
        content_type="image/png",
        size_bytes=128,
    )

    fake_session.add.assert_called_once()
    fake_session.commit.assert_awaited_once()
    assert row.id == attachment_id


@pytest.mark.asyncio
async def test_get_by_id_returns_attachment(fake_session):
    from app.repositories.attachments import get_by_id

    mock_row = MagicMock()
    fake_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=mock_row)
    )

    result = await get_by_id(fake_session, uuid4(), uuid4())

    assert result is mock_row


@pytest.mark.asyncio
async def test_get_by_ids_returns_empty_list_without_querying(fake_session):
    from app.repositories.attachments import get_by_ids

    result = await get_by_ids(fake_session, [], uuid4())

    assert result == []
    fake_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_by_ids_issues_a_single_batched_query(fake_session):
    from app.repositories.attachments import get_by_ids

    rows = [MagicMock(), MagicMock()]
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows)))
    )

    ids = [uuid4(), uuid4(), uuid4()]
    result = await get_by_ids(fake_session, ids, uuid4())

    assert result == rows
    fake_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_link_message_sets_message_id(fake_session):
    from app.repositories.attachments import link_message

    row = MagicMock()
    message_id = uuid4()

    linked = await link_message(fake_session, row, message_id)

    assert linked.message_id == message_id
    fake_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_for_gallery_images_returns_rows_and_has_more(fake_session):
    from app.repositories.attachments import list_for_gallery

    rows = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows)))
    )

    result, has_more = await list_for_gallery(
        fake_session, uuid4(), category="images", source="generated", limit=3, offset=0
    )

    assert result == rows[:3]
    assert has_more is True
    fake_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_for_gallery_exact_page_is_not_has_more(fake_session):
    """A full page with no extra row means there is nothing left to fetch."""
    from app.repositories.attachments import list_for_gallery

    rows = [MagicMock(), MagicMock(), MagicMock()]
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows)))
    )

    result, has_more = await list_for_gallery(
        fake_session, uuid4(), category="images", limit=3, offset=0
    )

    assert result == rows
    assert has_more is False


@pytest.mark.asyncio
async def test_list_for_gallery_files_category(fake_session):
    """category='files' excludes image content types."""
    from app.repositories.attachments import list_for_gallery

    rows = [MagicMock()]
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows)))
    )

    result, has_more = await list_for_gallery(
        fake_session, uuid4(), category="files", limit=30, offset=0
    )

    assert result == rows
    assert has_more is False
    fake_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_for_gallery_all_no_filters(fake_session):
    """When category and source are None, no content/source filters are applied."""
    from app.repositories.attachments import list_for_gallery

    rows = [MagicMock()]
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows)))
    )

    result, has_more = await list_for_gallery(
        fake_session, uuid4(), source=None, limit=30, offset=0
    )

    assert result == rows
    assert has_more is False


@pytest.mark.asyncio
async def test_list_for_gallery_excludes_unverified(fake_session):
    """The gallery query must filter out unverified attachments (verified_at
    IS NULL) — pending/failed rows produce broken download URLs."""
    from sqlalchemy.dialects import postgresql

    from app.repositories.attachments import list_for_gallery

    rows = [MagicMock()]
    captured: dict = {}
    fake_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows))),
        scalars_=MagicMock(),
    )

    async def _capture(stmt):
        captured["stmt"] = stmt
        return MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows)))
        )

    fake_session.execute = _capture
    await list_for_gallery(fake_session, uuid4(), limit=30, offset=0)

    compiled = captured["stmt"].compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "verified_at" in sql
    assert "IS NOT NULL" in sql.upper() or "is not" in sql.lower()


@pytest.mark.asyncio
async def test_list_for_gallery_fetches_one_extra_row_for_has_more(fake_session):
    from sqlalchemy.dialects import postgresql

    from app.repositories.attachments import list_for_gallery

    captured: dict = {}

    async def _capture(stmt):
        captured["stmt"] = stmt
        return MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))

    fake_session.execute = _capture
    await list_for_gallery(fake_session, uuid4(), limit=30, offset=0)

    compiled = captured["stmt"].compile(dialect=postgresql.dialect())
    combined = f"{compiled} {compiled.params}"
    assert "31" in combined

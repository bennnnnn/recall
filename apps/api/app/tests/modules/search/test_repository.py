from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.search import repository as search_repo


def _title_row(*, chat_id, title: str, created_at: datetime):
    row = MagicMock()
    row.match_type = "title"
    row.message_id = None
    row.chat_id = chat_id
    row.chat_title = title
    row.content = title
    row.role = "chat"
    row.created_at = created_at
    return row


def _message_row(*, message_id, chat_id, title: str, content: str, created_at: datetime):
    row = MagicMock()
    row.match_type = "message"
    row.message_id = message_id
    row.chat_id = chat_id
    row.chat_title = title
    row.content = content
    row.role = "user"
    row.created_at = created_at
    return row


@pytest.mark.asyncio
async def test_search_includes_title_only_match():
    user_id = uuid4()
    chat_id = uuid4()
    session = AsyncMock()
    page_result = MagicMock()
    page_result.all.return_value = [
        _title_row(chat_id=chat_id, title="Trip planning", created_at=datetime.now(UTC))
    ]
    session.execute = AsyncMock(return_value=page_result)

    results, has_more = await search_repo.search_conversations(session, user_id, "trip")

    assert has_more is False
    assert len(results) == 1
    assert results[0]["match_type"] == "title"
    assert results[0]["chat_id"] == chat_id
    assert results[0]["message_id"] is None


@pytest.mark.asyncio
async def test_search_pages_the_merged_union_once():
    """Offset/limit apply to the union, not to title and message streams separately,
    and nothing counts every hit."""
    session = AsyncMock()
    page_result = MagicMock()
    page_result.all.return_value = []
    session.execute = AsyncMock(return_value=page_result)

    results, has_more = await search_repo.search_conversations(
        session, uuid4(), "trip", limit=20, offset=60
    )

    assert results == []
    assert has_more is False
    session.execute.assert_awaited_once()
    sql = str(session.execute.await_args.args[0]).lower()
    assert "union all" in sql
    assert sql.count("limit") == 1
    assert sql.count("offset") == 1
    assert "count(" not in sql


@pytest.mark.asyncio
async def test_search_reads_one_row_past_the_page_for_has_more():
    now = datetime.now(UTC)
    page = MagicMock()
    page.all.return_value = [
        _message_row(
            message_id=uuid4(), chat_id=uuid4(), title="Trip", content="trip notes", created_at=now
        ),
        _title_row(chat_id=uuid4(), title="Trip planning", created_at=now),
    ]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=page)

    results, has_more = await search_repo.search_conversations(
        session, uuid4(), "trip", limit=1, offset=0
    )

    assert has_more is True
    assert [row["match_type"] for row in results] == ["message"]

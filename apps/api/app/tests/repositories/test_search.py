from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.repositories import search as search_repo


def _title_row(*, chat_id, title: str, created_at: datetime, total: int):
    row = MagicMock()
    row.match_type = "title"
    row.message_id = None
    row.chat_id = chat_id
    row.chat_title = title
    row.content = title
    row.role = "chat"
    row.created_at = created_at
    row.total = total
    return row


def _message_row(
    *, message_id, chat_id, title: str, content: str, created_at: datetime, total: int
):
    row = MagicMock()
    row.match_type = "message"
    row.message_id = message_id
    row.chat_id = chat_id
    row.chat_title = title
    row.content = content
    row.role = "user"
    row.created_at = created_at
    row.total = total
    return row


@pytest.mark.asyncio
async def test_search_includes_title_only_match():
    user_id = uuid4()
    chat_id = uuid4()
    session = AsyncMock()
    page_result = MagicMock()
    page_result.all.return_value = [
        _title_row(chat_id=chat_id, title="Trip planning", created_at=datetime.now(UTC), total=1)
    ]
    session.execute = AsyncMock(return_value=page_result)

    results, total = await search_repo.search_conversations(session, user_id, "trip")

    assert total == 1
    assert len(results) == 1
    assert results[0]["match_type"] == "title"
    assert results[0]["chat_id"] == chat_id
    assert results[0]["message_id"] is None


@pytest.mark.asyncio
async def test_search_pages_the_merged_union_once():
    """Offset/limit apply to the union, not to title and message streams separately."""
    session = AsyncMock()
    page_result = MagicMock()
    page_result.all.return_value = [MagicMock(match_type=None, total=50)]
    session.execute = AsyncMock(return_value=page_result)

    results, total = await search_repo.search_conversations(
        session, uuid4(), "trip", limit=20, offset=60
    )

    assert results == []
    assert total == 50
    session.execute.assert_awaited_once()
    sql = str(session.execute.await_args.args[0]).lower()
    assert "union all" in sql
    assert sql.count("limit") == 1
    assert sql.count("offset") == 1


@pytest.mark.asyncio
async def test_search_total_counts_union_across_pages():
    user_id = uuid4()
    now = datetime.now(UTC)
    page1 = MagicMock()
    page1.all.return_value = [
        _message_row(
            message_id=uuid4(),
            chat_id=uuid4(),
            title="Trip",
            content="trip notes",
            created_at=now,
            total=3,
        )
    ]
    page2 = MagicMock()
    page2.all.return_value = [
        _title_row(chat_id=uuid4(), title="Trip planning", created_at=now, total=3),
    ]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[page1, page2])

    _page_one, total_one = await search_repo.search_conversations(
        session, user_id, "trip", limit=1, offset=0
    )
    _page_two, total_two = await search_repo.search_conversations(
        session, user_id, "trip", limit=1, offset=1
    )

    assert total_one == total_two == 3

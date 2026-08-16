from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.repositories import search as search_repo


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


class SessionCM:
    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *_args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_search_includes_title_only_match():
    user_id = uuid4()
    chat_id = uuid4()
    session = AsyncMock()
    created = datetime.now(UTC)

    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    page_result = MagicMock()
    page_result.all.return_value = [
        _title_row(chat_id=chat_id, title="Trip planning", created_at=created)
    ]

    count_session = AsyncMock()
    count_session.execute = AsyncMock(return_value=count_result)
    session.execute = AsyncMock(return_value=page_result)

    with patch("app.repositories.search.SessionLocal", return_value=SessionCM(count_session)):
        results, total = await search_repo.search_conversations(session, user_id, "trip")

    assert total == 1
    assert len(results) == 1
    assert results[0]["match_type"] == "title"
    assert results[0]["chat_id"] == chat_id
    assert results[0]["message_id"] is None


@pytest.mark.asyncio
async def test_search_pages_the_merged_union_once():
    """Offset/limit apply to the union, not to title and message streams separately."""
    user_id = uuid4()
    session = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 50
    page_result = MagicMock()
    page_result.all.return_value = []

    count_session = AsyncMock()
    count_session.execute = AsyncMock(return_value=count_result)
    session.execute = AsyncMock(return_value=page_result)

    with patch("app.repositories.search.SessionLocal", return_value=SessionCM(count_session)):
        _, total = await search_repo.search_conversations(
            session, user_id, "trip", limit=20, offset=40
        )

    assert total == 50
    page_stmt = session.execute.await_args.args[0]
    count_sql = str(count_session.execute.await_args.args[0]).lower()
    page_sql = str(page_stmt).lower()
    assert "union" in count_sql
    assert "union" in page_sql
    assert page_stmt._offset_clause is not None
    assert page_stmt._limit_clause is not None
    assert str(page_stmt._limit_clause) == "20" or page_stmt._limit == 20


@pytest.mark.asyncio
async def test_search_total_is_stable_across_pages():
    user_id = uuid4()
    now = datetime.now(UTC)
    chat_id = uuid4()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 3

    page1 = MagicMock()
    page1.all.return_value = [
        _message_row(
            message_id=uuid4(),
            chat_id=chat_id,
            title="Trip",
            content="trip notes",
            created_at=now,
        )
    ]
    page2 = MagicMock()
    page2.all.return_value = [
        _title_row(chat_id=uuid4(), title="Trip planning", created_at=now),
    ]

    count_session = AsyncMock()
    count_session.execute = AsyncMock(return_value=count_result)
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[page1, page2])

    with patch("app.repositories.search.SessionLocal", return_value=SessionCM(count_session)):
        _page_one, total_one = await search_repo.search_conversations(
            session, user_id, "trip", limit=1, offset=0
        )
        _page_two, total_two = await search_repo.search_conversations(
            session, user_id, "trip", limit=1, offset=1
        )

    assert total_one == total_two == 3

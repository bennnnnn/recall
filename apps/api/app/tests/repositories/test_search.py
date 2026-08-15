from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.repositories import search as search_repo


@pytest.mark.asyncio
async def test_search_includes_title_only_match():
    user_id = uuid4()
    chat_id = uuid4()
    session = AsyncMock()

    title_chat = MagicMock()
    title_chat.id = chat_id
    title_chat.title = "Trip planning"
    title_chat.updated_at = datetime.now(UTC)
    title_chat.created_at = datetime.now(UTC)

    msg_count_result = MagicMock()
    msg_count_result.scalar_one.return_value = 0

    title_result = MagicMock()
    title_result.scalars.return_value.all.return_value = [title_chat]

    msg_chat_ids_result = MagicMock()
    msg_chat_ids_result.all.return_value = []

    msg_rows_result = MagicMock()
    msg_rows_result.all.return_value = []

    # search_conversations parallelizes the count/title/chat-ids queries on their
    # own short-lived sessions (asyncio.gather); only the main msg_stmt uses the
    # session passed in by the caller.
    parallel_session = AsyncMock()
    parallel_session.execute = AsyncMock(side_effect=[msg_count_result, title_result])
    parallel_session.scalars = AsyncMock(return_value=msg_chat_ids_result)

    class SessionCM:
        async def __aenter__(self):
            return parallel_session

        async def __aexit__(self, *_args: object) -> None:
            return None

    session.execute = AsyncMock(return_value=msg_rows_result)

    with patch("app.repositories.search.SessionLocal", return_value=SessionCM()):
        results, total = await search_repo.search_conversations(session, user_id, "trip")

    assert total == 1
    assert len(results) == 1
    assert results[0]["match_type"] == "title"
    assert results[0]["chat_id"] == chat_id
    assert results[0]["message_id"] is None


@pytest.mark.asyncio
async def test_search_pages_both_branches_in_sql():
    """Offset is applied in SQL on message and title queries, not by
    materializing limit+offset message rows then slicing in Python."""
    user_id = uuid4()
    session = AsyncMock()
    msg_count_result = MagicMock()
    msg_count_result.scalar_one.return_value = 0
    title_result = MagicMock()
    title_result.scalars.return_value.all.return_value = []
    msg_chat_ids_result = MagicMock()
    msg_chat_ids_result.all.return_value = []
    msg_rows_result = MagicMock()
    msg_rows_result.all.return_value = []

    captured: list[object] = []

    async def capture_execute(stmt: object) -> MagicMock:
        captured.append(stmt)
        if len(captured) == 1:
            return msg_count_result
        return title_result

    parallel_session = AsyncMock()
    parallel_session.execute = capture_execute
    parallel_session.scalars = AsyncMock(return_value=msg_chat_ids_result)

    class SessionCM:
        async def __aenter__(self):
            return parallel_session

        async def __aexit__(self, *_args: object) -> None:
            return None

    session.execute = AsyncMock(return_value=msg_rows_result)

    with patch("app.repositories.search.SessionLocal", return_value=SessionCM()):
        await search_repo.search_conversations(session, user_id, "trip", limit=20, offset=40)

    title_stmt = captured[1]
    msg_stmt = session.execute.await_args.args[0]
    count_sql = str(captured[0]).lower()
    assert "join" not in count_sql
    assert getattr(title_stmt, "_offset", None) == 40 or title_stmt._offset_clause is not None
    assert msg_stmt._offset_clause is not None
    assert str(title_stmt._limit_clause) == "30" or title_stmt._limit == 30
    assert str(msg_stmt._limit_clause) == "30" or msg_stmt._limit == 30

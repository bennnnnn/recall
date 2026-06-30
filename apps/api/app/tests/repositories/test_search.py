from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
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

    session.execute = AsyncMock(
        side_effect=[msg_count_result, title_result, msg_chat_ids_result, msg_rows_result]
    )
    session.scalars = AsyncMock(return_value=msg_chat_ids_result)

    results, total = await search_repo.search_conversations(session, user_id, "trip")

    assert total == 1
    assert len(results) == 1
    assert results[0]["match_type"] == "title"
    assert results[0]["chat_id"] == chat_id
    assert results[0]["message_id"] is None

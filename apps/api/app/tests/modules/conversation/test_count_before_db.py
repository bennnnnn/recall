"""A row's offset in its chat, counted in the order ``messages_before`` reads (real Postgres).

The prompt's history finds the summary's edge from the oldest loaded row's offset when the
turn passed no count (``prompt_context.load_anchored_history``). Rows written in the same
instant are ordered by id, as the reads order them.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.core.db import SessionLocal, engine
from app.models.orm import Message, User
from app.modules.account import lifecycle as account_lifecycle
from app.modules.conversation import chats_repository, history


@pytest.fixture
async def chat_rows() -> AsyncIterator[tuple[UUID, list[Message]]]:
    """A committed chat of six messages, two pairs sharing a time: (chat id, rows in order)."""
    await engine.dispose(close=False)
    async with SessionLocal() as session:
        user = User(email=f"{uuid4()}@example.com", name="Offsets", google_sub=str(uuid4()))
        session.add(user)
        await session.flush()
        chat = await chats_repository.create(session, user_id=user.id, model="free-chat")
        times = [datetime(2026, 1, 1, hour, tzinfo=UTC) for hour in (1, 2, 2, 3, 3, 4)]
        rows = [
            Message(chat_id=chat.id, user_id=user.id, role="user", content=f"m{i}", created_at=at)
            for i, at in enumerate(times)
        ]
        session.add_all(rows)
        await session.commit()
        user_id, chat_id = user.id, chat.id
    try:
        async with SessionLocal() as session:
            ordered = await history.recent_messages(session, chat_id, limit=10)
        yield chat_id, ordered
    finally:
        async with SessionLocal() as session:
            await account_lifecycle.erase_user_rows(session, user_id)
        await engine.dispose(close=False)


@pytest.mark.asyncio
async def test_a_rows_offset_counts_the_rows_read_before_it(chat_rows):
    chat_id, ordered = chat_rows
    async with SessionLocal() as session:
        for offset, row in enumerate(ordered):
            assert await history.count_before(session, chat_id, row) == offset
            before = await history.messages_before(session, chat_id, row, limit=10)
            assert [m.id for m in before] == [m.id for m in ordered[:offset]]

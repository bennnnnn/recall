"""Tests for live-talk chat persistence helpers."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.live_talk import message_out_payload, persist_live_talk_turn


def test_message_out_payload_none():
    assert message_out_payload(None) is None


@pytest.mark.asyncio
async def test_persist_live_talk_turn_writes_both_roles_and_enqueues_topic():
    user = MagicMock()
    user.id = uuid4()
    user.memory_enabled = False
    chat_id = uuid4()
    chat = MagicMock()
    user_row = MagicMock()
    user_row.id = uuid4()
    asst_row = MagicMock()
    asst_row.id = uuid4()

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.live_talk.SessionLocal", return_value=session),
        patch("app.services.live_talk.chats_repo.get_by_id", AsyncMock(return_value=chat)),
        patch(
            "app.services.live_talk.messages_repo.create",
            AsyncMock(side_effect=[user_row, asst_row]),
        ) as create,
        patch("app.services.live_talk.jobs.enqueue", AsyncMock()) as enqueue,
    ):
        result = await persist_live_talk_turn(
            user=user,
            chat_id=chat_id,
            user_text="Hello",
            assistant_text="Hi there",
            untitled=True,
            settings=MagicMock(chat_history_rag_enabled=False),
            redis=AsyncMock(),
        )

    assert result == (user_row, asst_row)
    assert create.await_count == 2
    session.commit.assert_awaited()
    topic_calls = [call.args[1] for call in enqueue.await_args_list]
    assert "topic" in topic_calls

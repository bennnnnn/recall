"""Tests for live-talk chat persistence helpers."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.live_talk import persist_live_talk_turn


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


@pytest.mark.asyncio
async def test_persist_live_talk_turn_titles_when_assistant_transcript_missing():
    user = MagicMock()
    user.id = uuid4()
    user.memory_enabled = False
    chat_id = uuid4()
    chat = MagicMock()
    user_row = MagicMock()
    user_row.id = uuid4()

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.services.live_talk.SessionLocal", return_value=session),
        patch("app.services.live_talk.chats_repo.get_by_id", AsyncMock(return_value=chat)),
        patch(
            "app.services.live_talk.messages_repo.create",
            AsyncMock(return_value=user_row),
        ),
        patch("app.services.live_talk.jobs.enqueue", AsyncMock()) as enqueue,
    ):
        await persist_live_talk_turn(
            user=user,
            chat_id=chat_id,
            user_text="Remind me to pack",
            assistant_text="",
            untitled=True,
            settings=MagicMock(chat_history_rag_enabled=False),
            redis=AsyncMock(),
        )

    topic = next(call for call in enqueue.await_args_list if call.args[1] == "topic")
    assert topic.args[2]["user_message"] == "Remind me to pack"
    assert topic.args[2]["assistant_message"] == "Remind me to pack"


@pytest.mark.asyncio
async def test_persist_live_talk_turn_skips_user_row_on_follow_up():
    user = MagicMock()
    user.id = uuid4()
    user.memory_enabled = False
    chat_id = uuid4()
    chat = MagicMock()
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
            AsyncMock(return_value=asst_row),
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
            write_user=False,
        )

    assert result == (None, asst_row)
    assert create.await_count == 1
    assert create.await_args.kwargs["role"] == "assistant"
    assert any(call.args[1] == "topic" for call in enqueue.await_args_list)

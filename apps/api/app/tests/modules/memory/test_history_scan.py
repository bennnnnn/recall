from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import Chat, Message
from app.modules.memory import history_scan
from app.repositories import users as users_repo


def _user(**kwargs):
    defaults = {"id": uuid4(), "memory_enabled": True, "memory_history_scanned_at": None}
    return SimpleNamespace(**{**defaults, **kwargs})


@pytest.mark.asyncio
async def test_request_history_scan_queues_once(fake_redis):
    user = _user()
    enqueue = AsyncMock()
    with patch("app.modules.memory.history_scan.jobs.enqueue", enqueue):
        first = await history_scan.request_history_scan(fake_redis, user)
        second = await history_scan.request_history_scan(fake_redis, user)

    assert (first, second) == (True, True)
    enqueue.assert_awaited_once()
    assert enqueue.await_args.args[1:] == ("memory_history_scan", {"user_id": str(user.id)})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user",
    [
        _user(memory_enabled=False),
        _user(memory_history_scanned_at=datetime(2026, 9, 1, tzinfo=UTC)),
    ],
)
async def test_request_history_scan_skips_when_off_or_done(fake_redis, user):
    enqueue = AsyncMock()
    with patch("app.modules.memory.history_scan.jobs.enqueue", enqueue):
        assert await history_scan.request_history_scan(fake_redis, user) is False
    enqueue.assert_not_awaited()


async def _make_user(session):
    return await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )


class _Reuse:
    """Hand the test's session to code that opens its own sessions."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return None


@pytest.mark.asyncio
async def test_scan_reads_recent_chats_once_and_skips_quizzes(db_session):
    user = await _make_user(db_session)
    talk = Chat(user_id=user.id, title="Recall app")
    quiz = Chat(user_id=user.id, title="Spanish quiz", quiz_mode="exam")
    empty = Chat(user_id=user.id, title="Nothing yet")
    db_session.add_all([talk, quiz, empty])
    await db_session.flush()
    db_session.add_all(
        [
            Message(
                chat_id=talk.id,
                user_id=user.id,
                role="user",
                content="I'm building Recall with Expo",
            ),
            Message(chat_id=talk.id, user_id=user.id, role="assistant", content="Nice!"),
            Message(chat_id=quiz.id, user_id=user.id, role="user", content="hola"),
        ]
    )
    await db_session.flush()

    extract = AsyncMock(return_value=None)
    with (
        patch("app.modules.memory.history_scan.SessionLocal", lambda: _Reuse(db_session)),
        patch("app.modules.memory.history_scan.extract_and_store_memories", extract),
    ):
        await history_scan.scan_recent_chats(Settings(), user_id=user.id)
        await history_scan.scan_recent_chats(Settings(), user_id=user.id)

    extract.assert_awaited_once()
    kwargs = extract.await_args.kwargs
    assert kwargs["chat_id"] == talk.id
    assert kwargs["from_history"] is True
    assert kwargs["transcript"] == "User: I'm building Recall with Expo"
    await db_session.refresh(user)
    assert user.memory_history_scanned_at is not None


@pytest.mark.asyncio
async def test_scan_keeps_going_after_a_chat_fails(db_session):
    user = await _make_user(db_session)
    chats = [Chat(user_id=user.id, title=f"Chat {index}") for index in range(2)]
    db_session.add_all(chats)
    await db_session.flush()
    db_session.add_all(
        [
            Message(chat_id=chat.id, user_id=user.id, role="user", content="I run every morning")
            for chat in chats
        ]
    )
    await db_session.flush()

    extract = AsyncMock(side_effect=[RuntimeError("provider down"), None])
    with (
        patch("app.modules.memory.history_scan.SessionLocal", lambda: _Reuse(db_session)),
        patch("app.modules.memory.history_scan.extract_and_store_memories", extract),
    ):
        await history_scan.scan_recent_chats(Settings(), user_id=user.id)

    assert extract.await_count == 2
    await db_session.refresh(user)
    assert user.memory_history_scanned_at is not None

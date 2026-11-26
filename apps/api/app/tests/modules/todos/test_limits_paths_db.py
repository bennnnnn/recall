"""The open to-do cap through the real writers (review round 2 of #2597): live talk's
add and reopen, a chat card's tap, a duplicate at the cap, and adds sent at once."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.db import engine
from app.models.orm import TodoItem, User
from app.modules.conversation import chats_repository as chats_repo
from app.modules.speech.live_talk import persist_live_talk_turn
from app.modules.todos import proposals
from app.modules.todos import repository as todos_repo
from app.modules.todos.actions import apply_todo_actions
from app.modules.todos.limits import OPEN_TODOS_MAX, TODO_LIST_FULL_REPLY, TodoLimitError
from app.modules.todos.reminder_fences import materialize_reminder_fences
from app.modules.todos.schemas import TodoActionItem
from app.repositories import users as users_repo
from app.tests.fakes import FakeSessionCM, redis_mock

DUE = (datetime.now(UTC) + timedelta(days=30)).replace(hour=17, minute=0, second=0, microsecond=0)


async def _full_list(session: Any, *, room: int = 0) -> Any:
    """A user with "Call mom" at DUE open and the rest of the cap filled, ``room`` short."""
    user = await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Full",
        avatar_url=None,
        google_sub=str(uuid4()),
    )
    user.timezone = "UTC"
    await session.execute(
        insert(TodoItem),
        [
            {"id": uuid4(), "user_id": user.id, "content": f"Errand {n}", "topic": "Aaa errands"}
            for n in range(OPEN_TODOS_MAX - 1 - room)
        ],
    )
    session.add(TodoItem(user_id=user.id, content="Call mom", topic="Reminders", due_at=DUE))
    session.add(TodoItem(user_id=user.id, content="Gym", topic="General", checked=True))
    await session.flush()
    return user


def _reply(title: str, due: datetime) -> str:
    return f'Sure, I\'ll remind you.\n\n```reminder\n{{"title": "{title}", "due_at": "{due.isoformat()}"}}\n```'


async def _open(session: Any, user_id: Any) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(TodoItem)
        .where(TodoItem.user_id == user_id, TodoItem.checked.is_(False))
    )
    return int(count or 0)


@pytest.mark.asyncio
async def test_a_spoken_add_at_the_cap_says_the_list_is_full_and_saves_nothing(db_session):
    user = await _full_list(db_session)
    chat = await chats_repo.create(db_session, user_id=user.id, model="free-chat")
    user_id = user.id
    with patch("app.modules.speech.live_talk.SessionLocal", FakeSessionCM(db_session)):
        _, assistant = await persist_live_talk_turn(
            user=user,
            chat_id=chat.id,
            user_text="remind me to water the plants at 6pm",
            assistant_text=_reply("Water the plants", DUE + timedelta(hours=1)),
            untitled=False,
            settings=Settings(_env_file=None),
            redis=redis_mock(),
            enqueue_jobs=False,
        )
    assert assistant is not None and assistant.content == TODO_LIST_FULL_REPLY
    assert await _open(db_session, user_id) == OPEN_TODOS_MAX


@pytest.mark.asyncio
async def test_a_duplicate_at_the_cap_is_the_duplicate_it_always_was(db_session):
    """An add of a reminder already open adds nothing: it meets the open-row unique, which
    its callers skip or answer with the row that is there, never the cap."""
    user = await _full_list(db_session)
    with pytest.raises(IntegrityError) as duplicate:
        async with db_session.begin_nested():
            await todos_repo.create(
                db_session, user_id=user.id, content="call mom", due_at=DUE, commit=False
            )
    assert todos_repo.is_open_content_due_conflict(duplicate.value)
    with pytest.raises(TodoLimitError):
        async with db_session.begin_nested():
            await todos_repo.create(
                db_session, user_id=user.id, content="Call dad", due_at=DUE, commit=False
            )


@pytest.mark.asyncio
async def test_reopening_a_done_to_do_at_the_cap_reaches_the_caller(db_session):
    """A spoken reopen's action path lets the cap through: no failed-action error log."""
    user = await _full_list(db_session)
    with (
        # The whole list is read, so the done "Gym" is found past the first 500.
        patch("app.modules.todos.actions.ACTION_RELOAD_LIMIT", 2 * OPEN_TODOS_MAX),
        patch("app.modules.todos.actions.logger.exception") as failed,
        pytest.raises(TodoLimitError),
    ):
        await apply_todo_actions(
            db_session,
            user_id=user.id,
            actions=[TodoActionItem(action="uncheck", topic="General", content="Gym")],
        )
    failed.assert_not_called()


@pytest.mark.asyncio
async def test_a_card_tapped_at_the_cap_is_refused_and_can_be_tapped_later(db_session, fake_redis):
    user = await _full_list(db_session)
    chat = await chats_repo.create(db_session, user_id=user.id, model="free-chat")
    text, written = await materialize_reminder_fences(
        db_session,
        user_id=user.id,
        chat_id=chat.id,
        assistant_text=_reply("Water the plants", DUE + timedelta(hours=1)),
        user_timezone="UTC",
        user_text="remind me to water the plants at 6pm",
        redis=fake_redis,
        confirm=True,
    )
    assert written == 0
    proposal_id = text.split('"proposal_id": "', 1)[1].split('"', 1)[0]
    user_id = user.id
    with pytest.raises(TodoLimitError):
        await proposals.confirm_proposal(
            db_session, fake_redis, user_id=user_id, proposal_id=proposal_id
        )
    assert await _open(db_session, user_id) == OPEN_TODOS_MAX
    # Kept: once there is room, the same card saves.
    assert await fake_redis.keys(f"*{proposal_id}*")


@pytest.mark.asyncio
async def test_adds_sent_at_once_never_pass_the_cap_together() -> None:
    """With one open to-do of room, two adds at once: one saves, the other is refused."""
    async with _own_session() as setup:
        user = await _full_list(setup, room=1)
        user_id = user.id
        await setup.commit()
    first_holds = asyncio.Event()

    async def add(title: str, *, hold: bool) -> str:
        async with _own_session() as session:
            try:
                await todos_repo.create(session, user_id=user_id, content=title, commit=False)
                if hold:
                    first_holds.set()
                    await asyncio.sleep(0.3)  # the second add's count waits on this one
                await session.commit()
                return "saved"
            except TodoLimitError:
                await session.rollback()
                return "refused"

    try:
        first = asyncio.create_task(add("One", hold=True))
        await first_holds.wait()
        second = await add("Two", hold=False)
        assert sorted([await first, second]) == ["refused", "saved"]
    finally:
        async with _own_session() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()
        await engine.dispose(close=False)


def _own_session() -> Any:
    """A session that commits for real: the race needs two connections."""
    from sqlalchemy.ext.asyncio import AsyncSession

    return AsyncSession(engine, expire_on_commit=False)

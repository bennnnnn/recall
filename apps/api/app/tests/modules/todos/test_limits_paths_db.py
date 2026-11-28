"""The open to-do cap through the real writers (review round 2 of #2597): live talk's
add and reopen, a chat card's tap, a duplicate at the cap, and adds sent at once."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError

from app.core.db import engine
from app.models.orm import TodoItem, User
from app.modules.todos import repository as todos_repo
from app.modules.todos.limits import OPEN_TODOS_MAX, TodoLimitError
from app.repositories import users as users_repo

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

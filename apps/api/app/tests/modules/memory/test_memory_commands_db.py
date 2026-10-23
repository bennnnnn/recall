"""What a chat line asks of memory, turn by turn, on the real database.

The memory model is faked: each pass returns the ops a model plausibly writes, and
the rest of the pass (backlog, sensitivity gate, writes) is the real code.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.models.orm import Chat, Memory, Message
from app.modules.memory.extraction_workflow import extract_and_store_memories
from app.modules.memory.schemas import MemoryFactOp, MemoryFactUpdateResult
from app.repositories import users as users_repo

_T0 = datetime(2026, 10, 1, tzinfo=UTC)


class _Reuse:
    """Hand the test's session to code that opens its own sessions."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return None


class _MemoryModel:
    """Returns the ops queued for the next pass."""

    def __init__(self) -> None:
        self.ops: list[MemoryFactOp] = []

    async def __call__(self, _settings, _transcript, **_kwargs):
        ops, self.ops = self.ops, []
        return MemoryFactUpdateResult(ops=ops)


@pytest.fixture
def model(db_session):
    fake = _MemoryModel()
    with (
        patch("app.modules.memory.extraction_workflow.SessionLocal", lambda: _Reuse(db_session)),
        patch("app.modules.memory.extraction_workflow.memory_llm.revise_memory_facts", fake),
    ):
        yield fake


async def _chat(session) -> Chat:
    user = await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )
    chat = Chat(user_id=user.id, title="Dinner")
    session.add(chat)
    await session.flush()
    return chat


async def _turn(session, chat: Chat, minute: int, line: str, reply: str = "Okay.") -> None:
    """One user line and its reply, then the memory pass that follows the turn."""
    for offset, (role, text) in enumerate((("user", line), ("assistant", reply))):
        session.add(
            Message(
                chat_id=chat.id,
                user_id=chat.user_id,
                role=role,
                content=text,
                created_at=_T0 + timedelta(minutes=minute, seconds=offset),
            )
        )
    await session.flush()
    await extract_and_store_memories(
        Settings(), user_id=chat.user_id, chat_id=chat.id, transcript=f"User: {line}"
    )


async def _active(session, chat: Chat) -> list[str]:
    rows = await session.execute(
        select(Memory.text).where(Memory.user_id == chat.user_id, Memory.status == "active")
    )
    return sorted(rows.scalars())


def _add(text: str, *, sensitivity: str = "normal") -> MemoryFactOp:
    return MemoryFactOp(
        op="add",
        topic="preferences",
        type="preference",
        text=text,
        confidence=0.95,
        sensitivity=sensitivity,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("line", "saved"),
    [
        ("Remember, I'm allergic to peanuts.", True),
        ("remember: I'm allergic to peanuts", True),
        ("Remember I've got a peanut allergy", True),
        ("Save to memory that I'm allergic to peanuts", True),
        # Said in passing, a health fact is not stored unless the user opted in.
        ("I'm allergic to peanuts, what should I cook?", False),
    ],
)
async def test_an_asked_for_sensitive_fact_is_saved(db_session, model, line, saved):
    chat = await _chat(db_session)
    model.ops = [_add("User is allergic to peanuts", sensitivity="health")]

    await _turn(db_session, chat, 1, line)

    assert await _active(db_session, chat) == (["User is allergic to peanuts"] if saved else [])

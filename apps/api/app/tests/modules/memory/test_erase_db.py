"""PostgreSQL: deleting, muting and capping facts end to end (M1, M8, M11, M13)."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.orm import Chat, Memory, Message, MessageChunk
from app.modules.memory import repository as memories_repo
from app.modules.memory.writes_repository import MemoryFactWrite, apply_fact_ops
from app.repositories import users as users_repo

_LISBON = [1.0] + [0.0] * 1535
_NAIROBI = [0.0, 1.0] + [0.0] * 1534
_OTHER = [0.0, 0.0, 1.0] + [0.0] * 1533


async def _user(session):
    return await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )


async def _chunk(session, user_id, text: str, vector: list[float], *, role: str = "user"):
    chat = Chat(user_id=user_id, title="t")
    session.add(chat)
    await session.flush()
    message = Message(chat_id=chat.id, user_id=user_id, role=role, content=text)
    session.add(message)
    await session.flush()
    chunk = MessageChunk(
        user_id=user_id,
        message_id=message.id,
        chat_id=chat.id,
        role=role,
        chunk_index=0,
        text=f"User: {text}",
        embedding=vector,
    )
    session.add(chunk)
    await session.flush()
    return chunk


async def _chunk_texts(session, user_id) -> list[str]:
    rows = await session.execute(select(MessageChunk.text).where(MessageChunk.user_id == user_id))
    return sorted(row[0] for row in rows)


async def _facts(session, user_id) -> list[tuple[str, str]]:
    rows = await session.execute(select(Memory).where(Memory.user_id == user_id))
    return sorted((memory.text, memory.status) for memory in rows.scalars())


def _write(op: str, text: str = "", *, match: str | None = None, importance: float = 0.5):
    return MemoryFactWrite(
        op=op, type="profile", text=text, confidence=0.9, match_text=match, importance=importance
    )


@pytest.mark.asyncio
async def test_deleting_a_fact_deletes_its_history_and_the_snippets_repeating_it(db_session):
    """M13: "I live in Nairobi" → "moved to Lisbon" → delete Lisbon → no Nairobi anywhere."""
    user = await _user(db_session)
    await apply_fact_ops(
        db_session, user.id, [_write("add", "User lives in Nairobi")], None, active_cap=150
    )
    await apply_fact_ops(
        db_session,
        user.id,
        [_write("supersede", "User lives in Lisbon", match="User lives in Nairobi")],
        None,
        active_cap=150,
    )
    lisbon = (
        await db_session.execute(
            select(Memory).where(Memory.user_id == user.id, Memory.status == "active")
        )
    ).scalar_one()
    lisbon.embedding = _LISBON
    await _chunk(db_session, user.id, "I just moved to Lisbon, love it", _LISBON)
    await _chunk(db_session, user.id, "I live in Nairobi near Westlands", _NAIROBI)
    await _chunk(db_session, user.id, "what's a good pasta recipe", _OTHER)
    await db_session.flush()

    assert await memories_repo.delete_by_id(db_session, user.id, lisbon.id, commit=False)

    assert await _facts(db_session, user.id) == []
    # The Lisbon line by its vector; the Nairobi line by name from the old version.
    assert await _chunk_texts(db_session, user.id) == ["User: what's a good pasta recipe"]


@pytest.mark.asyncio
async def test_clearing_all_memory_empties_past_chat_recall(db_session):
    user = await _user(db_session)
    await apply_fact_ops(
        db_session, user.id, [_write("add", "User lives in Nairobi")], None, active_cap=150
    )
    await _chunk(db_session, user.id, "what's a good pasta recipe", _OTHER)
    assert await _facts(db_session, user.id) != []
    assert await _chunk_texts(db_session, user.id) != []

    await memories_repo.delete_all_for_user(db_session, user.id, commit=False)

    assert await _facts(db_session, user.id) == []
    assert await _chunk_texts(db_session, user.id) == []


@pytest.mark.asyncio
async def test_a_mute_keeps_the_fact_but_stops_its_recall(db_session):
    """M11: muted, not deleted; past-chat snippets naming it are dropped."""
    user = await _user(db_session)
    await apply_fact_ops(
        db_session, user.id, [_write("add", "User works at Uber")], None, active_cap=150
    )
    await _chunk(db_session, user.id, "my Uber shift ran late again", _OTHER)
    await _chunk(db_session, user.id, "what's a good pasta recipe", _NAIROBI)

    applied: list[str] = []
    await apply_fact_ops(
        db_session,
        user.id,
        [_write("mute", match="User works at Uber")],
        None,
        active_cap=150,
        applied=applied,
        purge_history=True,
    )

    assert applied == ["mute"]
    assert await _facts(db_session, user.id) == [("User works at Uber", "muted")]
    assert await _chunk_texts(db_session, user.id) == ["User: what's a good pasta recipe"]
    # Not injected: only active facts are eligible for a prompt.
    active = await memories_repo.list_for_user(db_session, user.id, include_muted=False)
    assert active == []


@pytest.mark.parametrize("op", ["delete", "mute"])
@pytest.mark.parametrize(("purge_history", "left"), [(False, 2), (True, 1)])
@pytest.mark.asyncio
async def test_a_removal_purges_chat_snippets_only_when_the_user_asked(
    db_session, op, purge_history, left
):
    """The memory model's own delete or mute keeps chat history; the user's purges it."""
    user = await _user(db_session)
    text = "User is solving x^2 - 5x + 6 = 0"
    await apply_fact_ops(db_session, user.id, [_write("add", text)], None, active_cap=150)
    fact = (await db_session.execute(select(Memory).where(Memory.user_id == user.id))).scalar_one()
    fact.embedding = _LISBON
    await _chunk(db_session, user.id, "factor x^2 - 7x + 12 for me", _LISBON)
    await _chunk(db_session, user.id, "what's a good pasta recipe", _OTHER)
    await db_session.flush()

    await apply_fact_ops(
        db_session,
        user.id,
        [_write(op, match=text)],
        None,
        active_cap=150,
        purge_history=purge_history,
    )

    assert len(await _chunk_texts(db_session, user.id)) == left


@pytest.mark.asyncio
async def test_a_stale_fact_dropped_in_a_users_pass_keeps_chat_snippets(db_session):
    """A pass the user edited also drops stale facts in passing; those keep chat history."""
    user = await _user(db_session)
    text = "User is solving x^2 - 5x + 6 = 0"
    await apply_fact_ops(db_session, user.id, [_write("add", text)], None, active_cap=150)
    fact = (await db_session.execute(select(Memory).where(Memory.user_id == user.id))).scalar_one()
    fact.embedding = _LISBON
    await _chunk(db_session, user.id, "factor x^2 - 7x + 12 for me", _LISBON)
    await db_session.flush()

    stale = MemoryFactWrite(
        op="delete", type="fact", text="", confidence=1.0, match_text=text, stale=True
    )
    await apply_fact_ops(db_session, user.id, [stale], None, active_cap=150, purge_history=True)

    assert await _facts(db_session, user.id) == []
    assert await _chunk_texts(db_session, user.id) == ["User: factor x^2 - 7x + 12 for me"]


@pytest.mark.asyncio
async def test_a_short_add_never_overwrites_a_richer_fact(db_session):
    """M1: an add matches by exact text only."""
    user = await _user(db_session)
    rich = "User uses React Native and FastAPI for Recall"
    await apply_fact_ops(db_session, user.id, [_write("add", rich)], None, active_cap=150)
    await apply_fact_ops(
        db_session, user.id, [_write("add", "User uses React Native")], None, active_cap=150
    )

    assert await _facts(db_session, user.id) == [
        ("User uses React Native", "active"),
        (rich, "active"),
    ]


@pytest.mark.asyncio
async def test_the_fact_cap_never_evicts_what_the_user_asked_to_keep(db_session):
    """M8: at the cap, an explicit "remember …" fact survives; the oldest guess goes."""
    user = await _user(db_session)
    writes = [
        MemoryFactWrite(op="add", type="focus", text=f"User is busy with task {n}", confidence=0.9)
        for n in range(4)
    ]
    await apply_fact_ops(db_session, user.id, writes, None, active_cap=4)
    explicit = MemoryFactWrite(
        op="add", type="focus", text="User is vegetarian", confidence=0.9, importance=1.0
    )

    await apply_fact_ops(db_session, user.id, [explicit], None, active_cap=4)

    facts = await _facts(db_session, user.id)
    assert ("User is vegetarian", "active") in facts
    # The evicted fact is gone, not kept out of sight as "superseded".
    assert len(facts) == 4
    assert all(status == "active" for _, status in facts)

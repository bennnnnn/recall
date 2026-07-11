"""Real-Postgres tests for app.repositories.memories.

`test_memories.py` mocks `AsyncSession`, so a `WHERE user_id ==` filter that
was dropped or a `delete_by_type` that also deleted another type/user would
be invisible to it — the mock hands back the same canned result regardless
of the statement executed. These tests build real `Memory` rows for
multiple users/types and run the real compiled SQL via the `db_session`
fixture.
"""

from uuid import uuid4

import pytest

from app.models.orm import Memory
from app.repositories import memories as memories_repo
from app.repositories import users as users_repo


async def _make_user(session):
    return await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )


def _build_memory(user_id, *, memory_type, text):
    return Memory(user_id=user_id, type=memory_type, text=text)


@pytest.mark.asyncio
async def test_list_for_user_only_returns_that_users_memories(db_session):
    user_a = await _make_user(db_session)
    user_b = await _make_user(db_session)
    db_session.add_all(
        [
            _build_memory(user_a.id, memory_type="profile", text="A profile"),
            _build_memory(user_a.id, memory_type="preference", text="A preference"),
            _build_memory(user_b.id, memory_type="profile", text="B profile"),
        ]
    )
    await db_session.flush()

    result = await memories_repo.list_for_user(db_session, user_a.id)

    assert {m.text for m in result} == {"A profile", "A preference"}
    assert all(m.user_id == user_a.id for m in result)


@pytest.mark.asyncio
async def test_delete_by_type_only_deletes_matching_user_and_type(db_session):
    """delete_by_type(user_a, "profile") must not touch user_a's other
    memory types, nor user_b's "profile" memory (same type, different
    owner)."""
    user_a = await _make_user(db_session)
    user_b = await _make_user(db_session)
    db_session.add_all(
        [
            _build_memory(user_a.id, memory_type="profile", text="A profile"),
            _build_memory(user_a.id, memory_type="preference", text="A preference"),
            _build_memory(user_b.id, memory_type="profile", text="B profile"),
        ]
    )
    await db_session.flush()

    deleted = await memories_repo.delete_by_type(db_session, user_a.id, "profile")

    assert deleted == 1
    remaining_a = await memories_repo.list_for_user(db_session, user_a.id)
    assert {m.text for m in remaining_a} == {"A preference"}
    remaining_b = await memories_repo.list_for_user(db_session, user_b.id)
    assert {m.text for m in remaining_b} == {"B profile"}

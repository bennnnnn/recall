"""Real-Postgres tests for app.repositories.chats.

`test_chats.py` mocks `AsyncSession`, so it can only prove "did the
repository call `.execute()`". It cannot catch a `WHERE user_id ==` filter
that's missing or inverted, a broken `has_messages` EXISTS subquery/join, or
`archived` filtering that silently happens in Python instead of SQL — since
the mock returns the same canned rows regardless of the statement built.
These tests build real `User`/`Chat`/`Message` rows and run the real
compiled queries against Postgres via the `db_session` fixture
(`app/tests/repositories/conftest.py`).
"""

from uuid import uuid4

import pytest
from sqlalchemy import update

from app.models.orm import Chat
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.repositories import users as users_repo


async def _make_user(session):
    return await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )


async def _make_chat_with_message(session, user_id):
    """A chat with >=1 message — list_for_user only surfaces chats that have
    at least one message (has_messages EXISTS subquery)."""
    chat = await chats_repo.create(session, user_id=user_id, model="free-chat")
    await messages_repo.create(
        session,
        chat_id=chat.id,
        user_id=user_id,
        role="user",
        content="hello",
    )
    return chat


@pytest.mark.asyncio
async def test_get_by_id_returns_none_for_a_different_users_chat(db_session):
    """Proves the WHERE user_id == filter is real, not just present but
    broken/inverted — a mocked test can't distinguish "filtered correctly"
    from "ignored the filter and returned the canned row anyway"."""
    owner = await _make_user(db_session)
    other_user = await _make_user(db_session)
    chat = await chats_repo.create(db_session, user_id=owner.id, model="free-chat")

    assert await chats_repo.get_by_id(db_session, chat.id, other_user.id) is None

    found = await chats_repo.get_by_id(db_session, chat.id, owner.id)
    assert found is not None
    assert found.id == chat.id


@pytest.mark.asyncio
async def test_list_for_user_only_returns_calling_users_chats(db_session):
    """Two users each have a chat; list_for_user(user_a) must not leak
    user_b's chat."""
    user_a = await _make_user(db_session)
    user_b = await _make_user(db_session)
    chat_a = await _make_chat_with_message(db_session, user_a.id)
    await _make_chat_with_message(db_session, user_b.id)

    result = await chats_repo.list_for_user(db_session, user_a.id)

    assert [c.id for c in result] == [chat_a.id]


@pytest.mark.asyncio
async def test_list_for_user_excludes_chats_with_no_messages(db_session):
    """The has_messages EXISTS subquery must actually filter at the SQL
    level — an abandoned draft chat (zero messages) should never surface."""
    user = await _make_user(db_session)
    with_message = await _make_chat_with_message(db_session, user.id)
    await chats_repo.create(db_session, user_id=user.id, model="free-chat")  # no messages

    result = await chats_repo.list_for_user(db_session, user.id)

    assert [c.id for c in result] == [with_message.id]


@pytest.mark.asyncio
async def test_list_for_user_archived_filtering_happens_in_sql(db_session):
    """include_archived=False (default) must exclude archived chats at the
    SQL level; include_archived=True must include them."""
    user = await _make_user(db_session)
    active = await _make_chat_with_message(db_session, user.id)
    archived = await _make_chat_with_message(db_session, user.id)
    await chats_repo.set_archived(db_session, archived, True)

    default_result = await chats_repo.list_for_user(db_session, user.id)
    assert [c.id for c in default_result] == [active.id]

    with_archived = await chats_repo.list_for_user(db_session, user.id, include_archived=True)
    assert {c.id for c in with_archived} == {active.id, archived.id}


@pytest.mark.asyncio
async def test_generated_title_preserves_rename_and_owner_scope(db_session):
    owner = await _make_user(db_session)
    other_user = await _make_user(db_session)
    chat = await chats_repo.create(db_session, user_id=owner.id, model="free-chat")
    assert not await chats_repo.set_title_if_empty(
        db_session, chat.id, "Wrong owner", user_id=other_user.id
    )
    await db_session.execute(
        update(Chat)
        .where(Chat.id == chat.id)
        .values(title="Manual title")
        .execution_options(synchronize_session=False)
    )
    await db_session.commit()
    assert chat.title is None

    assert not await chats_repo.set_title_if_empty(
        db_session, chat.id, "Generated title", user_id=owner.id
    )
    await db_session.refresh(chat)
    assert chat.title == "Manual title"


@pytest.mark.asyncio
async def test_pin_archive_races_preserve_archived_unpinned_state(db_session):
    owner = await _make_user(db_session)
    chat = await chats_repo.create(db_session, user_id=owner.id, model="free-chat")
    await db_session.execute(
        update(Chat)
        .where(Chat.id == chat.id)
        .values(pinned=True)
        .execution_options(synchronize_session=False)
    )
    await db_session.commit()
    assert chat.pinned is False

    await chats_repo.set_archived(db_session, chat, True)
    assert chat.archived is True
    assert chat.pinned is False
    await chats_repo.set_pinned(db_session, chat, True)
    assert chat.archived is True
    assert chat.pinned is False

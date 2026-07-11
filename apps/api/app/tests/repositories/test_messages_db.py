"""Real-Postgres tests for app.repositories.messages.

`test_messages.py` mocks `AsyncSession` and returns a canned result no
matter what statement is executed, so it can't catch wrong ordering, a
`chat_id` scoping filter that's missing/inverted, or the tuple-comparison
`(created_at, id)` cutoff logic in `delete_messages_from` being off by one.
These tests build real `Message` rows (with explicit `created_at`/`id`
values, since Postgres `now()` is pinned to transaction start and every
fixture row in a test shares one transaction) and exercise the real
compiled SQL via the `db_session` fixture.
"""

import uuid
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.models.orm import Message
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


def _build_message(chat_id, user_id, *, created_at, message_id=None, role="user", content="msg"):
    """Construct a Message with an explicit created_at/id (bypassing the
    repository's `create()`, which has no way to control either) so ordering
    and cutoff tests are deterministic instead of racing the DB clock."""
    kwargs = {"id": message_id} if message_id is not None else {}
    return Message(
        chat_id=chat_id,
        user_id=user_id,
        role=role,
        content=content,
        created_at=created_at,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_list_recent_returns_correct_order_and_respects_limit(db_session):
    user = await _make_user(db_session)
    chat = await chats_repo.create(db_session, user_id=user.id, model="free-chat")
    base = datetime(2026, 1, 1, tzinfo=UTC)
    messages = [
        _build_message(chat.id, user.id, created_at=base + timedelta(minutes=i), content=f"m{i}")
        for i in range(5)
    ]
    db_session.add_all(messages)
    await db_session.flush()

    result = await messages_repo.list_recent(db_session, chat.id, limit=3)

    # list_recent takes the 3 newest (desc + limit) then reverses back to
    # chronological order — a wrong ORDER BY or a missing .reverse() would
    # both show up here.
    assert [m.content for m in result] == ["m2", "m3", "m4"]


@pytest.mark.asyncio
async def test_get_by_id_scoped_by_chat_does_not_leak_across_chats(db_session):
    user = await _make_user(db_session)
    chat_a = await chats_repo.create(db_session, user_id=user.id, model="free-chat")
    chat_b = await chats_repo.create(db_session, user_id=user.id, model="free-chat")
    message = await messages_repo.create(
        db_session, chat_id=chat_a.id, user_id=user.id, role="user", content="hi"
    )

    assert await messages_repo.get_by_id(db_session, message.id, chat_b.id) is None

    found = await messages_repo.get_by_id(db_session, message.id, chat_a.id)
    assert found is not None
    assert found.id == message.id


@pytest.mark.asyncio
async def test_delete_messages_from_respects_tuple_created_at_id_cutoff(db_session):
    """delete_messages_from deletes created_at > cutoff OR
    (created_at == cutoff AND id >= anchor_id). Build one message on each
    side of every branch of that tuple comparison. UUIDs built with
    `uuid.UUID(int=N)` compare the same way in Python and in Postgres (both
    compare the raw 128-bit value), so ordering is deterministic."""
    user = await _make_user(db_session)
    chat = await chats_repo.create(db_session, user_id=user.id, model="free-chat")
    cutoff = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    anchor_id = uuid.UUID(int=5)

    before_cutoff = _build_message(
        chat.id,
        user.id,
        created_at=cutoff - timedelta(minutes=1),
        message_id=uuid.UUID(int=1),
        content="before",
    )
    same_time_lower_id = _build_message(
        chat.id,
        user.id,
        created_at=cutoff,
        message_id=uuid.UUID(int=2),
        content="same-time-lower-id",
    )
    anchor = _build_message(
        chat.id, user.id, created_at=cutoff, message_id=anchor_id, content="anchor"
    )
    same_time_higher_id = _build_message(
        chat.id,
        user.id,
        created_at=cutoff,
        message_id=uuid.UUID(int=9),
        content="same-time-higher-id",
    )
    after_cutoff = _build_message(
        chat.id,
        user.id,
        created_at=cutoff + timedelta(minutes=1),
        message_id=uuid.UUID(int=10),
        content="after",
    )
    db_session.add_all(
        [before_cutoff, same_time_lower_id, anchor, same_time_higher_id, after_cutoff]
    )
    await db_session.flush()

    deleted_count = await messages_repo.delete_messages_from(
        db_session, chat.id, from_created_at=cutoff, from_message_id=anchor_id
    )

    # anchor itself (id >= anchor), same_time_higher_id (id >= anchor), and
    # after_cutoff (created_at > cutoff) should go; the two "kept" rows below
    # must survive.
    assert deleted_count == 3

    remaining = await messages_repo.list_all(db_session, chat.id)
    assert {m.content for m in remaining} == {"before", "same-time-lower-id"}

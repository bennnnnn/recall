"""CI coverage for PostgreSQL's actual trigram + substring search query."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.orm import Chat, Message
from app.repositories import search as search_repo
from app.repositories import users as users_repo


async def _user(session):
    return await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Search Test",
        avatar_url=None,
        google_sub=str(uuid4()),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query, distractor", [("%%", "ordinary"), ("__", "ordinary"), (r"\\", "\\")]
)
@pytest.mark.parametrize("match_type", ["title", "message"])
async def test_search_literal_symbols_with_real_trigram_operator(
    db_session, query, distractor, match_type
):
    owner = await _user(db_session)
    matching = Chat(user_id=owner.id, title=query if match_type == "title" else "Notes")
    unrelated = Chat(user_id=owner.id, title=distractor if match_type == "title" else "Notes")
    db_session.add_all([matching, unrelated])
    await db_session.flush()
    if match_type == "message":
        db_session.add_all(
            [
                Message(chat_id=chat.id, user_id=owner.id, role="user", content=content)
                for chat, content in [(matching, query), (unrelated, distractor)]
            ]
        )
    await db_session.commit()

    rows, total = await search_repo.search_conversations(db_session, owner.id, query)

    assert total == 1
    assert [row["chat_id"] for row in rows] == [matching.id]


@pytest.mark.asyncio
async def test_search_preserves_fuzzy_title_matching(db_session):
    owner = await _user(db_session)
    chat = Chat(user_id=owner.id, title="vacation")
    db_session.add(chat)
    await db_session.commit()

    rows, total = await search_repo.search_conversations(db_session, owner.id, "vacaton")

    assert total == 1
    assert [row["chat_id"] for row in rows] == [chat.id]


@pytest.mark.asyncio
async def test_search_scopes_both_message_and_chat_owners_and_excludes_archived(db_session):
    owner = await _user(db_session)
    other = await _user(db_session)
    allowed = Chat(user_id=owner.id, title="needle")
    private = Chat(user_id=other.id, title="needle secret")
    archived = Chat(user_id=owner.id, title="needle old", archived=True)
    db_session.add_all([allowed, private, archived])
    await db_session.flush()
    db_session.add_all(
        [
            Message(chat_id=chat.id, user_id=owner.id, role="user", content="needle")
            for chat in [allowed, private, archived]
        ]
    )
    await db_session.commit()

    rows, total = await search_repo.search_conversations(db_session, owner.id, "needle")

    assert total == 1
    assert [row["chat_id"] for row in rows] == [allowed.id]
    assert rows[0]["match_type"] == "message"


@pytest.mark.asyncio
async def test_search_equal_timestamp_pages_have_stable_order_and_total(db_session):
    owner = await _user(db_session)
    now = datetime(2026, 9, 4, tzinfo=UTC)
    chat_ids = sorted([uuid4(), uuid4()])
    message_ids = sorted([uuid4(), uuid4()])
    messages_chat = Chat(id=chat_ids[0], user_id=owner.id, title="needle", updated_at=now)
    title_chat = Chat(id=chat_ids[1], user_id=owner.id, title="needle", updated_at=now)
    db_session.add_all([messages_chat, title_chat])
    await db_session.flush()
    db_session.add_all(
        [
            Message(
                id=message_id,
                chat_id=messages_chat.id,
                user_id=owner.id,
                role="user",
                content="needle",
                created_at=now,
            )
            for message_id in message_ids
        ]
    )
    await db_session.commit()

    pages = [
        await search_repo.search_conversations(
            db_session, owner.id, "needle", limit=1, offset=offset
        )
        for offset in range(3)
    ]

    assert [total for _, total in pages] == [3, 3, 3]
    assert [(rows[0]["chat_id"], rows[0]["message_id"]) for rows, _ in pages] == [
        (title_chat.id, None),
        (messages_chat.id, message_ids[1]),
        (messages_chat.id, message_ids[0]),
    ]
    assert await search_repo.search_conversations(
        db_session, owner.id, "needle", limit=1, offset=99
    ) == ([], 3)
    assert await search_repo.search_conversations(db_session, owner.id, "unrelated", limit=1) == (
        [],
        0,
    )

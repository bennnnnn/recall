"""Execute search SQL locally; PostgreSQL-specific fuzzy matching has CI coverage."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, false
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.orm import Chat, Message
from app.repositories import search as search_repo


def _id(index: int) -> UUID:
    # Include a hex letter so SQLite's UUID column keeps text affinity.
    return UUID(f"aaaaaaaa-0000-0000-0000-{index:012d}")


@pytest.fixture
def search_session(monkeypatch):
    engine = create_engine("sqlite://")
    Chat.__table__.create(engine)
    Message.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as sync_session:
        session = AsyncMock(spec=AsyncSession)
        session.execute.side_effect = sync_session.execute
        session.__aenter__.return_value = session
        # Only replace the PostgreSQL operator; execute the real substring,
        # ownership, merged ordering, limit and count SQL.
        monkeypatch.setattr(search_repo, "_trgm_match", lambda *_: false())
        monkeypatch.setattr(search_repo, "SessionLocal", lambda: session, raising=False)
        yield sync_session, session
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("query, distractor", [("a_b", "axb"), ("50%", "500"), ("C:\\", "C:/")])
@pytest.mark.parametrize("match_type", ["title", "message"])
async def test_search_treats_substring_metacharacters_literally(
    search_session, query, distractor, match_type
):
    sync_session, session = search_session
    owner_id = uuid4()
    matching = Chat(user_id=owner_id, title=query if match_type == "title" else "Notes")
    unrelated = Chat(user_id=owner_id, title=distractor if match_type == "title" else "Notes")
    sync_session.add_all([matching, unrelated])
    sync_session.flush()
    if match_type == "message":
        sync_session.add_all(
            [
                Message(chat_id=chat.id, user_id=owner_id, role="user", content=content)
                for chat, content in [(matching, query), (unrelated, distractor)]
            ]
        )
    sync_session.commit()

    results, total = await search_repo.search_conversations(session, owner_id, query)

    assert total == 1
    assert [result["chat_id"] for result in results] == [matching.id]


@pytest.mark.asyncio
async def test_search_message_hit_requires_chat_owner(search_session):
    sync_session, session = search_session
    owner_id = uuid4()
    other_chat = Chat(user_id=uuid4(), title="Private title")
    sync_session.add(other_chat)
    sync_session.flush()
    # Both foreign keys are valid; the schema does not constrain their owners
    # to match. Search must not expose another owner's conversation metadata.
    sync_session.add(
        Message(chat_id=other_chat.id, user_id=owner_id, role="user", content="needle")
    )
    sync_session.commit()

    assert await search_repo.search_conversations(session, owner_id, "needle") == ([], 0)


@pytest.mark.asyncio
async def test_search_orders_equal_timestamps_before_offset(search_session):
    sync_session, session = search_session
    owner_id = uuid4()
    now = datetime(2026, 9, 4, tzinfo=UTC)
    messages_chat = Chat(id=_id(1), user_id=owner_id, title="needle", updated_at=now)
    title_chat = Chat(id=_id(2), user_id=owner_id, title="needle", updated_at=now)
    sync_session.add_all([messages_chat, title_chat])
    sync_session.flush()
    sync_session.add_all(
        [
            Message(
                id=_id(index),
                chat_id=messages_chat.id,
                user_id=owner_id,
                role="user",
                content="needle",
                created_at=now,
            )
            for index in [1, 2]
        ]
    )
    sync_session.commit()

    pages = [
        await search_repo.search_conversations(session, owner_id, "needle", limit=1, offset=offset)
        for offset in range(3)
    ]

    assert [total for _, total in pages] == [3, 3, 3]
    assert [(rows[0]["chat_id"], rows[0]["message_id"]) for rows, _ in pages] == [
        (title_chat.id, None),
        (messages_chat.id, _id(2)),
        (messages_chat.id, _id(1)),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("offset", [0, 1, 10])
async def test_search_page_and_total_share_one_statement(search_session, offset):
    sync_session, session = search_session
    owner_id = uuid4()
    chat = Chat(user_id=owner_id, title="needle")
    sync_session.add(chat)
    sync_session.commit()

    results, total = await search_repo.search_conversations(
        session, owner_id, "needle", limit=1, offset=offset
    )

    assert len(results) == (1 if offset == 0 else 0)
    assert total == 1
    # A single SQL statement gives both values one database snapshot, including
    # out-of-range offsets; no independently racing count connection.
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_empty_result_keeps_zero_total(search_session):
    _, session = search_session
    assert await search_repo.search_conversations(session, uuid4(), "absent") == ([], 0)

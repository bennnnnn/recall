"""Execute search SQL locally; PostgreSQL-specific fuzzy matching has CI coverage."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, false
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.orm import Attachment, Chat, Message
from app.modules.search import repository as search_repo
from app.repositories.keyset import encode_cursor


def _id(index: int) -> UUID:
    # Include a hex letter so SQLite's UUID column keeps text affinity.
    return UUID(f"aaaaaaaa-0000-0000-0000-{index:012d}")


@pytest.fixture
def search_session(monkeypatch):
    engine = create_engine("sqlite://")
    Chat.__table__.create(engine)
    Message.__table__.create(engine)
    Attachment.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as sync_session:
        session = AsyncMock(spec=AsyncSession)
        session.execute.side_effect = sync_session.execute
        session.__aenter__.return_value = session
        # Only replace the PostgreSQL operator; execute the real substring,
        # ownership, merged ordering and limit SQL.
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

    results, next_cursor = await search_repo.search_conversations(session, owner_id, query)

    assert next_cursor is None
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

    assert await search_repo.search_conversations(session, owner_id, "needle") == ([], None)


@pytest.mark.asyncio
async def test_search_pages_equal_timestamps_by_cursor(search_session):
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

    pages = []
    cursor = None
    for _ in range(4):
        page = await search_repo.search_conversations(
            session, owner_id, "needle", limit=1, cursor=cursor
        )
        pages.append(page)
        cursor = page[1]

    assert [next_cursor is not None for _, next_cursor in pages] == [True, True, True, False]
    # Titles first (both chats' titles match), then the messages, newest first.
    assert [(r[0]["match_type"], r[0]["chat_id"], r[0]["message_id"]) for r, _ in pages] == [
        ("title", title_chat.id, None),
        ("title", messages_chat.id, None),
        ("message", messages_chat.id, _id(2)),
        ("message", messages_chat.id, _id(1)),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("after_the_hit", [False, True])
async def test_search_page_and_cursor_share_one_statement(search_session, after_the_hit):
    sync_session, session = search_session
    owner_id = uuid4()
    at = datetime(2026, 9, 4, tzinfo=UTC)
    chat = Chat(user_id=owner_id, title="needle", updated_at=at)
    sync_session.add(chat)
    sync_session.commit()
    # The cursor after the title hit: its rank (title), time, chat and no row of its own.
    cursor = encode_cursor(at, UUID(int=2), chat.id, UUID(int=0)) if after_the_hit else None

    results, next_cursor = await search_repo.search_conversations(
        session, owner_id, "needle", limit=1, cursor=cursor
    )

    assert len(results) == (0 if after_the_hit else 1)
    assert next_cursor is None
    # One statement reads the page and the row past it; nothing counts every hit. The
    # second reads the page's message words by id, whatever the page holds.
    assert session.execute.await_count == 2
    assert "count(" not in str(session.execute.await_args_list[0].args[0]).lower()


@pytest.mark.asyncio
async def test_search_empty_result_has_no_more(search_session):
    _, session = search_session
    assert await search_repo.search_conversations(session, uuid4(), "absent") == ([], None)


def _sent_with_pdf(sync_session, owner_id, chat, *, typed: str, file_text: str) -> Message:
    """A user message as the server stores it: the words typed, the file's lines, its text."""
    attachment_id = uuid4()
    message = Message(
        chat_id=chat.id,
        user_id=owner_id,
        role="user",
        content=(
            f"{typed}\n\n[File: /attachments/{attachment_id}/file]\n"
            f"[File (application/pdf)]\n[page 1] {file_text}"
        ),
    )
    sync_session.add(message)
    sync_session.flush()
    sync_session.add(
        Attachment(
            id=attachment_id,
            user_id=owner_id,
            message_id=message.id,
            storage_key="k",
            content_type="application/pdf",
            size_bytes=1,
            original_filename="Chemistry Study Guide.pdf",
        )
    )
    return message


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["molar mass", "attachments", "application/pdf", "page 1"])
async def test_search_never_matches_a_files_text_or_its_markers(search_session, query):
    sync_session, session = search_session
    owner_id = uuid4()
    chat = Chat(user_id=owner_id, title="Notes")
    sync_session.add(chat)
    sync_session.flush()
    _sent_with_pdf(sync_session, owner_id, chat, typed="When is my test?", file_text="molar mass")
    sync_session.commit()

    results, _ = await search_repo.search_conversations(session, owner_id, query)

    assert results == []


@pytest.mark.asyncio
async def test_search_quotes_only_the_words_typed(search_session):
    sync_session, session = search_session
    owner_id = uuid4()
    chat = Chat(user_id=owner_id, title="Notes")
    sync_session.add(chat)
    sync_session.flush()
    _sent_with_pdf(sync_session, owner_id, chat, typed="When is my test?", file_text="molar mass")
    sync_session.commit()

    results, _ = await search_repo.search_conversations(session, owner_id, "my test")

    assert [(r["match_type"], r["content"]) for r in results] == [("message", "When is my test?")]


@pytest.mark.asyncio
async def test_search_finds_a_file_by_its_name_and_opens_its_message(search_session):
    sync_session, session = search_session
    owner_id = uuid4()
    chat = Chat(user_id=owner_id, title="Notes")
    sync_session.add(chat)
    sync_session.flush()
    message = _sent_with_pdf(sync_session, owner_id, chat, typed="Here", file_text="text")
    sync_session.commit()

    results, _ = await search_repo.search_conversations(session, owner_id, "study guide")

    assert [(r["match_type"], r["content"], r["message_id"]) for r in results] == [
        ("file", "Chemistry Study Guide.pdf", message.id)
    ]


@pytest.mark.asyncio
async def test_search_lists_titles_then_files_then_messages(search_session):
    sync_session, session = search_session
    owner_id = uuid4()
    older = datetime(2026, 1, 1, tzinfo=UTC)
    newer = datetime(2026, 9, 1, tzinfo=UTC)
    titled = Chat(user_id=owner_id, title="Chemistry plan", updated_at=older)
    other = Chat(user_id=owner_id, title="Notes", updated_at=newer)
    sync_session.add_all([titled, other])
    sync_session.flush()
    _sent_with_pdf(sync_session, owner_id, other, typed="my chemistry homework", file_text="x")
    sync_session.commit()

    results, _ = await search_repo.search_conversations(session, owner_id, "chemistry")

    # The oldest hit is a title: it still comes first, then the file, then the message.
    assert [r["match_type"] for r in results] == ["title", "file", "message"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "typed", ["Todo\n[File a bug] login crash on iOS", "[Image of the chart] login crash"]
)
async def test_search_keeps_words_typed_in_brackets(search_session, typed):
    """Only the server's own markers (``[File: /attachments/…]``) end what the user typed."""
    sync_session, session = search_session
    owner_id = uuid4()
    chat = Chat(user_id=owner_id, title="Notes")
    sync_session.add(chat)
    sync_session.flush()
    sync_session.add(Message(chat_id=chat.id, user_id=owner_id, role="user", content=typed))
    sync_session.commit()

    results, _ = await search_repo.search_conversations(session, owner_id, "login crash")

    assert [r["match_type"] for r in results] == ["message"]

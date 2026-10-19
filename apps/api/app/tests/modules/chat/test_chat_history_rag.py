"""Chat-history semantic RAG: index past turns, retrieve a small top-k."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.attachments.rag import chunk_text
from app.modules.chat.history_rag import (
    embed_query_for_prompt,
    index_message,
    index_turn_messages,
    prepare_message_text,
    retrieve_for_prompt,
)


def test_prepare_message_text_skips_short_and_system():
    assert prepare_message_text("system", "hello there friend") is None
    assert prepare_message_text("user", "ok") is None
    assert prepare_message_text("user", "  ") is None


def test_prepare_message_text_strips_attachment_excerpt():
    text = prepare_message_text(
        "user",
        "Please summarize this.\n[File: /attachments/abc/file]\n[File (application/pdf)]\nsecret",
    )
    assert text == "User: Please summarize this."
    assert "secret" not in (text or "")


def test_prepare_message_text_labels_roles():
    assert prepare_message_text("assistant", "Here is the recipe for injera batter.") == (
        "Assistant: Here is the recipe for injera batter."
    )


def _session_cm():
    @asynccontextmanager
    async def _cm(*_args, **_kwargs):
        yield MagicMock()

    return _cm


@pytest.mark.asyncio
async def test_retrieve_for_prompt_degrades_on_db_error():
    settings = Settings(chat_history_rag_enabled=True, mock_llm_enabled=True)
    with (
        patch("app.modules.chat.history_rag.SessionLocal", _session_cm()),
        patch(
            "app.modules.chat.history_rag.chunks_repo.has_chunks_for_user",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.modules.chat.history_rag.embedding_gateway.get_or_embed_query",
            AsyncMock(return_value=[0.1] * 1536),
        ),
        patch(
            "app.modules.chat.history_rag.chunks_repo.search_semantic",
            AsyncMock(side_effect=RuntimeError("db exploded")),
        ),
        patch("app.modules.chat.history_rag.chunks_repo.EMBEDDING_DIM", 1536),
    ):
        block = await retrieve_for_prompt(
            settings,
            user_id=uuid4(),
            query="what did we decide about the lease?",
        )
    assert block == ""


@pytest.mark.asyncio
async def test_retrieve_for_prompt_skips_embed_when_no_chunks():
    embed_mock = AsyncMock(return_value=[0.1] * 1536)
    with (
        patch("app.modules.chat.history_rag.SessionLocal", _session_cm()),
        patch(
            "app.modules.chat.history_rag.chunks_repo.has_chunks_for_user",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.modules.chat.history_rag.embedding_gateway.get_or_embed_query",
            embed_mock,
        ),
    ):
        block = await retrieve_for_prompt(
            settings=Settings(chat_history_rag_enabled=True, mock_llm_enabled=True),
            user_id=uuid4(),
            query="old conversation",
        )
    assert block == ""
    embed_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_retrieve_for_prompt_disabled_or_empty_query():
    with patch(
        "app.modules.chat.history_rag.chunks_repo.has_chunks_for_user",
        AsyncMock(),
    ) as probe:
        assert (
            await retrieve_for_prompt(
                Settings(chat_history_rag_enabled=False),
                user_id=uuid4(),
                query="hello",
            )
            == ""
        )
        assert (
            await retrieve_for_prompt(
                Settings(chat_history_rag_enabled=True),
                user_id=uuid4(),
                query="   ",
            )
            == ""
        )
    probe.assert_not_awaited()


@pytest.mark.asyncio
async def test_retrieve_for_prompt_wraps_hits_and_excludes():
    row = MagicMock()
    row.text = "User: we picked the blue couch"
    exclude = {uuid4()}
    with (
        patch("app.modules.chat.history_rag.SessionLocal", _session_cm()),
        patch(
            "app.modules.chat.history_rag.chunks_repo.has_chunks_for_user",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.modules.chat.history_rag.embedding_gateway.get_or_embed_query",
            AsyncMock(return_value=[0.1] * 8),
        ),
        patch(
            "app.modules.chat.history_rag.chunks_repo.search_semantic",
            AsyncMock(return_value=[row]),
        ) as search,
        patch(
            "app.modules.chat.history_rag.embedding_gateway.parse_embedding",
            return_value=[0.1] * 8,
        ),
        patch(
            "app.modules.chat.history_rag.embedding_gateway.cosine_similarity",
            return_value=0.9,
        ),
        patch("app.modules.chat.history_rag.chunks_repo.EMBEDDING_DIM", 1536),
    ):
        block = await retrieve_for_prompt(
            Settings(chat_history_rag_enabled=True, mock_llm_enabled=True),
            user_id=uuid4(),
            query="which couch",
            exclude_message_ids=exclude,
        )
    assert "earlier chats" in block
    assert "not this conversation and not saved memory" in block
    assert "blue couch" in block
    assert "not the full history" in block
    assert search.await_args.kwargs["exclude_message_ids"] == exclude


@pytest.mark.asyncio
async def test_embed_query_for_prompt_degrades_on_timeout():
    with (
        patch("app.modules.chat.history_rag.SessionLocal", _session_cm()),
        patch(
            "app.modules.chat.history_rag.chunks_repo.has_chunks_for_user",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.modules.chat.history_rag.embedding_gateway.get_or_embed_query",
            AsyncMock(return_value=None),
        ),
    ):
        vec = await embed_query_for_prompt(
            Settings(chat_history_rag_enabled=True, mock_llm_enabled=True),
            user_id=uuid4(),
            query="what did we decide about the lease?",
        )
    assert vec is None


@pytest.mark.asyncio
async def test_retrieve_for_prompt_uses_precomputed_vec_without_reembed():
    row = MagicMock()
    row.text = "User: we picked the blue couch"
    exclude = {uuid4()}
    embed = AsyncMock(return_value=[0.1] * 8)
    with (
        patch("app.modules.chat.history_rag.SessionLocal", _session_cm()),
        patch(
            "app.modules.chat.history_rag.chunks_repo.has_chunks_for_user",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.modules.chat.history_rag.embedding_gateway.get_or_embed_query",
            embed,
        ),
        patch(
            "app.modules.chat.history_rag.chunks_repo.search_semantic",
            AsyncMock(return_value=[row]),
        ) as search,
        patch(
            "app.modules.chat.history_rag.embedding_gateway.parse_embedding",
            return_value=[0.1] * 8,
        ),
        patch(
            "app.modules.chat.history_rag.embedding_gateway.cosine_similarity",
            return_value=0.9,
        ),
        patch("app.modules.chat.history_rag.chunks_repo.EMBEDDING_DIM", 1536),
    ):
        block = await retrieve_for_prompt(
            Settings(chat_history_rag_enabled=True, mock_llm_enabled=True),
            user_id=uuid4(),
            query="which couch",
            exclude_message_ids=exclude,
            query_vec=[0.2] * 8,
        )
    assert "blue couch" in block
    embed.assert_not_awaited()
    assert search.await_args.kwargs["exclude_message_ids"] == exclude
    assert search.await_args.args[2] == [0.2] * 8


@pytest.mark.asyncio
async def test_load_context_blocks_does_not_wait_on_history_embed_before_recent():
    """Recent-window load must not sit behind the RAG query embed."""
    import time

    from app.modules.chat.prompt_builder import _load_context_blocks

    async def slow_embed(*_args, **_kwargs):
        await asyncio.sleep(0.2)
        return [0.2]

    recent_at: dict[str, float] = {}

    async def fast_recent(*_args, **_kwargs):
        recent_at["t"] = time.perf_counter()
        return []

    t0 = time.perf_counter()
    user = MagicMock()
    user.id = uuid4()
    with (
        patch("app.modules.chat.prompt_context.SessionLocal", _session_cm()),
        patch("app.modules.chat.prompt_context.messages_repo.list_recent", fast_recent),
        patch(
            "app.modules.chat.history_rag.embed_query_for_prompt",
            slow_embed,
        ),
    ):
        blocks = await _load_context_blocks(
            user,
            uuid4(),
            Settings(chat_history_rag_enabled=True),
            chat=None,
            query_text="which couch did we pick last year",
            recent_limit=20,
            slim_context=True,
            client_timezone=None,
            out=None,
            history_rag=True,
        )
    assert recent_at["t"] - t0 < 0.1
    assert blocks.history_rag_query_vec == [0.2]


def test_slim_memory_cap_keeps_complete_fact_boundaries():
    from app.modules.chat.prompt_context import _cap_slim_memory_block

    first_fact = "x" * 600
    second_fact = "y" * 600
    block = f"Known facts about the user:\n\n## Preferences\n- {first_fact}\n- {second_fact}"

    capped = _cap_slim_memory_block(block)

    assert len(capped) <= 1000
    assert f"- {first_fact}" in capped
    assert "y" not in capped
    assert not capped.endswith("…")


@pytest.mark.asyncio
@pytest.mark.parametrize("rich_context", [True, False], ids=["rich", "slim"])
@pytest.mark.parametrize(
    "has_chunks,query_vec",
    [
        pytest.param(False, None, id="empty-history"),
        pytest.param(True, None, id="embed-timeout"),
        pytest.param(True, [0.2] * 1536, id="embedded-history"),
    ],
)
async def test_build_prompt_uses_gathered_history_embedding_once(
    has_chunks, query_vec, rich_context
):
    """Rich and ordinary slim turns both retrieve relevant long-term context."""
    from app.modules.chat.prompt_builder import build_prompt_messages

    query = "which couch did we pick last year?"
    chat_id = uuid4()
    user = MagicMock(
        id=uuid4(),
        email="test@example.com",
        location_enabled=False,
        response_style="balanced",
        response_tone="casual",
        locale="en",
        timezone="UTC",
        custom_instructions=None,
    )
    user.name = "Test User"
    chat = MagicMock(id=chat_id, summary=None, summary_message_count=0)
    probe = AsyncMock(return_value=has_chunks)
    # The gateway returns None after its foreground embedding timeout.
    embed = AsyncMock(return_value=query_vec)
    row = MagicMock(text="User: We chose the blue couch.")
    with (
        patch("app.modules.chat.prompt_builder.SessionLocal", _session_cm()),
        patch("app.modules.chat.prompt_context.SessionLocal", _session_cm()),
        patch("app.modules.chat.history_rag.SessionLocal", _session_cm()),
        patch("app.modules.memory.get_memory_block", AsyncMock(return_value="")),
        patch("app.modules.todos.build_todos_system_section", AsyncMock(return_value=None)),
        patch("app.modules.chat.history_rag.chunks_repo.has_chunks_for_user", probe),
        patch("app.modules.chat.history_rag.embedding_gateway.get_or_embed_query", embed),
        patch(
            "app.modules.chat.history_rag.chunks_repo.search_semantic",
            AsyncMock(return_value=[row]),
        ) as search,
    ):
        messages = await build_prompt_messages(
            user,
            chat_id,
            Settings(chat_history_rag_enabled=True, attachment_rag_enabled=False),
            query_text=query,
            chat=chat,
            rich_context=rich_context,
            recent_messages=[],
        )

    probe.assert_awaited_once()
    assert embed.await_count == int(has_chunks)
    assert messages[0]["role"] == "system"
    if query_vec is None:
        search.assert_not_awaited()
        assert row.text not in messages[0]["content"]
    else:
        search.assert_awaited_once()
        assert search.await_args.args[2] == query_vec
        assert row.text in messages[0]["content"]


@pytest.mark.asyncio
async def test_index_message_uses_short_lived_session():
    settings = Settings(chat_history_rag_enabled=True, mock_llm_enabled=True)
    message = MagicMock()
    message.id = uuid4()
    message.chat_id = uuid4()
    message.role = "user"
    message.content = "Remember that my lease ends in March 2027."
    open_count = 0
    live = 0
    max_live = 0

    @asynccontextmanager
    async def _cm(*_args, **_kwargs):
        nonlocal open_count, live, max_live
        open_count += 1
        live += 1
        max_live = max(max_live, live)
        try:
            yield MagicMock()
        finally:
            live -= 1

    async def _embed(*_a, **_k):
        assert live == 0
        return [0.1] * 8

    with (
        patch("app.modules.chat.history_rag.SessionLocal", _cm),
        patch(
            "app.modules.chat.history_rag.embedding_gateway.embed_text",
            _embed,
        ),
        patch(
            "app.modules.chat.history_rag.chunks_repo.replace_chunks",
            AsyncMock(),
        ) as replace_mock,
    ):
        count = await index_message(settings, user_id=uuid4(), message=message)

    assert count == 1
    assert open_count == 1
    assert max_live == 1
    replace_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_index_message_stores_failed_piece_as_null_under_shared_concurrency():
    """Pieces embed under the shared ``embedding_concurrency`` (the gateway caps requests in
    flight); a piece whose embed failed is still stored, in its place, with a null vector
    (search skips it)."""
    settings = Settings(
        chat_history_rag_enabled=True,
        chat_history_rag_chunk_chars=30,
        chat_history_rag_chunk_overlap=0,
        embedding_concurrency=2,
    )
    message = MagicMock()
    message.id = uuid4()
    message.chat_id = uuid4()
    message.role = "user"
    message.content = "My lease ends in March 2027 and the landlord wants sixty days notice first."
    text = prepare_message_text(message.role, message.content) or ""
    pieces = chunk_text(text, chunk_chars=30, overlap=0)
    assert len(pieces) >= 3
    seen: dict = {}

    async def _embed_many(_settings, texts, *, concurrency):
        seen["texts"], seen["concurrency"] = texts, concurrency
        return [None if text == pieces[1] else [float(len(text))] for text in texts]

    with (
        patch("app.modules.chat.history_rag.SessionLocal", _session_cm()),
        patch("app.modules.chat.history_rag.embedding_gateway.embed_many", _embed_many),
        patch(
            "app.modules.chat.history_rag.chunks_repo.replace_chunks", AsyncMock()
        ) as replace_mock,
    ):
        count = await index_message(settings, user_id=uuid4(), message=message)

    assert count == len(pieces)
    assert seen == {"texts": pieces, "concurrency": 2}
    assert replace_mock.call_args.kwargs["chunks"] == [
        (index, piece, None if index == 1 else [float(len(piece))])
        for index, piece in enumerate(pieces)
    ]


async def _index_a_turn(*, edited_at: datetime | None = None, memory_on: bool = True) -> int:
    settings = Settings(chat_history_rag_enabled=True, mock_llm_enabled=True)
    account = SimpleNamespace(memory_enabled=memory_on, memory_edited_at=edited_at)
    user_id = uuid4()
    chat_id = uuid4()
    assistant = MagicMock()
    assistant.id = uuid4()
    assistant.chat_id = chat_id
    assistant.role = "assistant"
    assistant.content = "We should renew the lease in March."
    user_msg = MagicMock()
    user_msg.id = uuid4()
    user_msg.chat_id = chat_id
    user_msg.role = "user"
    user_msg.content = "When does my apartment lease end again?"
    older = MagicMock()
    older.id = uuid4()
    older.chat_id = uuid4()
    older.role = "user"
    older.content = "I live in a two-bedroom near the lake."
    older.created_at = datetime(2026, 1, 1, tzinfo=UTC)

    with (
        patch("app.modules.chat.history_rag.SessionLocal", _session_cm()),
        patch(
            "app.modules.chat.history_rag.users_repo.get_by_id",
            AsyncMock(return_value=account),
        ),
        patch(
            "app.modules.chat.history_rag.chunks_repo.count_for_user",
            AsyncMock(return_value=0),
        ),
        patch(
            "app.modules.chat.history_rag.messages_repo.get_by_id",
            AsyncMock(return_value=assistant),
        ),
        patch(
            "app.modules.chat.history_rag.messages_repo.get_last_user",
            AsyncMock(return_value=user_msg),
        ),
        patch(
            "app.modules.chat.history_rag.index_message",
            AsyncMock(return_value=1),
        ) as index_one,
        patch(
            "app.modules.chat.history_rag.messages_repo.list_recent_for_user",
            AsyncMock(return_value=[user_msg, assistant, older]),
        ),
        patch(
            "app.modules.chat.history_rag.chunks_repo.indexed_message_ids",
            AsyncMock(return_value=set()),
        ),
    ):
        count = await index_turn_messages(
            settings,
            user_id=user_id,
            chat_id=chat_id,
            assistant_message_id=assistant.id,
        )

    if not memory_on:
        assert count == 0
        index_one.assert_not_awaited()
        return count
    indexed = {call.kwargs["message"].id for call in index_one.await_args_list}
    assert user_msg.id in indexed and assistant.id in indexed
    # After "clear all", the backfill skips what was said before it (M13).
    assert (older.id in indexed) is (edited_at is None)
    return count


@pytest.mark.asyncio
async def test_index_turn_messages_backfills_when_corpus_empty():
    assert await _index_a_turn() == 3


@pytest.mark.asyncio
async def test_index_turn_messages_backfill_skips_lines_before_a_memory_clear():
    assert await _index_a_turn(edited_at=datetime(2026, 6, 1, tzinfo=UTC)) == 2


@pytest.mark.asyncio
async def test_index_turn_messages_indexes_nothing_while_memory_is_off():
    """M14: memory off means no personal recall, so nothing is indexed for it."""
    assert await _index_a_turn(memory_on=False) == 0


@pytest.mark.asyncio
async def test_retrieved_snippets_carry_the_day_they_were_said():
    row = MagicMock()
    row.text = "User: we picked Neon over Supabase"
    row.created_at = datetime(2026, 5, 3, tzinfo=UTC)
    with (
        patch("app.modules.chat.history_rag.SessionLocal", _session_cm()),
        patch(
            "app.modules.chat.history_rag.chunks_repo.search_semantic",
            AsyncMock(return_value=[row]),
        ),
    ):
        block = await retrieve_for_prompt(
            Settings(chat_history_rag_enabled=True, mock_llm_enabled=True),
            user_id=uuid4(),
            query="which database",
            query_vec=[0.1] * 1536,
        )
    assert "[1] (2026-05-03) User: we picked Neon over Supabase" in block

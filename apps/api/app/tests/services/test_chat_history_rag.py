"""Chat-history semantic RAG: index past turns, retrieve a small top-k."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat_history_rag import (
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
        patch("app.services.chat_history_rag.SessionLocal", _session_cm()),
        patch(
            "app.services.chat_history_rag.chunks_repo.has_chunks_for_user",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.services.chat_history_rag.embedding_gateway.get_or_embed_query",
            AsyncMock(return_value=[0.1] * 1536),
        ),
        patch(
            "app.services.chat_history_rag.chunks_repo.search_semantic",
            AsyncMock(side_effect=RuntimeError("db exploded")),
        ),
        patch("app.services.chat_history_rag.chunks_repo.EMBEDDING_DIM", 1536),
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
        patch("app.services.chat_history_rag.SessionLocal", _session_cm()),
        patch(
            "app.services.chat_history_rag.chunks_repo.has_chunks_for_user",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.services.chat_history_rag.embedding_gateway.get_or_embed_query",
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
        "app.services.chat_history_rag.chunks_repo.has_chunks_for_user",
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
        patch("app.services.chat_history_rag.SessionLocal", _session_cm()),
        patch(
            "app.services.chat_history_rag.chunks_repo.has_chunks_for_user",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.services.chat_history_rag.embedding_gateway.get_or_embed_query",
            AsyncMock(return_value=[0.1] * 8),
        ),
        patch(
            "app.services.chat_history_rag.chunks_repo.search_semantic",
            AsyncMock(return_value=[row]),
        ) as search,
        patch(
            "app.services.chat_history_rag.embedding_gateway.parse_embedding",
            return_value=[0.1] * 8,
        ),
        patch(
            "app.services.chat_history_rag.embedding_gateway.cosine_similarity",
            return_value=0.9,
        ),
        patch("app.services.chat_history_rag.chunks_repo.EMBEDDING_DIM", 1536),
    ):
        block = await retrieve_for_prompt(
            Settings(chat_history_rag_enabled=True, mock_llm_enabled=True),
            user_id=uuid4(),
            query="which couch",
            exclude_message_ids=exclude,
        )
    assert "past conversations" in block
    assert "blue couch" in block
    assert "not the full history" in block
    assert search.await_args.kwargs["exclude_message_ids"] == exclude


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
        patch("app.services.chat_history_rag.SessionLocal", _cm),
        patch(
            "app.services.chat_history_rag.embedding_gateway.embed_text",
            _embed,
        ),
        patch(
            "app.services.chat_history_rag.chunks_repo.replace_chunks",
            AsyncMock(),
        ) as replace_mock,
    ):
        count = await index_message(settings, user_id=uuid4(), message=message)

    assert count == 1
    assert open_count == 1
    assert max_live == 1
    replace_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_index_turn_messages_backfills_when_corpus_empty():
    settings = Settings(chat_history_rag_enabled=True, mock_llm_enabled=True)
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

    with (
        patch("app.services.chat_history_rag.SessionLocal", _session_cm()),
        patch(
            "app.services.chat_history_rag.chunks_repo.count_for_user",
            AsyncMock(return_value=0),
        ),
        patch(
            "app.services.chat_history_rag.messages_repo.get_by_id",
            AsyncMock(return_value=assistant),
        ),
        patch(
            "app.services.chat_history_rag.messages_repo.get_last_user",
            AsyncMock(return_value=user_msg),
        ),
        patch(
            "app.services.chat_history_rag.index_message",
            AsyncMock(return_value=1),
        ) as index_one,
        patch(
            "app.services.chat_history_rag.messages_repo.list_recent_for_user",
            AsyncMock(return_value=[user_msg, assistant, older]),
        ),
        patch(
            "app.services.chat_history_rag.chunks_repo.indexed_message_ids",
            AsyncMock(return_value=set()),
        ),
    ):
        count = await index_turn_messages(
            settings,
            user_id=user_id,
            chat_id=chat_id,
            assistant_message_id=assistant.id,
        )

    assert count == 3
    assert index_one.await_count == 3

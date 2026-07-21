from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.attachment_rag import chunk_text, retrieve_for_prompt


def _session_cm():
    @asynccontextmanager
    async def _cm(*_args, **_kwargs):
        yield MagicMock()

    return _cm


def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_text_single_chunk():
    assert chunk_text("hello world", chunk_chars=100) == ["hello world"]


def test_chunk_text_overlaps():
    text = "a" * 50 + "b" * 50 + "c" * 50
    chunks = chunk_text(text, chunk_chars=60, overlap=10)
    assert len(chunks) >= 2
    assert all(len(c) <= 60 for c in chunks)
    # Overlap means consecutive chunks share content
    assert chunks[0][-5:] in chunks[1] or chunks[0][-10:][:5] in chunks[1]


def test_chunk_text_terminates_when_overlap_meets_or_exceeds_chunk_size():
    """A misconfigured overlap >= chunk_chars must not spin forever — `start`
    has to strictly advance every iteration regardless of the configured
    overlap. This test itself is the regression check: it would hang the
    whole suite if the guard regressed."""
    text = "".join(chr(ord("a") + (i % 26)) for i in range(500))
    chunks = chunk_text(text, chunk_chars=60, overlap=60)
    # Bounded and non-degenerate: strictly fewer chunks than characters (a
    # stalled `start` would instead spin until something else killed the
    # process), and the final chunk actually reaches the end of the input —
    # proof `start` advanced all the way through rather than looping on the
    # same window forever.
    assert 0 < len(chunks) < len(text)
    assert chunks[-1].endswith(text[-1])


@pytest.mark.asyncio
async def test_retrieve_for_prompt_degrades_on_db_error_instead_of_raising():
    """BUG FIX: a pgvector/DB-level error in search_semantic used to have no
    catch anywhere in this call chain and would propagate up to fail the
    whole chat turn. RAG is best-effort context, same as memory/todos/
    projects — it must degrade to no-context instead."""
    settings = Settings(mock_llm_enabled=True)
    user_id = uuid4()
    chat_id = uuid4()

    with (
        patch("app.services.attachment_rag.SessionLocal", _session_cm()),
        patch(
            "app.services.attachment_rag.chunks_repo.has_chunks_for_chat",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.services.attachment_rag.embedding_gateway.embed_text",
            AsyncMock(return_value=[0.1] * 1536),
        ),
        patch(
            "app.services.attachment_rag.chunks_repo.search_semantic",
            AsyncMock(side_effect=RuntimeError("db exploded")),
        ),
        patch("app.services.attachment_rag.chunks_repo.EMBEDDING_DIM", 1536),
    ):
        block = await retrieve_for_prompt(
            settings=settings,
            user_id=user_id,
            chat_id=chat_id,
            query="what does the attached PDF say?",
        )

    assert block == ""


@pytest.mark.asyncio
async def test_retrieve_for_prompt_skips_embed_when_no_chunks():
    settings = Settings(mock_llm_enabled=True)
    embed_mock = AsyncMock(return_value=[0.1] * 1536)

    with (
        patch("app.services.attachment_rag.SessionLocal", _session_cm()),
        patch(
            "app.services.attachment_rag.chunks_repo.has_chunks_for_chat",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.services.attachment_rag.embedding_gateway.embed_text",
            embed_mock,
        ),
    ):
        block = await retrieve_for_prompt(
            settings=settings,
            user_id=uuid4(),
            chat_id=uuid4(),
            query="what does the attached PDF say?",
        )

    assert block == ""
    embed_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_retrieve_for_prompt_times_out_hung_embed():
    settings = Settings(mock_llm_enabled=True)

    async def _hang(_settings, _text):
        import asyncio

        await asyncio.sleep(10)
        return [0.1] * 1536

    with (
        patch("app.services.attachment_rag.SessionLocal", _session_cm()),
        patch(
            "app.services.attachment_rag.chunks_repo.has_chunks_for_chat",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.services.attachment_rag.embedding_gateway.embed_text",
            _hang,
        ),
        patch(
            "app.services.attachment_rag._RAG_EMBED_TIMEOUT_SECONDS",
            0.05,
        ),
    ):
        block = await retrieve_for_prompt(
            settings=settings,
            user_id=uuid4(),
            chat_id=uuid4(),
            query="what does the attached PDF say?",
        )

    assert block == ""

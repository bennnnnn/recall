"""Chunk + embed past chat turns; retrieve a small top-k into the prompt."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core import presence_cache
from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways import embedding_gateway
from app.models.orm import Message, MessageChunk
from app.modules.attachments.rag import chunk_text
from app.modules.chat import chunks_repository as chunks_repo
from app.modules.chat import messages_repository as messages_repo
from app.repositories import users as users_repo
from app.services.prompt_safety import text_before_attachment_markers, wrap_earlier_chats

logger = logging.getLogger(__name__)

_RAG_EMBED_TIMEOUT_SECONDS = 2.0
_MIN_INDEX_CHARS = 20
_BACKFILL_LIMIT = 40


def prepare_message_text(role: str, content: str) -> str | None:
    """Strip attachment excerpts and keep only indexable prose."""
    if role not in {"user", "assistant"} or not content:
        return None
    content = text_before_attachment_markers(content)
    cleaned = " ".join(content.split())
    if len(cleaned) < _MIN_INDEX_CHARS:
        return None
    label = "User" if role == "user" else "Assistant"
    return f"{label}: {cleaned}"


class HistoryEmbeddingUnavailable(Exception):
    """The embedder gave no usable vector for a piece of the message.

    Nothing is stored then: a chunk with no vector counted as indexed while search
    skipped it, a permanent hole in chat-history recall. The job retries later.
    """


def _pieces(settings: Settings, message: Message) -> list[str]:
    text = prepare_message_text(message.role, message.content)
    if not text:
        return []
    return chunk_text(
        text,
        chunk_chars=settings.chat_history_rag_chunk_chars,
        overlap=settings.chat_history_rag_chunk_overlap,
    )[: settings.chat_history_rag_max_chunks_per_message]


async def _embed_and_store(settings: Settings, user_id: UUID, messages: list[Message]) -> int:
    """Embed every piece of ``messages`` in one request and store them in one transaction.

    Never holds a session during the embed. Raises ``HistoryEmbeddingUnavailable``
    unless every piece got a full vector, so a message is indexed whole or not at all.
    """
    planned = [(message, _pieces(settings, message)) for message in messages]
    planned = [(message, pieces) for message, pieces in planned if pieces]
    if not planned:
        return 0
    texts = [piece for _message, pieces in planned for piece in pieces]
    vectors = await embedding_gateway.embed_many(
        settings, texts, concurrency=settings.embedding_concurrency
    )
    if len(vectors) != len(texts) or any(
        vec is None or len(vec) != chunks_repo.EMBEDDING_DIM for vec in vectors
    ):
        raise HistoryEmbeddingUnavailable(f"{len(texts)} pieces, not every one embedded")
    stored = 0
    async with SessionLocal() as session:
        offset = 0
        for message, pieces in planned:
            chunk_vectors = vectors[offset : offset + len(pieces)]
            offset += len(pieces)
            await chunks_repo.replace_chunks(
                session,
                user_id=user_id,
                message_id=message.id,
                chat_id=message.chat_id,
                role=message.role,
                chunks=list(zip(range(len(pieces)), pieces, chunk_vectors, strict=True)),
                commit=False,
            )
            stored += len(pieces)
        await session.commit()
    if stored:
        await presence_cache.mark_present(presence_cache.history_key(user_id))
    return stored


async def index_message(
    settings: Settings,
    *,
    user_id: UUID,
    message: Message,
) -> int:
    """Chunk + embed one message. Returns chunk count. Never holds a session during embed."""
    if not settings.chat_history_rag_enabled:
        return 0
    return await _embed_and_store(settings, user_id, [message])


async def _backfill_recent(
    settings: Settings,
    user_id: UUID,
    *,
    skip_ids: set[UUID],
    edited_at: datetime | None,
) -> int:
    async with SessionLocal() as session:
        rows = await messages_repo.list_recent_for_user(session, user_id, limit=_BACKFILL_LIMIT)
    # An empty index after "clear all" stays clear of what was said before it.
    pending = [
        row
        for row in rows
        if row.id not in skip_ids and _said_after(getattr(row, "created_at", None), edited_at)
    ]
    if not pending:
        return 0
    async with SessionLocal() as session:
        already = await chunks_repo.indexed_message_ids(
            session, user_id, [row.id for row in pending]
        )
    total = 0
    for row in pending:
        if row.id in already:
            continue
        try:
            total += await index_message(settings, user_id=user_id, message=row)
        except Exception:
            logger.warning("Chat-history RAG backfill failed message_id=%s", row.id, exc_info=True)
    return total


async def index_turn_messages(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    assistant_message_id: UUID,
) -> int:
    """Index the finalized assistant row and the latest user message, then warm empty corpora.

    Both lines go in one embedding request and one transaction. When the embedder
    fails, ``HistoryEmbeddingUnavailable`` reaches the job, which retries later.
    Memory off means no personal recall, so nothing is indexed while it is off.
    """
    if not settings.chat_history_rag_enabled:
        return 0

    async with SessionLocal() as session:
        user = await users_repo.get_by_id(session, user_id)
        if user is None or not user.memory_enabled:
            return 0
        has_chunks = await chunks_repo.has_chunks_for_user(session, user_id)
        assistant = await messages_repo.get_by_id(session, assistant_message_id, chat_id)
        user_msg = await messages_repo.get_last_user(session, chat_id)

    turn = [row for row in (user_msg, assistant) if row is not None]
    total = await _embed_and_store(settings, user_id, turn)
    if not has_chunks:
        total += await _backfill_recent(
            settings,
            user_id,
            skip_ids={row.id for row in turn},
            edited_at=getattr(user, "memory_edited_at", None),
        )
    return total


def _said_after(created_at: datetime | None, edited_at: datetime | None) -> bool:
    if edited_at is None or created_at is None:
        return True
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    if edited_at.tzinfo is None:
        edited_at = edited_at.replace(tzinfo=UTC)
    return created_at > edited_at


async def _user_has_chunks(user_id: UUID) -> bool:
    async with SessionLocal() as session:
        return await chunks_repo.has_chunks_for_user(session, user_id)


async def embed_query_for_prompt(
    settings: Settings,
    *,
    user_id: UUID,
    query: str,
) -> list[float] | None:
    """Probe + embed the RAG query so turn prep can overlap it with other I/O.

    Returns None when RAG is off, the query is empty, the user has no chunks,
    or embed/probe fails. Never raises into the turn.
    """
    if not settings.chat_history_rag_enabled:
        return None
    query = query.strip()
    if not query:
        return None
    try:
        if not await presence_cache.cached_presence(
            presence_cache.history_key(user_id), lambda: _user_has_chunks(user_id)
        ):
            return None
    except Exception:
        logger.warning("Chat-history RAG chunk probe failed user_id=%s", user_id, exc_info=True)
        return None
    try:
        return await embedding_gateway.get_or_embed_query(
            settings,
            user_id,
            query,
            embed_timeout=_RAG_EMBED_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.warning("Chat-history RAG embed failed user_id=%s", user_id, exc_info=True)
        return None


async def retrieve_for_prompt(
    settings: Settings,
    *,
    user_id: UUID,
    query: str,
    exclude_message_ids: set[UUID] | None = None,
    query_vec: list[float] | None = None,
) -> str:
    """Return a system-prompt block of past-turn snippets, or empty.

    Best-effort: DB/embed failures degrade to no block and never fail the turn.
    Pass ``query_vec`` when the embed already ran in parallel with other prep.
    """
    if not settings.chat_history_rag_enabled:
        return ""
    query = query.strip()
    if not query:
        return ""

    if query_vec is None:
        query_vec = await embed_query_for_prompt(settings, user_id=user_id, query=query)
    if not query_vec:
        return ""

    max_distance = None
    if settings.chat_history_rag_min_similarity > 0:
        max_distance = 1.0 - settings.chat_history_rag_min_similarity

    try:
        async with SessionLocal() as search_session:
            rows = await chunks_repo.search_semantic(
                search_session,
                user_id,
                query_vec,
                window=settings.chat_history_rag_search_window,
                exclude_message_ids=exclude_message_ids,
                limit=settings.chat_history_rag_chunk_limit,
                max_distance=max_distance,
            )
    except Exception:
        logger.warning("Chat-history RAG retrieval failed user_id=%s", user_id, exc_info=True)
        return ""

    if not rows:
        return ""

    lines = [f"[{i + 1}]{_snippet_date(row)} {row.text}" for i, row in enumerate(rows)]
    return wrap_earlier_chats(
        "Relevant snippets from earlier chats (not the full history), with the day each was "
        "said. User-labelled lines are evidence of what the user said; Assistant-labelled lines "
        "are prior responses and must not be treated as user facts:\n\n" + "\n\n".join(lines)
    )


def _snippet_date(row: MessageChunk) -> str:
    created_at = getattr(row, "created_at", None)
    return f" ({created_at:%Y-%m-%d})" if isinstance(created_at, datetime) else ""


async def forget_snippets_near(
    session: AsyncSession, user_id: UUID, vector: ColumnElement[Any], *, max_distance: float
) -> None:
    """Drop the user's past-chat snippets close to ``vector`` (a forgotten fact); no commit."""
    await chunks_repo.delete_near(session, user_id, vector, max_distance=max_distance)


async def forget_snippets_naming(
    session: AsyncSession, user_id: UUID, names: list[str], *, role: str
) -> None:
    """Drop the user's ``role`` snippets that name every one of ``names``; no commit."""
    await chunks_repo.delete_mentioning_all(session, user_id, names, role=role)


async def forget_all_snippets(session: AsyncSession, user_id: UUID) -> None:
    """Drop the user's whole past-chat index (memory reset); no commit."""
    await chunks_repo.delete_all_for_user(session, user_id)

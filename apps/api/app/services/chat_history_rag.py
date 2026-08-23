"""Chunk + embed past chat turns; retrieve a small top-k into the prompt."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways import embedding_gateway
from app.models.orm import Message, MessageChunk
from app.repositories import message_chunks as chunks_repo
from app.repositories import messages as messages_repo
from app.services.attachment_rag import chunk_text
from app.services.prompt_safety import text_before_attachment_markers, wrap_untrusted

logger = logging.getLogger(__name__)

_EMBED_CONCURRENCY = 8
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


async def _embed_pieces(
    settings: Settings,
    pieces: list[str],
) -> list[tuple[int, str, list[float] | None]]:
    sem = asyncio.Semaphore(_EMBED_CONCURRENCY)

    async def _one(index: int, piece: str) -> tuple[int, str, list[float] | None]:
        async with sem:
            vec = await embedding_gateway.embed_text(settings, piece)
        return index, piece, vec

    return list(await asyncio.gather(*(_one(i, piece) for i, piece in enumerate(pieces))))


async def index_message(
    settings: Settings,
    *,
    user_id: UUID,
    message: Message,
) -> int:
    """Chunk + embed one message. Returns chunk count. Never holds a session during embed."""
    if not settings.chat_history_rag_enabled:
        return 0
    text = prepare_message_text(message.role, message.content)
    if not text:
        return 0
    pieces = chunk_text(
        text,
        chunk_chars=settings.chat_history_rag_chunk_chars,
        overlap=settings.chat_history_rag_chunk_overlap,
    )[: settings.chat_history_rag_max_chunks_per_message]
    if not pieces:
        return 0
    embedded = await _embed_pieces(settings, pieces)
    async with SessionLocal() as session:
        await chunks_repo.replace_chunks(
            session,
            user_id=user_id,
            message_id=message.id,
            chat_id=message.chat_id,
            role=message.role,
            chunks=embedded,
        )
    return len(embedded)


async def _backfill_recent(settings: Settings, user_id: UUID, *, skip_ids: set[UUID]) -> int:
    async with SessionLocal() as session:
        rows = await messages_repo.list_recent_for_user(session, user_id, limit=_BACKFILL_LIMIT)
    pending = [row for row in rows if row.id not in skip_ids]
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
    """Index the finalized assistant row and the latest user message, then warm empty corpora."""
    if not settings.chat_history_rag_enabled:
        return 0

    async with SessionLocal() as session:
        existing = await chunks_repo.count_for_user(session, user_id)
        assistant = await messages_repo.get_by_id(session, assistant_message_id, chat_id)
        user_msg = await messages_repo.get_last_user(session, chat_id)

    indexed_ids: set[UUID] = set()
    total = 0
    for row in (user_msg, assistant):
        if row is None:
            continue
        try:
            count = await index_message(settings, user_id=user_id, message=row)
        except Exception:
            logger.warning("Chat-history RAG index failed message_id=%s", row.id, exc_info=True)
            continue
        if count:
            total += count
            indexed_ids.add(row.id)

    if existing == 0:
        total += await _backfill_recent(settings, user_id, skip_ids=indexed_ids)
    return total


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
        async with SessionLocal() as probe_session:
            if not await chunks_repo.has_chunks_for_user(probe_session, user_id):
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
                exclude_message_ids=exclude_message_ids,
                limit=settings.chat_history_rag_chunk_limit,
                max_distance=max_distance if len(query_vec) == chunks_repo.EMBEDDING_DIM else None,
            )
    except Exception:
        logger.warning("Chat-history RAG retrieval failed user_id=%s", user_id, exc_info=True)
        return ""

    if len(query_vec) != chunks_repo.EMBEDDING_DIM and rows:
        scored: list[tuple[float, MessageChunk]] = []
        for row in rows:
            stored = embedding_gateway.parse_embedding(row.embedding_json)
            if not stored:
                continue
            score = embedding_gateway.cosine_similarity(query_vec, stored)
            if score >= settings.chat_history_rag_min_similarity:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        rows = [item[1] for item in scored[: settings.chat_history_rag_chunk_limit]]

    if not rows:
        return ""

    lines = [f"[{i + 1}] {row.text}" for i, row in enumerate(rows)]
    return wrap_untrusted(
        "past conversations",
        "Relevant snippets from earlier chats (not the full history):\n\n" + "\n\n".join(lines),
        first_party=True,
    )

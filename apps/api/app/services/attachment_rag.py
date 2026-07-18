"""Chunk + embed attachment text; retrieve into chat prompts (pgvector RAG)."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways import embedding_gateway
from app.gateways.storage_gateway import get_storage_gateway
from app.models.orm import Attachment, AttachmentChunk
from app.repositories import attachment_chunks as chunks_repo
from app.repositories import attachments as attachments_repo
from app.services import attachment_content as attachment_content_service
from app.services.prompt_safety import wrap_untrusted

logger = logging.getLogger(__name__)

# Cap concurrent embedding calls so a large PDF doesn't stampede the provider.
_EMBED_CONCURRENCY = 8


def chunk_text(text: str, *, chunk_chars: int = 900, overlap: int = 120) -> list[str]:
    # Guard against a misconfigured overlap >= chunk_chars: `start` would
    # never advance past the previous chunk's start, spinning forever on a
    # long document (pure CPU loop in the background indexing worker, no
    # await to time out on). Shipped defaults (900/120) are safe; this is a
    # footgun guard for a bad config value, not a correctness fix for today.
    if overlap >= chunk_chars:
        overlap = max(0, chunk_chars - 1)
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    if len(cleaned) <= chunk_chars:
        return [cleaned]
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_chars)
        chunks.append(cleaned[start:end])
        if end >= len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def is_indexable_attachment(row: Attachment) -> bool:
    return (
        not attachment_content_service.is_image_content_type(row.content_type)
        and row.content_type in attachment_content_service.EXTRACTABLE_CONTENT_TYPES
    )


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


async def index_attachment(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    attachment_id: UUID,
    chat_id: UUID | None = None,
) -> int:
    """Extract, chunk, embed, and store chunks for one attachment. Returns chunk count."""
    if not settings.attachment_rag_enabled:
        return 0

    row = await attachments_repo.get_by_id(session, attachment_id, user_id)
    if row is None or not is_indexable_attachment(row):
        return 0

    gateway = get_storage_gateway(settings)
    data = await attachment_content_service.read_attachment_bytes(gateway, row.storage_key)
    if not data:
        return 0

    text = await attachment_content_service.extract_text_from_bytes_async(
        row.content_type, data, settings
    )
    if not text:
        return 0

    pieces = chunk_text(
        text,
        chunk_chars=settings.attachment_rag_chunk_chars,
        overlap=settings.attachment_rag_chunk_overlap,
    )[: settings.attachment_rag_max_chunks_per_file]
    if not pieces:
        return 0

    embedded = await _embed_pieces(settings, pieces)

    await chunks_repo.replace_chunks(
        session,
        user_id=row.user_id,
        attachment_id=row.id,
        chat_id=chat_id,
        chunks=embedded,
    )
    return len(embedded)


async def retrieve_for_prompt(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    query: str,
) -> str:
    """Return a system-prompt block of top attachment chunks for this chat, or empty."""
    if not settings.attachment_rag_enabled:
        return ""
    query = query.strip()
    if not query:
        return ""

    query_vec = await embedding_gateway.embed_text(settings, query)
    if not query_vec:
        return ""

    max_distance = None
    if settings.attachment_rag_min_similarity > 0:
        max_distance = 1.0 - settings.attachment_rag_min_similarity

    # BUG FIX (was silent): a DB/pgvector-level error here (unlike an
    # embedding-gateway failure, already handled above via the empty-vector
    # check) had no catch anywhere in this call chain, so it propagated all
    # the way up and failed the whole chat turn instead of just proceeding
    # without attachment context — RAG is best-effort background context,
    # same as memory/todos/projects, and must degrade the same way.
    try:
        rows = await chunks_repo.search_semantic(
            session,
            user_id,
            query_vec,
            chat_id=chat_id,
            limit=settings.attachment_rag_chunk_limit,
            max_distance=max_distance if len(query_vec) == chunks_repo.EMBEDDING_DIM else None,
        )
    except Exception:
        logger.warning("Attachment RAG retrieval failed for chat_id=%s", chat_id, exc_info=True)
        return ""

    if len(query_vec) != chunks_repo.EMBEDDING_DIM and rows:
        scored: list[tuple[float, AttachmentChunk]] = []
        for row in rows:
            stored = embedding_gateway.parse_embedding(row.embedding_json)
            if not stored:
                continue
            score = embedding_gateway.cosine_similarity(query_vec, stored)
            if score >= settings.attachment_rag_min_similarity:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        rows = [item[1] for item in scored[: settings.attachment_rag_chunk_limit]]

    if not rows:
        return ""

    lines = [f"[{i + 1}] {row.text}" for i, row in enumerate(rows)]
    return wrap_untrusted("attached documents", "\n\n".join(lines))

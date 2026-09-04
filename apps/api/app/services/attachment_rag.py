"""Chunk + embed attachment text; retrieve into chat prompts (pgvector RAG)."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways import embedding_gateway
from app.gateways.storage_gateway import get_storage_gateway
from app.models.orm import Attachment, AttachmentChunk
from app.repositories import attachment_chunks as chunks_repo
from app.repositories import attachments as attachments_repo
from app.services import attachment_content as attachment_content_service
from app.services.prompt_safety import wrap_untrusted

logger = logging.getLogger(__name__)

_RAG_COVERAGE_PREFIX = (
    f"Indexed file text covers at most the first "
    f"{attachment_content_service.PDF_INDEX_MAX_PAGES} PDF pages and the first "
    f"{attachment_content_service.MAX_INDEX_EXTRACT_CHARS} characters. "
    "The configured chunk budget can reduce coverage further. "
    "A retrieval miss is not proof the answer is absent from unread pages. "
    "Do not invent from outside these excerpts.\n\n"
)
_RAG_MISS_NOTE = (
    "Indexed excerpts were searched but none matched this question. "
    "That is not proof the answer is absent from unread pages or the rest of "
    "the file. Do not invent from outside the file. If you cannot ground an "
    "answer in the excerpts, say so."
)

# Cap concurrent embedding calls so a large PDF doesn't stampede the provider.
_EMBED_CONCURRENCY = 8
# Foreground TTFT path — match memory's live-embed budget.
_RAG_EMBED_TIMEOUT_SECONDS = 2.0


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


class AttachmentIndexError(Exception):
    """Raised when attachment indexing fails transiently (R2 read, extraction, embedding).

    Distinguished from a legitimate "nothing to index" (image file, empty doc)
    which returns 0. A raised exception lets the worker retry (3 attempts)
    instead of the dedupe key blocking re-enqueue for 24h.
    """


async def index_attachment(
    settings: Settings,
    *,
    user_id: UUID,
    attachment_id: UUID,
    chat_id: UUID | None = None,
) -> int:
    """Extract, chunk, embed, and store chunks for one attachment. Returns chunk count.

    Short-lived sessions around the row load and ``replace_chunks`` only — the
    download / extract / embed pipeline runs with no pool checkout held, same
    discipline as ``retrieve_for_prompt``.

    Raises :class:`AttachmentIndexError` for transient failures (R2 read,
    extraction timeout, all-embeddings-failed) so the worker retries instead of
    silently succeeding and blocking re-indexing via the dedupe key.
    """
    if not settings.attachment_rag_enabled:
        return 0

    async with SessionLocal() as session:
        row = await attachments_repo.get_by_id(session, attachment_id, user_id)
        if row is None or row.verified_at is None or not is_indexable_attachment(row):
            return 0
        storage_key = row.storage_key
        content_type = row.content_type
        owner_id = row.user_id
        row_id = row.id

    gateway = get_storage_gateway(settings)
    data = await attachment_content_service.read_attachment_bytes(gateway, storage_key)
    if not data:
        raise AttachmentIndexError(f"Failed to read attachment bytes for {attachment_id}")

    text = await attachment_content_service.extract_text_from_bytes_async(
        content_type,
        data,
        settings,
        max_chars=attachment_content_service.MAX_INDEX_EXTRACT_CHARS,
    )
    if not text:
        # Legitimate "no text" — scanned PDF with no OCR, or genuinely empty doc.
        # Not a transient failure; don't raise.
        return 0

    pieces = chunk_text(
        text,
        chunk_chars=settings.attachment_rag_chunk_chars,
        overlap=settings.attachment_rag_chunk_overlap,
    )[: settings.attachment_rag_max_chunks_per_file]
    if not pieces:
        return 0

    embedded = await _embed_pieces(settings, pieces)

    # Filter out chunks with null embeddings. If ALL failed, raise so the
    # worker retries — storing all-null chunks creates dead rows that
    # has_chunks_for_chat won't find (it requires embedding IS NOT NULL).
    successful: list[tuple[int, str, list[float] | None]] = [
        (idx, piece, vec) for idx, piece, vec in embedded if vec is not None
    ]
    failed_count = len(embedded) - len(successful)
    if failed_count > 0:
        logger.warning(
            "Attachment %s: %d/%d chunk embeddings failed",
            attachment_id,
            failed_count,
            len(embedded),
        )
    if not successful:
        raise AttachmentIndexError(
            f"All {len(embedded)} chunk embeddings failed for {attachment_id}"
        )

    async with SessionLocal() as session:
        stored = await chunks_repo.replace_chunks(
            session,
            user_id=owner_id,
            attachment_id=row_id,
            chat_id=chat_id,
            chunks=successful,
        )
    return len(successful) if stored else 0


async def retrieve_for_prompt(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    query: str,
) -> str:
    """Return a system-prompt block of top attachment chunks for this chat, or empty.

    Opens short-lived DB sessions around probe/search only — the embedding HTTP
    call runs with no pool checkout held, so a hung provider cannot stall TTFT
    via connection exhaustion.
    """
    if not settings.attachment_rag_enabled:
        return ""
    query = query.strip()
    if not query:
        return ""

    # Skip paid embed when this chat has no indexed chunks yet.
    try:
        async with SessionLocal() as probe_session:
            if not await chunks_repo.has_chunks_for_chat(probe_session, user_id, chat_id):
                return ""
    except Exception:
        logger.warning("Attachment RAG chunk probe failed for chat_id=%s", chat_id, exc_info=True)
        return ""

    try:
        query_vec = await embedding_gateway.get_or_embed_query(
            settings,
            user_id,
            query,
            embed_timeout=_RAG_EMBED_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.warning("Attachment RAG embed failed for chat_id=%s", chat_id, exc_info=True)
        return ""
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
    filenames: dict[UUID, str] = {}
    try:
        async with SessionLocal() as search_session:
            rows = await chunks_repo.search_semantic(
                search_session,
                user_id,
                query_vec,
                chat_id=chat_id,
                limit=settings.attachment_rag_chunk_limit,
                max_distance=max_distance if len(query_vec) == chunks_repo.EMBEDDING_DIM else None,
            )
            att_ids = list({row.attachment_id for row in rows})
            if att_ids:
                loaded = await attachments_repo.get_by_ids(search_session, att_ids, user_id)
                filenames = {
                    row.id: (row.original_filename or "").strip() or "attachment" for row in loaded
                }
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
        return wrap_untrusted("attached documents", _RAG_MISS_NOTE)

    lines = []
    for i, row in enumerate(rows):
        name = filenames.get(row.attachment_id) or "attachment"
        lines.append(f"[{i + 1}] ({name}) {row.text}")
    return wrap_untrusted("attached documents", _RAG_COVERAGE_PREFIX + "\n\n".join(lines))

"""Unprocessed user lines for a memory extraction pass.

Each job must see every user message since the previous successful pass, not
only the current turn. Redis stores a per-chat cursor; the payload transcript
is the fallback when Redis or Neon is unavailable.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.repositories import messages as messages_repo
from app.services.memory.text import memory_extract_user_text
from app.services.text_normalize import cap_text_head_tail

logger = logging.getLogger(__name__)

_MEMORY_TRANSCRIPT_MAX_CHARS = 4000
_MEMORY_EXTRACT_BACKLOG = 20
_CURSOR_TTL_SECONDS = 60 * 60 * 24 * 60


def _cursor_key(user_id: UUID, chat_id: UUID) -> str:
    return f"memory:extract_cursor:{user_id}:{chat_id}"


def parse_extract_cursor(raw: str | None) -> tuple[datetime | None, UUID | None]:
    if not raw:
        return None, None
    stamp, sep, id_part = raw.partition("|")
    if not sep or not id_part:
        return None, None
    try:
        return datetime.fromisoformat(stamp), UUID(id_part)
    except ValueError:
        return None, None


def format_extract_cursor(created_at: datetime, message_id: UUID) -> str:
    return f"{created_at.isoformat()}|{message_id}"


def format_user_memory_transcript(user_texts: list[str]) -> str:
    lines: list[str] = []
    for raw in user_texts:
        cleaned = memory_extract_user_text(raw)
        if cleaned:
            lines.append(f"User: {cleaned}")
    return "\n".join(lines)


async def expand_memory_extract_transcript(
    session: AsyncSession,
    *,
    user_id: UUID,
    chat_id: UUID,
    fallback_transcript: str,
) -> tuple[str, str | None]:
    """Return ``(transcript, cursor_to_stamp_or_none)``.

    Cursor is stamped by the caller only after the LLM pass succeeds.
    """
    after_created_at: datetime | None = None
    after_id: UUID | None = None
    try:
        raw = await get_redis_client().get(_cursor_key(user_id, chat_id))
        if isinstance(raw, bytes):
            raw = raw.decode()
        after_created_at, after_id = parse_extract_cursor(raw if isinstance(raw, str) else None)
    except Exception:
        logger.debug("memory extract cursor read failed chat_id=%s", chat_id, exc_info=True)

    try:
        rows = await messages_repo.list_user_contents_since(
            session,
            chat_id,
            after_created_at=after_created_at,
            after_id=after_id,
            limit=_MEMORY_EXTRACT_BACKLOG,
        )
    except Exception:
        logger.debug("memory extract backlog list failed chat_id=%s", chat_id, exc_info=True)
        return cap_text_head_tail(fallback_transcript, _MEMORY_TRANSCRIPT_MAX_CHARS), None

    texts = [row.content for row in rows]
    built = format_user_memory_transcript(texts)
    if not built:
        built = fallback_transcript
    newest_cursor: str | None = None
    if rows:
        last = rows[-1]
        newest_cursor = format_extract_cursor(last.created_at, last.id)
    return cap_text_head_tail(built, _MEMORY_TRANSCRIPT_MAX_CHARS), newest_cursor


async def stamp_extract_cursor(user_id: UUID, chat_id: UUID, cursor: str) -> None:
    try:
        await get_redis_client().set(
            _cursor_key(user_id, chat_id),
            cursor,
            ex=_CURSOR_TTL_SECONDS,
        )
    except Exception:
        logger.debug("memory extract cursor write failed chat_id=%s", chat_id, exc_info=True)

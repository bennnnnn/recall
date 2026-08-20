import asyncio
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    Text,
    exists,
    func,
    literal,
    null,
    or_,
    select,
    union_all,
)
from sqlalchemy import cast as sql_cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models.orm import Chat, Message


def _trgm_match(column: Any, query: str) -> ColumnElement[bool]:
    """pg_trgm `%` operator — uses GIN trigram indexes on title/content."""
    return cast(ColumnElement[bool], column.op("%")(query))


async def search_conversations(
    session: AsyncSession, user_id: UUID, query: str, limit: int = 20, offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    """Search chat titles and message bodies as one recency-ordered timeline.

    Title and message hits are unioned, then offset/limit apply once. ``total``
    is the union count (stable across pages), not a page-local title set.
    Title-only rows omit chats that already have a matching message.
    """
    q = query.strip()
    if not q:
        return [], 0

    pattern = f"%{q}%"
    msg_where = (
        Message.user_id == user_id,
        or_(_trgm_match(Message.content, q), Message.content.ilike(pattern)),
    )
    title_match = or_(_trgm_match(Chat.title, q), Chat.title.ilike(pattern))
    message_hit = exists(select(1).where(Message.chat_id == Chat.id, *msg_where))

    title_stmt = select(
        literal("title").label("match_type"),
        sql_cast(null(), Message.id.type).label("message_id"),
        Chat.id.label("chat_id"),
        Chat.title.label("chat_title"),
        sql_cast(Chat.title, Text).label("content"),
        literal("chat").label("role"),
        func.coalesce(Chat.updated_at, Chat.created_at).label("created_at"),
    ).where(
        Chat.user_id == user_id,
        Chat.archived.is_(False),
        Chat.title.isnot(None),
        Chat.title != "",
        title_match,
        ~message_hit,
    )
    msg_stmt = (
        select(
            literal("message").label("match_type"),
            Message.id.label("message_id"),
            Chat.id.label("chat_id"),
            Chat.title.label("chat_title"),
            Message.content.label("content"),
            Message.role.label("role"),
            Message.created_at.label("created_at"),
        )
        .join(Chat, Message.chat_id == Chat.id)
        .where(Chat.archived.is_(False), *msg_where)
    )
    combined = union_all(msg_stmt, title_stmt).subquery("search_hits")
    count_stmt = select(func.count()).select_from(combined)
    page_stmt = select(combined).order_by(combined.c.created_at.desc()).offset(offset).limit(limit)

    async def _count_hits() -> int:
        async with SessionLocal() as extra:
            result = await extra.execute(count_stmt)
            return result.scalar_one()

    total, page_result = await asyncio.gather(_count_hits(), session.execute(page_stmt))

    results: list[dict[str, Any]] = []
    for row in page_result.all():
        raw = row.content or ""
        content = _snippet(raw, q, 120) if row.match_type == "message" else raw
        created = row.created_at or datetime.now(UTC)
        results.append(
            {
                "match_type": row.match_type,
                "message_id": row.message_id,
                "chat_id": row.chat_id,
                "chat_title": row.chat_title,
                "content": content,
                "role": row.role,
                "created_at": created,
            }
        )
    return results, total


# Backwards-compatible alias for tests/imports that still reference this name.
search_messages = search_conversations


def _snippet(content: str, query: str, max_len: int = 120) -> str:
    """Extract a short snippet around the first match of query."""
    idx = content.lower().find(query.lower())
    if idx == -1:
        return content[:max_len]
    start = max(0, idx - 40)
    end = min(len(content), idx + len(query) + 80)
    snippet = content[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(content):
        snippet += "…"
    return snippet

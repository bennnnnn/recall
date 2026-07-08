import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models.orm import Chat, Message

TITLE_MATCH_LIMIT = 50


def _trgm_match(column, query: str):
    """pg_trgm `%` operator — uses GIN trigram indexes on title/content."""
    return column.op("%")(query)


async def search_conversations(
    session: AsyncSession, user_id: UUID, query: str, limit: int = 20, offset: int = 0
) -> tuple[list[dict], int]:
    """Search chat titles and message bodies, merged by recency."""
    q = query.strip()
    if not q:
        return [], 0

    pattern = f"%{q}%"
    msg_where = (
        Message.user_id == user_id,
        or_(_trgm_match(Message.content, q), Message.content.ilike(pattern)),
    )

    msg_count_stmt = (
        select(func.count())
        .select_from(Message)
        .join(Chat, Message.chat_id == Chat.id)
        .where(*msg_where)
    )
    title_stmt = (
        select(Chat)
        .where(
            Chat.user_id == user_id,
            Chat.title.isnot(None),
            Chat.title != "",
            or_(_trgm_match(Chat.title, q), Chat.title.ilike(pattern)),
        )
        .order_by(Chat.updated_at.desc())
        .limit(TITLE_MATCH_LIMIT)
    )
    msg_chat_ids_stmt = select(Message.chat_id.distinct()).where(*msg_where)
    msg_stmt = (
        select(
            Message.id,
            Message.content,
            Message.role,
            Message.created_at,
            Chat.id.label("chat_id"),
            Chat.title.label("chat_title"),
        )
        .join(Chat, Message.chat_id == Chat.id)
        .where(*msg_where)
        .order_by(Message.created_at.desc())
        .limit(max(limit + offset, limit))
    )

    async def _count_messages() -> int:
        async with SessionLocal() as s:
            result = await s.execute(msg_count_stmt)
            return result.scalar_one()

    async def _title_matches() -> list[Chat]:
        async with SessionLocal() as s:
            result = await s.execute(title_stmt)
            return list(result.scalars().all())

    async def _message_chat_ids() -> set:
        async with SessionLocal() as s:
            result = await s.scalars(msg_chat_ids_stmt)
            return set(result.all())

    message_total, title_chats, message_chat_ids_set, msg_rows_result = await asyncio.gather(
        _count_messages(), _title_matches(), _message_chat_ids(), session.execute(msg_stmt)
    )
    msg_rows = msg_rows_result.all()

    title_only = [chat for chat in title_chats if chat.id not in message_chat_ids_set]
    total = message_total + len(title_only)

    results: list[dict] = []
    for row in msg_rows:
        results.append(
            {
                "match_type": "message",
                "message_id": row.id,
                "chat_id": row.chat_id,
                "chat_title": row.chat_title,
                "content": _snippet(row.content, q, 120),
                "role": row.role,
                "created_at": row.created_at,
            }
        )

    for chat in title_only:
        results.append(
            {
                "match_type": "title",
                "message_id": None,
                "chat_id": chat.id,
                "chat_title": chat.title,
                "content": chat.title or "",
                "role": "chat",
                "created_at": chat.updated_at or chat.created_at or datetime.now(UTC),
            }
        )

    results.sort(key=lambda item: item["created_at"], reverse=True)
    return results[offset : offset + limit], total


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

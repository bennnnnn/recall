from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Message, Chat


async def search_messages(
    session: AsyncSession, user_id: UUID, query: str, limit: int = 20, offset: int = 0
) -> tuple[list[dict], int]:
    """Search messages by content using ILIKE, returning snippet + chat context.

    Returns (results, total_matching_count).
    """
    pattern = f"%{query}%"
    base_where = (
        Message.user_id == user_id,
        Message.content.ilike(pattern),
    )

    # Count total matches (independent of limit).
    count_stmt = (
        select(func.count())
        .select_from(Message)
        .join(Chat, Message.chat_id == Chat.id)
        .where(*base_where)
    )
    total: int = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(
            Message.id,
            Message.content,
            Message.role,
            Message.created_at,
            Chat.id.label("chat_id"),
            Chat.title.label("chat_title"),
        )
        .join(Chat, Message.chat_id == Chat.id)
        .where(*base_where)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [
        {
            "message_id": row.id,
            "chat_id": row.chat_id,
            "chat_title": row.chat_title,
            "content": _snippet(row.content, query, 120),
            "role": row.role,
            "created_at": row.created_at,
        }
        for row in rows
    ], total


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

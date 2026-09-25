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
    true,
    union_all,
)
from sqlalchemy import cast as sql_cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Chat, Message


def _trgm_match(column: Any, query: str) -> ColumnElement[bool]:
    """pg_trgm `%` operator — uses GIN trigram indexes on title/content."""
    return cast(ColumnElement[bool], column.op("%")(query))


async def search_conversations(
    session: AsyncSession, user_id: UUID, query: str, limit: int = 20, offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    """Search chat titles and message bodies as one recency-ordered timeline.

    Title and message hits are unioned, then offset/limit apply once. ``total``
    counts that same database snapshot, including when the page is empty.
    Title-only rows omit chats that already have a matching message.
    """
    q = query.strip()
    if not q:
        return [], 0

    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    msg_where = (
        Message.user_id == user_id,
        or_(_trgm_match(Message.content, q), Message.content.ilike(pattern, escape="\\")),
    )
    title_match = or_(_trgm_match(Chat.title, q), Chat.title.ilike(pattern, escape="\\"))
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
        .where(Chat.user_id == user_id, Chat.archived.is_(False), *msg_where)
    )
    combined = union_all(msg_stmt, title_stmt).cte("search_hits")
    count = select(func.count().label("total")).select_from(combined).subquery("hit_count")
    page = (
        select(combined)
        .order_by(
            combined.c.created_at.desc(), combined.c.chat_id.desc(), combined.c.message_id.desc()
        )
        .offset(offset)
        .limit(limit)
        .subquery("page_hits")
    )
    # The aggregate always yields one row. Its outer join retains total for an
    # empty/out-of-range page while keeping the page and count in one snapshot.
    stmt = (
        select(page, count.c.total)
        .select_from(count.outerjoin(page, true()))
        .order_by(page.c.created_at.desc(), page.c.chat_id.desc(), page.c.message_id.desc())
    )
    rows = (await session.execute(stmt)).all()
    total = rows[0].total if rows else 0

    results: list[dict[str, Any]] = []
    for row in rows:
        if row.match_type is None:
            continue
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

"""The nearest chunks among a user's newest: one search for documents and past chats.

A global vector index filters by user (and chat) only after its scan, so it found nothing
for most users. Both chunk tables are ranked exactly instead, over a bounded window of the
newest rows, read through their ``(user_id, created_at)`` index; the LIMIT keeps the
planner from flattening the window into the outer query.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.vectors import EMBEDDING_DIM


async def nearest_in_window(
    session: AsyncSession,
    table: Any,
    query_embedding: list[float],
    *,
    filters: list[ColumnElement[bool]],
    window: int,
    limit: int,
    max_distance: float | None,
) -> list[Any]:
    """The ``limit`` embedded rows of ``table`` nearest ``query_embedding`` (cosine) among
    the newest ``window`` that match ``filters``; none for a vector of the wrong width.

    ``table`` is a chunk model (its ``id``, ``embedding`` and ``created_at``), passed by
    its owning module: shared persistence names no product module's table.
    """
    if len(query_embedding) != EMBEDDING_DIM:
        return []
    newest = (
        select(table.id, table.embedding)
        .where(table.embedding.isnot(None), *filters)
        .order_by(table.created_at.desc())
        .limit(window)
        .subquery("newest")
    )
    distance = newest.c.embedding.cosine_distance(query_embedding)
    stmt = select(table).join(newest, newest.c.id == table.id)
    if max_distance is not None:
        stmt = stmt.where(distance <= max_distance)
    result = await session.execute(stmt.order_by(distance).limit(limit))
    return list(result.scalars().all())

"""Conversation search — service façade over the search repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import search as search_repo


async def search_conversations(
    session: AsyncSession,
    user_id: UUID,
    *,
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    return await search_repo.search_conversations(
        session, user_id, query=query, limit=limit, offset=offset
    )

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways import embedding_gateway
from app.models.orm import Memory
from app.modules.home import service as home_service
from app.modules.memory import repository as memories_repo

logger = logging.getLogger(__name__)


async def _invalidate_caches(seams: Any, user_id: UUID) -> None:
    await seams.invalidate_memory_block(user_id)
    await home_service.invalidate_home_cache(user_id)


@asynccontextmanager
async def _write_locked(seams: Any, user_id: UUID) -> AsyncIterator[None]:
    """Hold the user's memory write lock for the block (busy: ``MemoryWriteLockBusyError``)."""
    lock_token = await seams._acquire_memory_write_lock_or_raise(user_id)
    try:
        yield
    finally:
        await seams.release_memory_write_lock(user_id, lock_token)


async def _commit_hand_delete[T: int](
    seams: Any,
    session: AsyncSession,
    user_id: UUID,
    delete: Callable[[], Awaitable[T]],
) -> T:
    """One hand delete as one transaction: delete, stamp the edit, commit; then drop caches.

    Stamping ``memory_edited_at`` in the same commit keeps the history scan from
    restoring what the user removed. A failure rolls the whole unit back.
    """
    try:
        removed = await delete()
        if removed:
            await memories_repo.note_manual_edit(session, user_id)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    if removed:
        await _invalidate_caches(seams, user_id)
    return removed


async def update_memory(
    seams: Any,
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
    memory_id: UUID,
    text: str | None,
    *,
    status: str | None = None,
) -> Memory | None:
    clean: str | None = None
    if text is not None:
        clean = seams.normalize_memory_text(seams.strip_memory_as_of(text))
        if not clean:
            raise seams.MemoryEmptyTextError()
    if clean is None and status is None:
        raise seams.MemoryEmptyTextError()
    async with _write_locked(seams, user_id):
        memory = await memories_repo.get_by_id(session, user_id, memory_id)
        if memory is None:
            return None
        new_vec: list[float] | None = None
        if clean is not None:
            # End the read before the embedding call (a provider round trip); the write
            # lock keeps the row as read until the writes below.
            await session.commit()
            try:
                new_vec = await embedding_gateway.embed_text(settings, clean)
            except Exception:
                logger.warning("Memory re-embed on edit failed", exc_info=True)
        updated: Memory | None = memory
        try:
            if status is not None:
                updated = await memories_repo.update_status(
                    session, user_id, memory_id, status, commit=False
                )
                if updated is None:
                    return None
            if clean is not None:
                if new_vec is not None:
                    updated = await memories_repo.update_text_and_embedding(
                        session,
                        user_id,
                        memory_id,
                        clean,
                        new_vec,
                        embedding_text_hash=seams.embedding_text_hash(clean),
                        commit=False,
                    )
                else:
                    updated = await memories_repo.update_text(
                        session,
                        user_id,
                        memory_id,
                        clean,
                        commit=False,
                    )
            if updated is not None:
                await memories_repo.note_manual_edit(session, user_id)
                await session.commit()
                await session.refresh(updated)
        except Exception:
            await session.rollback()
            raise
        if updated is not None:
            await _invalidate_caches(seams, user_id)
        return updated


async def delete_memory(
    seams: Any,
    session: AsyncSession,
    user_id: UUID,
    memory_id: UUID,
) -> bool:
    async with _write_locked(seams, user_id):
        return await _commit_hand_delete(
            seams,
            session,
            user_id,
            lambda: memories_repo.delete_by_id(session, user_id, memory_id, commit=False),
        )


async def delete_memory_document(
    seams: Any,
    session: AsyncSession,
    user_id: UUID,
    topic: str,
) -> bool:
    """Delete every fact in one document (and an area's title row)."""
    async with _write_locked(seams, user_id):
        removed = await _commit_hand_delete(
            seams,
            session,
            user_id,
            lambda: memories_repo.delete_topic(session, user_id, topic, commit=False),
        )
    return removed > 0


async def delete_all_memories(seams: Any, session: AsyncSession, user_id: UUID) -> int:
    async with _write_locked(seams, user_id):
        return await _commit_hand_delete(
            seams,
            session,
            user_id,
            lambda: memories_repo.delete_all_for_user(session, user_id, commit=False),
        )

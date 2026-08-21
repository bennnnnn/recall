import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Memory

logger = logging.getLogger(__name__)


async def delete_memory_fact(
    seams: Any,
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
    memory_id: UUID,
    fact_index: int,
    *,
    expected_text: str | None = None,
) -> bool:
    from app.gateways import embedding_gateway
    from app.repositories import memories as memories_repo

    lock_token = await seams._acquire_memory_write_lock_or_raise(user_id)
    try:
        memory = await memories_repo.get_by_id(session, user_id, memory_id)
        if memory is None:
            return False
        facts = seams.split_memory_facts(memory.text)
        target_index = fact_index
        if expected_text is not None:
            normalized_expected = seams.normalize_memory_text(expected_text).lower()
            matches = [
                index
                for index, fact in enumerate(facts)
                if seams.normalize_memory_text(fact).lower() == normalized_expected
            ]
            if not matches:
                return False
            target_index = fact_index if fact_index in matches else matches[0]
        if target_index < 0 or target_index >= len(facts):
            return False
        facts.pop(target_index)
        if not facts:
            try:
                deleted = await memories_repo.delete_by_id(
                    session,
                    user_id,
                    memory_id,
                    commit=False,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            if deleted:
                await seams.invalidate_memory_block(user_id)
            return deleted

        new_text = seams.join_memory_facts(facts)
        try:
            new_vec = await embedding_gateway.embed_text(settings, new_text)
        except Exception:
            logger.debug("Memory re-embed on fact delete failed", exc_info=True)
            new_vec = None
        try:
            if new_vec is not None:
                updated = await memories_repo.update_text_and_embedding(
                    session,
                    user_id,
                    memory_id,
                    new_text,
                    new_vec,
                    embedding_gateway.serialize_embedding(new_vec),
                    commit=False,
                )
            else:
                updated = await memories_repo.update_text(
                    session,
                    user_id,
                    memory_id,
                    new_text,
                    commit=False,
                )
            if updated is not None:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
        if updated is not None:
            await seams.invalidate_memory_block(user_id)
            return True
        return False
    finally:
        await seams.release_memory_write_lock(user_id, lock_token)


async def update_memory(
    seams: Any,
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
    memory_id: UUID,
    text: str,
) -> Memory | None:
    from app.gateways import embedding_gateway
    from app.repositories import memories as memories_repo

    clean = seams.normalize_memory_text(text)
    if not clean:
        raise seams.MemoryEmptyTextError()
    stamped = seams.stamp_memory_as_of(clean)
    lock_token = await seams._acquire_memory_write_lock_or_raise(user_id)
    try:
        memory = await memories_repo.get_by_id(session, user_id, memory_id)
        if memory is None:
            return None
        try:
            new_vec = await embedding_gateway.embed_text(settings, stamped)
        except Exception:
            logger.debug("Memory re-embed on edit failed", exc_info=True)
            new_vec = None
        try:
            if new_vec is not None:
                updated = await memories_repo.update_text_and_embedding(
                    session,
                    user_id,
                    memory_id,
                    stamped,
                    new_vec,
                    embedding_gateway.serialize_embedding(new_vec),
                    embedding_text_hash=seams.embedding_text_hash(stamped),
                    commit=False,
                )
            else:
                updated = await memories_repo.update_text(
                    session,
                    user_id,
                    memory_id,
                    stamped,
                    commit=False,
                )
            if updated is not None:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
        if updated is not None:
            await seams.invalidate_memory_block(user_id)
        return updated
    finally:
        await seams.release_memory_write_lock(user_id, lock_token)


async def delete_memory(
    seams: Any,
    session: AsyncSession,
    user_id: UUID,
    memory_id: UUID,
) -> bool:
    from app.repositories import memories as memories_repo

    lock_token = await seams._acquire_memory_write_lock_or_raise(user_id)
    try:
        try:
            deleted = await memories_repo.delete_by_id(
                session,
                user_id,
                memory_id,
                commit=False,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        if deleted:
            await seams.invalidate_memory_block(user_id)
        return deleted
    finally:
        await seams.release_memory_write_lock(user_id, lock_token)


async def delete_memory_section(
    seams: Any,
    session: AsyncSession,
    user_id: UUID,
    memory_type: str,
) -> bool:
    from app.repositories import memories as memories_repo

    lock_token = await seams._acquire_memory_write_lock_or_raise(user_id)
    try:
        try:
            removed = await memories_repo.delete_by_type(
                session,
                user_id,
                memory_type,
                commit=False,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        if removed:
            await seams.invalidate_memory_block(user_id)
        return removed > 0
    finally:
        await seams.release_memory_write_lock(user_id, lock_token)

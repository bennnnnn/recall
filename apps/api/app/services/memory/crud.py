import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Memory
from app.services.memory.facts import MUTED_STATUS

logger = logging.getLogger(__name__)


async def _invalidate_caches(seams: Any, user_id: UUID) -> None:
    from app.services import home as home_service

    await seams.invalidate_memory_block(user_id)
    await home_service.invalidate_home_cache(user_id)


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
    """Legacy sentence-index delete. Atomic rows delete the whole fact."""
    from app.gateways import embedding_gateway
    from app.repositories import memories as memories_repo

    lock_token = await seams._acquire_memory_write_lock_or_raise(user_id)
    try:
        memory = await memories_repo.get_by_id(session, user_id, memory_id)
        if memory is None:
            return False
        facts = seams.split_memory_facts(memory.text)
        if len(facts) <= 1:
            if expected_text is not None:
                expected = seams.normalize_memory_text(expected_text).lower()
                actual = seams.normalize_memory_text(memory.text).lower()
                if expected and expected not in actual and actual not in expected:
                    return False
            deleted = await memories_repo.delete_by_id(session, user_id, memory_id, commit=False)
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            if deleted:
                await _invalidate_caches(seams, user_id)
            return deleted

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
                await _invalidate_caches(seams, user_id)
            return deleted

        new_text = seams.join_memory_facts(facts)
        stored = seams.normalize_memory_text(new_text)
        try:
            new_vec = await embedding_gateway.embed_text(settings, stored)
        except Exception:
            logger.debug("Memory re-embed on fact delete failed", exc_info=True)
            new_vec = None
        try:
            if new_vec is not None:
                updated = await memories_repo.update_text_and_embedding(
                    session,
                    user_id,
                    memory_id,
                    stored,
                    new_vec,
                    embedding_gateway.serialize_embedding(new_vec),
                    embedding_text_hash=seams.embedding_text_hash(stored),
                    commit=False,
                )
            else:
                updated = await memories_repo.update_text(
                    session,
                    user_id,
                    memory_id,
                    stored,
                    commit=False,
                )
            if updated is not None:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
        if updated is not None:
            await _invalidate_caches(seams, user_id)
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
    text: str | None,
    *,
    status: str | None = None,
) -> Memory | None:
    from app.gateways import embedding_gateway
    from app.repositories import memories as memories_repo

    clean: str | None = None
    if text is not None:
        clean = seams.normalize_memory_text(seams.strip_memory_as_of(text))
        if not clean:
            raise seams.MemoryEmptyTextError()
    if clean is None and status is None:
        raise seams.MemoryEmptyTextError()
    lock_token = await seams._acquire_memory_write_lock_or_raise(user_id)
    try:
        memory = await memories_repo.get_by_id(session, user_id, memory_id)
        if memory is None:
            return None
        updated: Memory | None = memory
        try:
            if status is not None:
                updated = await memories_repo.update_status(
                    session, user_id, memory_id, status, commit=False
                )
                if updated is None:
                    return None
            if clean is not None:
                try:
                    new_vec = await embedding_gateway.embed_text(settings, clean)
                except Exception:
                    logger.debug("Memory re-embed on edit failed", exc_info=True)
                    new_vec = None
                if new_vec is not None:
                    updated = await memories_repo.update_text_and_embedding(
                        session,
                        user_id,
                        memory_id,
                        clean,
                        new_vec,
                        embedding_gateway.serialize_embedding(new_vec),
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
                await session.commit()
                await session.refresh(updated)
        except Exception:
            await session.rollback()
            raise
        if updated is not None:
            await _invalidate_caches(seams, user_id)
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
            await _invalidate_caches(seams, user_id)
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
            await _invalidate_caches(seams, user_id)
        return removed > 0
    finally:
        await seams.release_memory_write_lock(user_id, lock_token)


async def delete_all_memories(seams: Any, session: AsyncSession, user_id: UUID) -> int:
    from app.repositories import memories as memories_repo

    lock_token = await seams._acquire_memory_write_lock_or_raise(user_id)
    try:
        try:
            removed = await memories_repo.delete_all_for_user(session, user_id, commit=False)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        if removed:
            await _invalidate_caches(seams, user_id)
        return removed
    finally:
        await seams.release_memory_write_lock(user_id, lock_token)


async def disable_and_clear_memories(
    seams: Any,
    session: AsyncSession,
    user_id: UUID,
) -> int:
    from app.repositories import memories as memories_repo
    from app.repositories import users as users_repo

    lock_token = await seams._acquire_memory_write_lock_or_raise(user_id)
    try:
        try:
            if not await memories_repo.lock_memory_enabled(session, user_id):
                # Still allow wipe + disable even when already off.
                pass
            user = await users_repo.get_by_id(session, user_id)
            if user is None:
                return 0
            removed = await memories_repo.delete_all_for_user(session, user_id, commit=False)
            user.memory_enabled = False
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        await _invalidate_caches(seams, user_id)
        return removed
    finally:
        await seams.release_memory_write_lock(user_id, lock_token)


async def mute_memory(
    seams: Any,
    session: AsyncSession,
    user_id: UUID,
    memory_id: UUID,
) -> Memory | None:
    from app.repositories import memories as memories_repo

    lock_token = await seams._acquire_memory_write_lock_or_raise(user_id)
    try:
        updated: Memory | None = None
        try:
            updated = await memories_repo.update_status(
                session, user_id, memory_id, MUTED_STATUS, commit=False
            )
            if updated is not None:
                await session.commit()
                await session.refresh(updated)
        except Exception:
            await session.rollback()
            raise
        if updated is not None:
            await _invalidate_caches(seams, user_id)
        return updated
    finally:
        await seams.release_memory_write_lock(user_id, lock_token)

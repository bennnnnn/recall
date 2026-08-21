"""Compatibility barrel for the memory service.

Stateful behavior lives in focused cache, lock, retrieval, and CRUD modules.
Wrappers deliberately pass this module as the seam provider so existing
``app.services.memory.*`` monkeypatches continue to affect collaborators.
"""

import sys
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.background_tasks import create_background_task as create_background_task
from app.core.config import Settings
from app.core.redis import get_redis_client as get_redis_client
from app.models.orm import Memory, User
from app.services.memory import cache as _cache
from app.services.memory import crud as _crud
from app.services.memory import locks as _locks
from app.services.memory import retrieval as _retrieval
from app.services.memory.consolidation import (
    accept_memory_section_rewrite as accept_memory_section_rewrite,
)
from app.services.memory.consolidation import (
    consolidation_rewrite_preserves_facts as consolidation_rewrite_preserves_facts,
)
from app.services.memory.consolidation import (
    extract_consolidation_anchors as extract_consolidation_anchors,
)
from app.services.memory.consolidation import (
    section_needs_consolidation as section_needs_consolidation,
)
from app.services.memory.consolidation import (
    sections_need_consolidation as sections_need_consolidation,
)
from app.services.memory.selection import (
    _ALWAYS_INJECT_TYPES as _ALWAYS_INJECT_TYPES,
)
from app.services.memory.selection import (
    _SIMILARITY_GATED_TYPES as _SIMILARITY_GATED_TYPES,
)
from app.services.memory.selection import (
    SECTION_LABELS as SECTION_LABELS,
)
from app.services.memory.selection import (
    TYPE_PRIORITY as TYPE_PRIORITY,
)
from app.services.memory.selection import (
    _confidence_value as _confidence_value,
)
from app.services.memory.selection import (
    _eligible_memory as _eligible_memory,
)
from app.services.memory.selection import (
    format_memory_block as format_memory_block,
)
from app.services.memory.selection import (
    select_memories_for_prompt as select_memories_for_prompt,
)
from app.services.memory.selection import (
    select_memories_semantic as select_memories_semantic,
)
from app.services.memory.text import (
    _split_sentences as _split_sentences,
)
from app.services.memory.text import (
    embedding_text_hash as embedding_text_hash,
)
from app.services.memory.text import (
    is_sensitive_memory_text as is_sensitive_memory_text,
)
from app.services.memory.text import (
    join_memory_facts as join_memory_facts,
)
from app.services.memory.text import (
    normalize_memory_text as normalize_memory_text,
)
from app.services.memory.text import (
    split_memory_facts as split_memory_facts,
)
from app.services.memory.text import (
    stamp_memory_as_of as stamp_memory_as_of,
)
from app.services.memory.text import (
    strip_memory_as_of as strip_memory_as_of,
)


def _seams():
    return sys.modules[__name__]


def _memory_query_cache_key(user_id: UUID, generation: bytes | str | None, query_text: str) -> str:
    return _cache.memory_query_cache_key(user_id, generation, query_text)


def _memory_query_scoped_key(
    user_id: UUID,
    generation: bytes | str | None,
    query_text: str,
    *,
    omit_project_memory: bool,
    exclude_sensitive: bool,
) -> str:
    return _cache.memory_query_scoped_key(
        user_id,
        generation,
        query_text,
        omit_project_memory=omit_project_memory,
        exclude_sensitive=exclude_sensitive,
    )


def _memory_block_key(user_id: UUID) -> str:
    return _cache.memory_block_key(user_id)


def _memory_generation_key(user_id: UUID) -> str:
    return _cache.memory_generation_key(user_id)


async def _write_query_block_cache(cache_key: str, block: str, settings: Settings) -> None:
    await _cache.write_query_block_cache(_seams(), cache_key, block, settings)


async def invalidate_memory_block(user_id: UUID) -> None:
    await _cache.invalidate_memory_block(_seams(), user_id)


async def _semantic_memories_from_vec(
    session: AsyncSession,
    user: User,
    settings: Settings,
    query_vec: list[float],
    *,
    omit_project_memory: bool = False,
) -> list[Memory]:
    return await _retrieval.semantic_memories_from_vec(
        _seams(),
        session,
        user,
        settings,
        query_vec,
        omit_project_memory=omit_project_memory,
    )


async def load_relevant_memories(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    query_text: str | None = None,
    query_vec: list[float] | None = None,
    omit_project_memory: bool = False,
) -> list[Memory]:
    return await _retrieval.load_relevant_memories(
        _seams(),
        session,
        user,
        settings,
        query_text=query_text,
        query_vec=query_vec,
        omit_project_memory=omit_project_memory,
    )


async def _semantic_block_from_vec(
    session: AsyncSession,
    user: User,
    settings: Settings,
    query_vec: list[float],
    *,
    omit_project_memory: bool,
    exclude_sensitive: bool,
) -> str:
    return await _retrieval.semantic_block_from_vec(
        _seams(),
        session,
        user,
        settings,
        query_vec,
        omit_project_memory=omit_project_memory,
        exclude_sensitive=exclude_sensitive,
    )


async def _warm_semantic_memory_cache(
    settings: Settings,
    user_id: UUID,
    query_text: str,
    *,
    omit_project_memory: bool = False,
) -> None:
    await _retrieval.warm_semantic_memory_cache(
        _seams(),
        settings,
        user_id,
        query_text,
        omit_project_memory=omit_project_memory,
    )


async def get_memory_block(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    query_text: str | None = None,
    chat_project_id: UUID | None = None,
    exclude_sensitive: bool = False,
) -> str:
    return await _retrieval.get_memory_block(
        _seams(),
        session,
        user,
        settings,
        query_text=query_text,
        chat_project_id=chat_project_id,
        exclude_sensitive=exclude_sensitive,
    )


def _memory_write_lock_key(user_id: UUID) -> str:
    return _locks.memory_write_lock_key(user_id)


async def acquire_memory_write_lock(user_id: UUID) -> str | None:
    return await _locks.acquire_memory_write_lock(_seams(), user_id)


async def release_memory_write_lock(user_id: UUID, token: str | None) -> None:
    await _locks.release_memory_write_lock(_seams(), user_id, token)


class MemoryWriteLockBusyError(Exception):
    def __init__(self, user_id: UUID) -> None:
        super().__init__(f"Memory write lock busy for user_id={user_id}")
        self.user_id = user_id


class MemoryEmptyTextError(Exception):
    """Edited memory text normalized to empty."""


async def _acquire_memory_write_lock_or_raise(user_id: UUID) -> str:
    return await _locks.acquire_memory_write_lock_or_raise(_seams(), user_id)


async def delete_memory_fact(
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
    memory_id: UUID,
    fact_index: int,
    *,
    expected_text: str | None = None,
) -> bool:
    return await _crud.delete_memory_fact(
        _seams(),
        session,
        settings,
        user_id,
        memory_id,
        fact_index,
        expected_text=expected_text,
    )


async def update_memory(
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
    memory_id: UUID,
    text: str,
) -> Memory | None:
    return await _crud.update_memory(_seams(), session, settings, user_id, memory_id, text)


async def delete_memory(session: AsyncSession, user_id: UUID, memory_id: UUID) -> bool:
    return await _crud.delete_memory(_seams(), session, user_id, memory_id)


async def delete_memory_section(session: AsyncSession, user_id: UUID, memory_type: str) -> bool:
    return await _crud.delete_memory_section(_seams(), session, user_id, memory_type)

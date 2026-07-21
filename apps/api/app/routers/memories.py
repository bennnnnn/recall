import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs
from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_settings_dep
from app.core.redis import get_redis_client
from app.models.orm import User
from app.models.schemas import MemoryOut, MemoryType, MemoryUpdate
from app.repositories import memories as memories_repo
from app.services import memory as memory_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["memories"])

_CONSOLIDATE_LOCK_TTL = 300


async def _maybe_enqueue_consolidation(user: User, memories: list) -> None:
    if not user.memory_enabled or not memories:
        return
    redis = get_redis_client()
    lock_key = f"memconsolidate:{user.id}"
    try:
        # BUG FIX (perf): list_memories calls this on every GET /memories —
        # a plain, frequently-polled read. Checking the lock first avoids
        # re-running sections_need_consolidation's text scan over every
        # memory section on each of those reads while a consolidation job
        # is already queued/in-flight for this user (the common case while
        # sections stay messy across the whole lock TTL window).
        if await redis.exists(lock_key):
            return
        sections = {memory.type: memory.text for memory in memories}
        if not memory_service.sections_need_consolidation(sections):
            return
        acquired = await redis.set(lock_key, "1", ex=_CONSOLIDATE_LOCK_TTL, nx=True)
        if acquired:
            await jobs.enqueue(redis, "memory_consolidate", {"user_id": str(user.id)})
    except Exception:
        logger.debug("Failed to enqueue memory consolidation", exc_info=True)


@router.get("", response_model=list[MemoryOut])
async def list_memories(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[MemoryOut]:
    memories = await memories_repo.list_for_user(session, user.id)
    await _maybe_enqueue_consolidation(user, memories)
    return [MemoryOut.model_validate(m) for m in memories]


@router.post("/consolidate", status_code=status.HTTP_202_ACCEPTED)
async def consolidate_memories(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    if not user.memory_enabled:
        return {"status": "skipped"}

    memories = await memories_repo.list_for_user(session, user.id)
    sections = {memory.type: memory.text for memory in memories}
    if not memory_service.sections_need_consolidation(sections):
        return {"status": "skipped"}

    redis = get_redis_client()
    lock_key = f"memconsolidate:{user.id}"
    acquired = await redis.set(lock_key, "1", ex=_CONSOLIDATE_LOCK_TTL, nx=True)
    if acquired:
        await jobs.enqueue(redis, "memory_consolidate", {"user_id": str(user.id)})
        return {"status": "queued"}
    return {"status": "in_progress"}


_LOCK_BUSY_DETAIL = "Memory is being updated right now — try again in a moment."


@router.delete("/type/{memory_type}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory_section(
    memory_type: MemoryType,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        deleted = await memory_service.delete_memory_section(session, user.id, memory_type)
    except memory_service.MemoryWriteLockBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_LOCK_BUSY_DETAIL) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")


@router.patch("/{memory_id}", response_model=MemoryOut)
async def update_memory(
    memory_id: UUID,
    body: MemoryUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> MemoryOut:
    try:
        updated = await memory_service.update_memory(
            session, settings, user.id, memory_id, body.text
        )
    except memory_service.MemoryWriteLockBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_LOCK_BUSY_DETAIL) from exc
    except memory_service.MemoryEmptyTextError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Memory text cannot be empty",
        ) from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return MemoryOut.model_validate(updated)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        deleted = await memory_service.delete_memory(session, user.id, memory_id)
    except memory_service.MemoryWriteLockBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_LOCK_BUSY_DETAIL) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")


@router.delete("/{memory_id}/facts/{fact_index}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory_fact(
    memory_id: UUID,
    fact_index: int,
    fact_text: str | None = Query(default=None, max_length=2000),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    if fact_index < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid fact index")
    # fact_text (the fact as the client actually displayed it) lets the
    # service locate it by content instead of trusting a positional index
    # that may have gone stale — see the BUG FIX comment in
    # memory_service.delete_memory_fact.
    try:
        deleted = await memory_service.delete_memory_fact(
            session, settings, user.id, memory_id, fact_index, expected_text=fact_text
        )
    except memory_service.MemoryWriteLockBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_LOCK_BUSY_DETAIL) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory fact not found")

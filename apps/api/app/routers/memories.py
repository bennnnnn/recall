from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_settings_dep
from app.core.redis import get_redis_client
from app.models.orm import User
from app.models.schemas import MemoryOut, MemoryType, MemoryUpdate
from app.models.schemas.memory import MEMORY_FACT_TEXT_MAX_LENGTH
from app.services import memory as memory_service
from app.services.memory import enqueue_policy

router = APIRouter(prefix="/memories", tags=["memories"])

_LOCK_BUSY_DETAIL = "Memory is being updated right now — try again in a moment."


@router.get("", response_model=list[MemoryOut])
async def list_memories(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[MemoryOut]:
    memories = await enqueue_policy.list_user_memories(
        session,
        get_redis_client(),
        user,
    )
    titles = await enqueue_policy.source_chat_titles(session, memories)
    outs: list[MemoryOut] = []
    for memory in memories:
        item = MemoryOut.model_validate(memory)
        title = titles.get(memory.source_chat_id) if memory.source_chat_id else None
        if title:
            item = item.model_copy(update={"source_chat_title": title})
        outs.append(item)
    return outs


@router.post("/consolidate", status_code=status.HTTP_202_ACCEPTED)
async def consolidate_memories(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    result = await enqueue_policy.request_user_consolidation(
        session,
        get_redis_client(),
        user,
    )
    return {"status": result}


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_memories(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await memory_service.delete_all_memories(session, user.id)
    except memory_service.MemoryWriteLockBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_LOCK_BUSY_DETAIL) from exc


@router.post("/disable-and-clear", status_code=status.HTTP_204_NO_CONTENT)
async def disable_and_clear_memories(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await memory_service.disable_and_clear_memories(session, user.id)
    except memory_service.MemoryWriteLockBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_LOCK_BUSY_DETAIL) from exc


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_memories(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await memory_service.delete_all_memories(session, user.id)
    except memory_service.MemoryWriteLockBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_LOCK_BUSY_DETAIL) from exc


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
            session, settings, user.id, memory_id, body.text, status=body.status
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
    fact_text: str | None = Query(default=None, max_length=MEMORY_FACT_TEXT_MAX_LENGTH),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    if fact_index < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid fact index")
    try:
        deleted = await memory_service.delete_memory_fact(
            session, settings, user.id, memory_id, fact_index, expected_text=fact_text
        )
    except memory_service.MemoryWriteLockBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_LOCK_BUSY_DETAIL) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory fact not found")

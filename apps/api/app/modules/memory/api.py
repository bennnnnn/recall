from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_settings_dep
from app.core.rate_limit import allow_request_fail_closed
from app.core.redis import get_redis_client
from app.models.orm import User
from app.models.schemas import MemoryOut, MemoryType, MemoryUpdate
from app.modules import memory as memory_service
from app.modules.memory import documents as documents_service
from app.modules.memory import enqueue_policy, history_scan
from app.modules.memory import instruct as instruct_service
from app.modules.memory.schemas import (
    MEMORY_FACT_TEXT_MAX_LENGTH,
    MemoryDocumentOut,
    MemoryDocumentsOut,
    MemoryInstructIn,
    MemoryInstructOut,
)
from app.modules.memory.topics import parse_topic
from app.services import quota as quota_service

router = APIRouter(prefix="/memories", tags=["memories"])

_LOCK_BUSY_DETAIL = "Memory is being updated right now — try again in a moment."
# Direct edits call the model; this bounds them per user per hour.
_INSTRUCT_PER_HOUR = 30


def _document_out(document: documents_service.MemoryDocument) -> MemoryDocumentOut:
    return MemoryDocumentOut(
        key=document.key,
        group=document.group,
        title=document.title,
        summary=document.summary,
        updated_at=document.updated_at,
        facts=[MemoryOut.model_validate(fact) for fact in document.facts],
    )


async def _documents_out(session: AsyncSession, user: User) -> list[MemoryDocumentOut]:
    return [_document_out(doc) for doc in await documents_service.list_documents(session, user.id)]


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


@router.get("/documents", response_model=MemoryDocumentsOut)
async def list_memory_documents(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MemoryDocumentsOut:
    documents = await _documents_out(session, user)
    scanning = await history_scan.request_history_scan(get_redis_client(), user)
    return MemoryDocumentsOut(documents=documents, scanning=scanning)


@router.delete("/documents/{topic}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory_document(
    topic: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    key = parse_topic(topic)
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    try:
        deleted = await memory_service.delete_memory_document(session, user.id, key)
    except memory_service.MemoryWriteLockBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_LOCK_BUSY_DETAIL) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")


@router.post("/instruct", response_model=MemoryInstructOut)
async def instruct_memory(
    body: MemoryInstructIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> MemoryInstructOut:
    redis = get_redis_client()
    if await quota_service.global_spend_exceeded(redis, settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory editing is paused right now — try again later.",
        )
    if not await allow_request_fail_closed(
        redis, f"memory_instruct:{user.id}", limit=_INSTRUCT_PER_HOUR, window_seconds=3600
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many memory edits — try again later.",
        )
    try:
        outcome = await instruct_service.apply_memory_instruction(
            settings,
            user_id=user.id,
            instruction=body.instruction.strip(),
            focus_topic=body.topic,
        )
    except memory_service.MemoryWriteLockBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_LOCK_BUSY_DETAIL) from exc
    except instruct_service.MemoryOffError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Memory is off.") from exc
    except instruct_service.MemoryInstructionFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Memory couldn't be updated right now — try again.",
        ) from exc
    return MemoryInstructOut(
        reply=outcome.reply,
        applied=outcome.applied,
        documents=await _documents_out(session, user),
    )


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

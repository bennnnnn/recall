from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_settings_dep
from app.core.rate_limit import allow_request_fail_closed
from app.core.redis import get_redis_client
from app.models.orm import Memory, User
from app.models.schemas import MemoryOut, MemoryUpdate
from app.modules import memory as memory_service
from app.modules.memory import documents as documents_service
from app.modules.memory import enqueue_policy, history_scan
from app.modules.memory import instruct as instruct_service
from app.modules.memory.schemas import (
    MemoryDocumentOut,
    MemoryDocumentsOut,
    MemoryInstructIn,
    MemoryInstructOut,
)
from app.modules.memory.topics import parse_topic
from app.services import quota as quota_service

router = APIRouter(prefix="/memories", tags=["memories"])

# Direct edits call the model; this bounds them per user per hour.
_INSTRUCT_PER_HOUR = 30


def _fact_out(fact: Memory, titles: dict[UUID, str]) -> MemoryOut:
    item = MemoryOut.model_validate(fact)
    title = titles.get(fact.source_chat_id) if fact.source_chat_id else None
    return item.model_copy(update={"source_chat_title": title}) if title else item


def _document_out(
    document: documents_service.MemoryDocument, titles: dict[UUID, str]
) -> MemoryDocumentOut:
    return MemoryDocumentOut(
        key=document.key,
        group=document.group,
        title=document.title,
        summary=document.summary,
        updated_at=document.updated_at,
        facts=[_fact_out(fact, titles) for fact in document.facts],
    )


async def _documents_out(session: AsyncSession, user: User) -> list[MemoryDocumentOut]:
    """Every page, each fact with the chat it was learned in (M12)."""
    documents = await documents_service.list_documents(session, user.id)
    titles = await enqueue_policy.source_chat_titles(
        session, [fact for document in documents for fact in document.facts]
    )
    return [_document_out(document, titles) for document in documents]


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
    return [_fact_out(memory, titles) for memory in memories]


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
    deleted = await memory_service.delete_memory_document(session, user.id, key)
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
    outcome = await instruct_service.apply_memory_instruction(
        settings,
        user_id=user.id,
        instruction=body.instruction.strip(),
        focus_topic=body.topic,
    )
    return MemoryInstructOut(
        reply=outcome.reply,
        applied=outcome.applied,
        documents=await _documents_out(session, user),
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_memories(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    await memory_service.delete_all_memories(session, user.id)


@router.patch("/{memory_id}", response_model=MemoryOut)
async def update_memory(
    memory_id: UUID,
    body: MemoryUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> MemoryOut:
    updated = await memory_service.update_memory(
        session, settings, user.id, memory_id, body.text, status=body.status
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return MemoryOut.model_validate(updated)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    deleted = await memory_service.delete_memory(session, user.id, memory_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")

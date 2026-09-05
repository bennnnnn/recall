"""Assemble a user's data export (profile, chats, memories, todos, projects, attachments)."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import SessionLocal
from app.gateways.storage_gateway import StorageGateway, get_storage_gateway
from app.models.orm import (
    Chat,
    LearningPracticeEvent,
    Memory,
    Message,
    ProductEvent,
    Project,
    ProjectItem,
    TodoItem,
    User,
)
from app.repositories import attachments as attachments_repo
from app.repositories import chats as chats_repo
from app.repositories import learning_export as learning_export_repo
from app.repositories import memories as memories_repo
from app.repositories import messages as messages_repo
from app.repositories import product_events as product_events_repo
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.repositories import todos as todos_repo

logger = logging.getLogger(__name__)

# Bound memory/time for a single export request — messages are paged per chat.
EXPORT_MAX_CHATS = 500
EXPORT_MAX_MESSAGES_PER_CHAT = 2_000
EXPORT_MESSAGE_PAGE_SIZE = 200
EXPORT_MEMORY_PAGE_SIZE = 50
EXPORT_MAX_MEMORIES = 50
EXPORT_MAX_TODOS = 2_000
EXPORT_TODO_PAGE_SIZE = 200
EXPORT_MAX_PROJECTS = 100
EXPORT_MAX_PROJECT_ITEMS = 20_000
EXPORT_MAX_LEARNING_PRACTICE_EVENTS = 20_000
EXPORT_LEARNING_PRACTICE_PAGE_SIZE = 200
EXPORT_MAX_ATTACHMENTS = 2_000
EXPORT_MAX_PRODUCT_EVENTS = 2_000


def _user_payload(user: User) -> dict[str, Any]:
    return {
        "email": user.email,
        "name": user.name,
        "created_at": user.created_at.isoformat(),
    }


def _chat_header(chat: Chat) -> dict[str, Any]:
    return {
        "id": str(chat.id),
        "title": chat.title,
        "model": chat.model,
        "pinned": chat.pinned,
        "created_at": chat.created_at.isoformat(),
        "updated_at": chat.updated_at.isoformat(),
    }


def _message_payload(message: Message) -> dict[str, Any]:
    return {
        "role": message.role,
        "content": message.content,
        "model": message.model,
        "created_at": message.created_at.isoformat(),
    }


def _memory_payload(memory: Memory) -> dict[str, Any]:
    return {
        "type": memory.type,
        "text": memory.text,
        "confidence": float(memory.confidence) if memory.confidence is not None else None,
        "created_at": memory.created_at.isoformat(),
    }


def _todo_payload(todo: TodoItem) -> dict[str, Any]:
    return {
        "id": str(todo.id),
        "content": todo.content,
        "topic": todo.topic,
        "checked": todo.checked,
        "due_at": todo.due_at.isoformat() if todo.due_at is not None else None,
        "chat_id": str(todo.chat_id) if todo.chat_id is not None else None,
        "project_id": str(todo.project_id) if todo.project_id is not None else None,
        "sort_order": todo.sort_order,
        "created_at": todo.created_at.isoformat(),
        "updated_at": todo.updated_at.isoformat(),
    }


def _project_header(project: Project) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "title": project.title,
        "description": project.description,
        "kind": project.kind,
        "target_language": project.target_language,
        "native_language": project.native_language,
        "level": project.level,
        "daily_goal": project.daily_goal,
        "archived": project.archived,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


def _project_item_payload(item: ProjectItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "list_title": item.list_title,
        "content": item.content,
        "note": item.note,
        "definition": item.definition,
        "example_sentence": item.example_sentence,
        "ipa": item.ipa,
        "part_of_speech": item.part_of_speech,
        "vocabulary_kind": item.vocabulary_kind,
        "verb_kind": item.verb_kind,
        "noun_kind": item.noun_kind,
        "simple_gloss": item.simple_gloss,
        "status": item.status,
        "mastered": item.mastered,
        "mastered_at": item.mastered_at.isoformat() if item.mastered_at is not None else None,
        "last_completed_at": item.last_completed_at.isoformat()
        if item.last_completed_at is not None
        else None,
        "review_count": item.review_count,
        "quiz_attempts": item.quiz_attempts,
        "quiz_correct": item.quiz_correct,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _product_event_payload(event: ProductEvent) -> dict[str, Any]:
    return {
        "name": event.name,
        "properties": event.properties,
        "platform": event.platform,
        "app_version": event.app_version,
        "installation_id": event.installation_id,
        "client_at": event.client_at.isoformat() if event.client_at is not None else None,
        "recorded_at": event.recorded_at.isoformat(),
    }


def _practice_event_payload(event: LearningPracticeEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "attempt_id": str(event.attempt_id),
        "project_id": str(event.project_id),
        "item_id": str(event.item_id),
        "was_correct": event.was_correct,
        "completes_word": event.completes_word,
        "newly_mastered": event.newly_mastered,
        "occurred_at": event.occurred_at.isoformat(),
    }


def _export_limits(settings: Settings) -> dict[str, int]:
    return {
        "max_chats": EXPORT_MAX_CHATS,
        "max_messages_per_chat": EXPORT_MAX_MESSAGES_PER_CHAT,
        "max_memories": EXPORT_MAX_MEMORIES,
        "max_todos": EXPORT_MAX_TODOS,
        "max_projects": EXPORT_MAX_PROJECTS,
        "max_project_items": EXPORT_MAX_PROJECT_ITEMS,
        "max_learning_practice_events": EXPORT_MAX_LEARNING_PRACTICE_EVENTS,
        "max_attachments": EXPORT_MAX_ATTACHMENTS,
        "max_product_events": EXPORT_MAX_PRODUCT_EVENTS,
        "attachment_download_url_ttl_seconds": settings.r2_presign_expiry_seconds,
    }


async def _attachment_payload(
    attachment: Any,
    *,
    settings: Settings,
    gateway: StorageGateway,
) -> dict[str, Any]:
    download_url: str | None = None
    try:
        download_url = await gateway.presign_download(attachment.storage_key)
    except Exception:
        logger.warning(
            "Export presign failed for attachment_id=%s",
            attachment.id,
            exc_info=True,
        )
    return {
        "id": str(attachment.id),
        "message_id": str(attachment.message_id) if attachment.message_id is not None else None,
        "content_type": attachment.content_type,
        "size_bytes": attachment.size_bytes,
        "source": attachment.source,
        "created_at": attachment.created_at.isoformat(),
        "download_url": download_url,
        "download_url_expires_in_seconds": settings.r2_presign_expiry_seconds,
    }


class _BorrowedSession:
    """Use an existing session without closing it (``build_export`` tests)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *_args: object) -> None:
        return None


SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def _session_factory(session: AsyncSession | None) -> SessionFactory:
    if session is not None:
        return lambda: _BorrowedSession(session)
    return SessionLocal


async def _iter_export_json(
    user: User,
    settings: Settings,
    *,
    session_factory: SessionFactory,
) -> AsyncIterator[str]:
    # Open a session per repository call and close it before yielding so a
    # slow client download cannot pin a Neon connection for the stream lifetime.
    snapshot_time = datetime.now(UTC)
    exported_at = snapshot_time.isoformat()
    yield "{"
    yield f'"exported_at":{json.dumps(exported_at)},'
    yield f'"export_limits":{json.dumps(_export_limits(settings))},'
    yield f'"user":{json.dumps(_user_payload(user))},'
    yield '"chats":['

    async with session_factory() as session:
        chats = await chats_repo.list_for_user(
            session,
            user.id,
            limit=EXPORT_MAX_CHATS,
            include_archived=True,
        )
        chat_rows = [(_chat_header(chat), chat.id) for chat in chats]

    for chat_index, (header, chat_id) in enumerate(chat_rows):
        if chat_index:
            yield ","
        yield json.dumps(header)[:-1]
        yield ',"messages":['

        offset = 0
        first_message = True
        while offset < EXPORT_MAX_MESSAGES_PER_CHAT:
            page_size = min(EXPORT_MESSAGE_PAGE_SIZE, EXPORT_MAX_MESSAGES_PER_CHAT - offset)
            async with session_factory() as session:
                messages = await messages_repo.list_range(
                    session,
                    chat_id,
                    offset=offset,
                    limit=page_size,
                )
                message_chunks = [json.dumps(_message_payload(message)) for message in messages]
            if not message_chunks:
                break
            for chunk in message_chunks:
                if not first_message:
                    yield ","
                first_message = False
                yield chunk
            offset += len(message_chunks)
            if len(message_chunks) < page_size:
                break
        yield "]}"

    yield '],"memories":['
    memory_offset = 0
    first_memory = True
    while memory_offset < EXPORT_MAX_MEMORIES:
        page_size = min(EXPORT_MEMORY_PAGE_SIZE, EXPORT_MAX_MEMORIES - memory_offset)
        async with session_factory() as session:
            memories = await memories_repo.list_range(
                session,
                user.id,
                offset=memory_offset,
                limit=page_size,
            )
            memory_chunks = [json.dumps(_memory_payload(memory)) for memory in memories]
        if not memory_chunks:
            break
        for chunk in memory_chunks:
            if not first_memory:
                yield ","
            first_memory = False
            yield chunk
        memory_offset += len(memory_chunks)
        if len(memory_chunks) < page_size:
            break

    yield '],"todos":['
    todo_offset = 0
    first_todo = True
    while todo_offset < EXPORT_MAX_TODOS:
        page_size = min(EXPORT_TODO_PAGE_SIZE, EXPORT_MAX_TODOS - todo_offset)
        async with session_factory() as session:
            todos = await todos_repo.list_for_user(
                session,
                user.id,
                limit=page_size,
                offset=todo_offset,
            )
            todo_chunks = [json.dumps(_todo_payload(todo)) for todo in todos]
        if not todo_chunks:
            break
        for chunk in todo_chunks:
            if not first_todo:
                yield ","
            first_todo = False
            yield chunk
        todo_offset += len(todo_chunks)
        if len(todo_chunks) < page_size:
            break

    yield '],"projects":['
    async with session_factory() as session:
        projects = await projects_repo.list_for_user(
            session,
            user.id,
            include_archived=True,
            limit=EXPORT_MAX_PROJECTS,
        )
        project_rows = [(_project_header(project), project.id) for project in projects]
        items_by_project: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
        if project_rows:
            items = await project_items_repo.list_for_projects(
                session,
                [project_id for _, project_id in project_rows],
                limit=EXPORT_MAX_PROJECT_ITEMS,
            )
            for item in items:
                items_by_project[item.project_id].append(_project_item_payload(item))

    for project_index, (header, project_id) in enumerate(project_rows):
        if project_index:
            yield ","
        yield json.dumps(header)[:-1]
        yield ',"items":['
        for item_index, item_payload in enumerate(items_by_project.get(project_id, [])):
            if item_index:
                yield ","
            yield json.dumps(item_payload)
        yield "]}"

    yield '],"learning_practice_events":['
    practice_count = 0
    practice_cursor: tuple[datetime, UUID] | None = None
    while practice_count < EXPORT_MAX_LEARNING_PRACTICE_EVENTS:
        page_size = min(
            EXPORT_LEARNING_PRACTICE_PAGE_SIZE, EXPORT_MAX_LEARNING_PRACTICE_EVENTS - practice_count
        )
        async with session_factory() as session:
            practice_events = await learning_export_repo.list_page(
                session,
                user.id,
                through=snapshot_time,
                limit=page_size,
                after=practice_cursor,
            )
            practice_chunks = [
                json.dumps(_practice_event_payload(event)) for event in practice_events
            ]
            if practice_events:
                last = practice_events[-1]
                practice_cursor = (last.occurred_at, last.id)
        for chunk in practice_chunks:
            if practice_count:
                yield ","
            yield chunk
            practice_count += 1
        if len(practice_chunks) < page_size:
            break

    yield '],"attachments":['
    async with session_factory() as session:
        attachments = await attachments_repo.list_for_user(
            session,
            user.id,
            limit=EXPORT_MAX_ATTACHMENTS,
        )
        # Copy scalars before close — ORM instances expire with the session.
        attachment_rows = [
            SimpleNamespace(
                id=attachment.id,
                message_id=attachment.message_id,
                storage_key=attachment.storage_key,
                content_type=attachment.content_type,
                size_bytes=attachment.size_bytes,
                source=attachment.source,
                created_at=attachment.created_at,
            )
            for attachment in attachments
        ]
    gateway = get_storage_gateway(settings)
    for attachment_index, attachment in enumerate(attachment_rows):
        if attachment_index:
            yield ","
        yield json.dumps(await _attachment_payload(attachment, settings=settings, gateway=gateway))

    yield '],"product_events":['
    async with session_factory() as session:
        product_events = await product_events_repo.list_for_user(
            session,
            user.id,
            limit=EXPORT_MAX_PRODUCT_EVENTS,
        )
        product_event_chunks = [
            json.dumps(_product_event_payload(event)) for event in product_events
        ]
    for event_index, event_payload in enumerate(product_event_chunks):
        if event_index:
            yield ","
        yield event_payload

    yield "]}"


async def iter_export_json(
    user: User,
    settings: Settings | None = None,
) -> AsyncIterator[str]:
    """Stream a valid JSON export without holding all messages in memory."""
    resolved = settings if settings is not None else get_settings()
    async for chunk in _iter_export_json(user, resolved, session_factory=SessionLocal):
        yield chunk


async def build_export(
    session: AsyncSession,
    user: User,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Materialize the export for tests and callers that need a dict."""
    resolved = settings if settings is not None else get_settings()
    parts: list[str] = []
    async for chunk in _iter_export_json(
        user,
        resolved,
        session_factory=_session_factory(session),
    ):
        parts.append(chunk)
    return json.loads("".join(parts))

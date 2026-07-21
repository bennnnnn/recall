"""Assemble a user's data export (profile, chats, memories, todos, projects, attachments)."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import SessionLocal
from app.gateways.storage_gateway import StorageGateway, get_storage_gateway
from app.models.orm import Attachment, Chat, Memory, Message, Project, ProjectItem, TodoItem, User
from app.repositories import attachments as attachments_repo
from app.repositories import chats as chats_repo
from app.repositories import memories as memories_repo
from app.repositories import messages as messages_repo
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.repositories import todos as todos_repo

logger = logging.getLogger(__name__)

# Bound memory/time for a single export request — messages are paged per chat.
EXPORT_MAX_CHATS = 500
EXPORT_MAX_MESSAGES_PER_CHAT = 2_000
EXPORT_MESSAGE_PAGE_SIZE = 200
EXPORT_MEMORY_PAGE_SIZE = 50
EXPORT_MAX_TODOS = 2_000
EXPORT_TODO_PAGE_SIZE = 200
EXPORT_MAX_PROJECTS = 100
EXPORT_MAX_PROJECT_ITEMS = 20_000
EXPORT_MAX_ATTACHMENTS = 2_000


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
        "status": item.status,
        "mastered": item.mastered,
        "mastered_at": item.mastered_at.isoformat() if item.mastered_at is not None else None,
        "review_count": item.review_count,
        "quiz_attempts": item.quiz_attempts,
        "quiz_correct": item.quiz_correct,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _export_limits(settings: Settings) -> dict[str, int]:
    return {
        "max_chats": EXPORT_MAX_CHATS,
        "max_messages_per_chat": EXPORT_MAX_MESSAGES_PER_CHAT,
        "max_todos": EXPORT_MAX_TODOS,
        "max_projects": EXPORT_MAX_PROJECTS,
        "max_project_items": EXPORT_MAX_PROJECT_ITEMS,
        "max_attachments": EXPORT_MAX_ATTACHMENTS,
        "attachment_download_url_ttl_seconds": settings.r2_presign_expiry_seconds,
    }


async def _attachment_payload(
    attachment: Attachment,
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


async def _iter_export_json(
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> AsyncIterator[str]:
    exported_at = datetime.now(UTC).isoformat()
    yield "{"
    yield f'"exported_at":{json.dumps(exported_at)},'
    yield f'"export_limits":{json.dumps(_export_limits(settings))},'
    yield f'"user":{json.dumps(_user_payload(user))},'
    yield '"chats":['

    chats = await chats_repo.list_for_user(
        session,
        user.id,
        limit=EXPORT_MAX_CHATS,
        include_archived=True,
    )
    for chat_index, chat in enumerate(chats):
        if chat_index:
            yield ","
        header = json.dumps(_chat_header(chat))
        yield header[:-1]
        yield ',"messages":['

        offset = 0
        first_message = True
        while offset < EXPORT_MAX_MESSAGES_PER_CHAT:
            page_size = min(EXPORT_MESSAGE_PAGE_SIZE, EXPORT_MAX_MESSAGES_PER_CHAT - offset)
            messages = await messages_repo.list_range(
                session,
                chat.id,
                offset=offset,
                limit=page_size,
            )
            if not messages:
                break
            for message in messages:
                if not first_message:
                    yield ","
                first_message = False
                yield json.dumps(_message_payload(message))
            offset += len(messages)
            if len(messages) < page_size:
                break
        yield "]}"

    yield '],"memories":['
    memory_offset = 0
    first_memory = True
    while True:
        memories = await memories_repo.list_range(
            session,
            user.id,
            offset=memory_offset,
            limit=EXPORT_MEMORY_PAGE_SIZE,
        )
        if not memories:
            break
        for memory in memories:
            if not first_memory:
                yield ","
            first_memory = False
            yield json.dumps(_memory_payload(memory))
        memory_offset += len(memories)
        if len(memories) < EXPORT_MEMORY_PAGE_SIZE:
            break

    yield '],"todos":['
    todo_offset = 0
    first_todo = True
    while todo_offset < EXPORT_MAX_TODOS:
        page_size = min(EXPORT_TODO_PAGE_SIZE, EXPORT_MAX_TODOS - todo_offset)
        todos = await todos_repo.list_for_user(
            session,
            user.id,
            limit=page_size,
            offset=todo_offset,
        )
        if not todos:
            break
        for todo in todos:
            if not first_todo:
                yield ","
            first_todo = False
            yield json.dumps(_todo_payload(todo))
        todo_offset += len(todos)
        if len(todos) < page_size:
            break

    yield '],"projects":['
    projects = await projects_repo.list_for_user(
        session,
        user.id,
        include_archived=True,
        limit=EXPORT_MAX_PROJECTS,
    )
    items_by_project: dict[UUID, list[ProjectItem]] = defaultdict(list)
    if projects:
        items = await project_items_repo.list_for_projects(
            session,
            [project.id for project in projects],
            limit=EXPORT_MAX_PROJECT_ITEMS,
        )
        for item in items:
            items_by_project[item.project_id].append(item)

    for project_index, project in enumerate(projects):
        if project_index:
            yield ","
        header = json.dumps(_project_header(project))
        yield header[:-1]
        yield ',"items":['
        for item_index, item in enumerate(items_by_project.get(project.id, [])):
            if item_index:
                yield ","
            yield json.dumps(_project_item_payload(item))
        yield "]}"

    yield '],"attachments":['
    attachments = await attachments_repo.list_for_user(
        session,
        user.id,
        limit=EXPORT_MAX_ATTACHMENTS,
    )
    gateway = get_storage_gateway(settings)
    for attachment_index, attachment in enumerate(attachments):
        if attachment_index:
            yield ","
        yield json.dumps(await _attachment_payload(attachment, settings=settings, gateway=gateway))

    yield "]}"


async def iter_export_json(
    user: User,
    settings: Settings | None = None,
) -> AsyncIterator[str]:
    """Stream a valid JSON export without holding all messages in memory."""
    resolved = settings if settings is not None else get_settings()
    async with SessionLocal() as session:
        async for chunk in _iter_export_json(session, user, resolved):
            yield chunk


async def build_export(
    session: AsyncSession,
    user: User,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Materialize the export for tests and callers that need a dict."""
    resolved = settings if settings is not None else get_settings()
    parts: list[str] = []
    async for chunk in _iter_export_json(session, user, resolved):
        parts.append(chunk)
    return json.loads("".join(parts))

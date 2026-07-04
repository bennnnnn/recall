"""Assemble a user's full data export (profile + chats + messages + memories)."""

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models.orm import Chat, Memory, Message, User
from app.repositories import chats as chats_repo
from app.repositories import memories as memories_repo
from app.repositories import messages as messages_repo

# Bound memory/time for a single export request — messages are paged per chat.
EXPORT_MAX_CHATS = 500
EXPORT_MAX_MESSAGES_PER_CHAT = 2_000
EXPORT_MESSAGE_PAGE_SIZE = 200


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


def _export_limits() -> dict[str, int]:
    return {
        "max_chats": EXPORT_MAX_CHATS,
        "max_messages_per_chat": EXPORT_MAX_MESSAGES_PER_CHAT,
    }


async def _iter_export_json(session: AsyncSession, user: User) -> AsyncIterator[str]:
    exported_at = datetime.now(UTC).isoformat()
    yield "{"
    yield f'"exported_at":{json.dumps(exported_at)},'
    yield f'"export_limits":{json.dumps(_export_limits())},'
    yield f'"user":{json.dumps(_user_payload(user))},'
    yield '"chats":['

    chats = await chats_repo.list_for_user(session, user.id, limit=EXPORT_MAX_CHATS)
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

    memories = await memories_repo.list_for_user(session, user.id)
    memory_payloads = [_memory_payload(memory) for memory in memories]
    yield f'],"memories":{json.dumps(memory_payloads)}'
    yield "}"


async def iter_export_json(user: User) -> AsyncIterator[str]:
    """Stream a valid JSON export without holding all messages in memory."""
    async with SessionLocal() as session:
        async for chunk in _iter_export_json(session, user):
            yield chunk


async def build_export(session: AsyncSession, user: User) -> dict[str, Any]:
    """Materialize the export for tests and callers that need a dict."""
    parts: list[str] = []
    async for chunk in _iter_export_json(session, user):
        parts.append(chunk)
    parsed: dict[str, Any] = json.loads("".join(parts))
    return parsed

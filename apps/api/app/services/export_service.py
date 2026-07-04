"""Assemble a user's full data export (profile + chats + messages + memories)."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import User
from app.repositories import chats as chats_repo
from app.repositories import memories as memories_repo
from app.repositories import messages as messages_repo

# Bound memory/time for a single export request — full history is streamed in pages.
EXPORT_MAX_CHATS = 500
EXPORT_MAX_MESSAGES_PER_CHAT = 2_000


async def build_export(session: AsyncSession, user: User) -> dict[str, Any]:
    chats = await chats_repo.list_for_user(session, user.id, limit=EXPORT_MAX_CHATS)
    exported_chats: list[dict[str, Any]] = []
    for chat in chats:
        msgs = await messages_repo.list_all(session, chat.id, limit=EXPORT_MAX_MESSAGES_PER_CHAT)
        exported_chats.append(
            {
                "id": str(chat.id),
                "title": chat.title,
                "model": chat.model,
                "pinned": chat.pinned,
                "created_at": chat.created_at.isoformat(),
                "updated_at": chat.updated_at.isoformat(),
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "model": m.model,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in msgs
                ],
            }
        )

    memories = await memories_repo.list_for_user(session, user.id)
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "export_limits": {
            "max_chats": EXPORT_MAX_CHATS,
            "max_messages_per_chat": EXPORT_MAX_MESSAGES_PER_CHAT,
        },
        "user": {
            "email": user.email,
            "name": user.name,
            "created_at": user.created_at.isoformat(),
        },
        "chats": exported_chats,
        "memories": [
            {
                "type": m.type,
                "text": m.text,
                "confidence": float(m.confidence) if m.confidence is not None else None,
                "created_at": m.created_at.isoformat(),
            }
            for m in memories
        ],
    }

"""Background todo extraction / sync from chat transcripts."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Message
from app.models.schemas import TodoExtractionResult
from app.repositories import todos as todos_repo
from app.repositories import users as users_repo
from app.services import home as home_service
from app.services.todos.actions import (
    _ACTION_RELOAD_LIMIT,
    MAX_TODO_ACTIONS_PER_TURN,
)
from app.services.todos.classification import _transcript_implies_bulk_shift_to_tomorrow

logger = logging.getLogger(__name__)

TODO_SYNC_RECENT_MESSAGES = 8


def format_chat_transcript(messages: list[Message]) -> str:
    lines: list[str] = []
    for msg in messages:
        prefix = "User" if msg.role == "user" else "Assistant"
        lines.append(f"{prefix}: {msg.content}")
    return "\n".join(lines)


async def build_todo_sync_transcript(
    session: AsyncSession,
    chat_id: UUID,
    *,
    user_message: str,
    assistant_text: str,
    recent_limit: int = TODO_SYNC_RECENT_MESSAGES,
) -> str:
    """Prefer recent chat messages so Yes/confirm turns include the prior offer + date."""
    from app.repositories import messages as messages_repo

    recent = await messages_repo.list_recent(session, chat_id, limit=recent_limit)
    if len(recent) >= 2:
        return format_chat_transcript(recent)
    return f"User: {user_message}\nAssistant: {assistant_text}"


@dataclass(frozen=True)
class _TodoSyncSnapshot:
    user_timezone: str | None
    snapshot: list[dict[str, Any]]


async def _load_todo_sync_snapshot(
    session: AsyncSession,
    user_id: UUID,
    settings: Settings,
) -> _TodoSyncSnapshot:
    user = await users_repo.get_by_id(session, user_id)
    user_timezone = user.timezone if user else None
    items = await todos_repo.list_for_user(session, user_id, limit=settings.todo_inject_limit)
    return _TodoSyncSnapshot(
        user_timezone=user_timezone,
        snapshot=[
            {
                "topic": item.topic,
                "content": item.content,
                "checked": item.checked,
                "due_at": item.due_at.isoformat() if item.due_at else None,
            }
            for item in items
        ],
    )


async def _apply_todo_extraction_result(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
    result: TodoExtractionResult | None,
    user_timezone: str | None,
) -> None:
    # Resolve apply via package so tests can patch todos_service.apply_todo_actions.
    # Bulk helpers are private — import (and patch) from actions.
    from app.services.todos import apply_todo_actions
    from app.services.todos.actions import _apply_bulk_shift_due_today_to_tomorrow

    if result and result.actions:
        safe_actions = result.actions[:MAX_TODO_ACTIONS_PER_TURN]
        await apply_todo_actions(
            session,
            user_id=user_id,
            actions=safe_actions,
            chat_id=chat_id,
            user_timezone=user_timezone,
        )
    if _transcript_implies_bulk_shift_to_tomorrow(transcript):
        items = await todos_repo.list_for_user(session, user_id, limit=_ACTION_RELOAD_LIMIT)
        bulk_applied = await _apply_bulk_shift_due_today_to_tomorrow(
            session,
            user_id=user_id,
            items=items,
            user_timezone=user_timezone,
        )
        if bulk_applied:
            logger.info(
                "Bulk-shifted %d todo(s) due today → tomorrow for user_id=%s",
                bulk_applied,
                user_id,
            )
            await home_service.invalidate_home_cache(user_id)
    # Deliberately no bulk overdue wipe here. Regex-triggered mass deletes had
    # unbounded blast radius; "delete overdue" must land as explicit LLM
    # `delete` actions (capped).


async def _run_extracted_todo_actions(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> TodoExtractionResult | None:
    from app.core.db import SessionLocal
    from app.services.todos.extract import extract_todo_actions

    async with SessionLocal() as session:
        loaded = await _load_todo_sync_snapshot(session, user_id, settings)
        await session.commit()

    try:
        result = await extract_todo_actions(
            settings,
            transcript,
            loaded.snapshot,
            user_timezone=loaded.user_timezone,
        )
    except Exception:
        logger.exception("Todo action extraction failed for user_id=%s", user_id)
        return None

    async with SessionLocal() as session:
        await _apply_todo_extraction_result(
            session,
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript=transcript,
            result=result,
            user_timezone=loaded.user_timezone,
        )
        await session.commit()
    return result


async def sync_todos_from_transcript(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> TodoExtractionResult | None:
    try:
        return await _run_extracted_todo_actions(
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript=transcript,
        )
    except Exception:
        logger.exception("Todo sync failed for user_id=%s", user_id)
        return None

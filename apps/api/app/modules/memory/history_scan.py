"""One pass over a user's recent chats, so memory starts from what they already said.

Live extraction only reads new turns. When someone opens the Memory screen for
the first time (or memory missed their earlier chats), this job reads the user
lines of their most recent chats once and records that it did.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select, update

from app.core import jobs
from app.core.config import Settings
from app.core.db import SessionLocal
from app.models.orm import Chat, User
from app.modules.memory.extract_backlog import history_transcript
from app.modules.memory.extraction_workflow import extract_and_store_memories
from app.repositories import messages as messages_repo
from app.repositories import users as users_repo

logger = logging.getLogger(__name__)

HISTORY_SCAN_JOB = "memory_history_scan"
HISTORY_SCAN_CHATS = 20
_LINES_PER_CHAT = 20
_QUEUED_TTL_SECONDS = 60 * 30
_LOCK_RETRIES = 3
_LOCK_RETRY_SECONDS = 2.0


def _queued_key(user_id: UUID) -> str:
    return f"memory:history_scan:{user_id}"


async def request_history_scan(redis: Redis, user: User) -> bool:
    """Queue the scan unless it already ran. True while it is queued or running."""
    if not user.memory_enabled or user.memory_history_scanned_at is not None:
        return False
    try:
        if await redis.set(_queued_key(user.id), "1", ex=_QUEUED_TTL_SECONDS, nx=True):
            await jobs.enqueue(redis, HISTORY_SCAN_JOB, {"user_id": str(user.id)})
    except Exception:
        logger.warning("memory history scan enqueue failed user_id=%s", user.id, exc_info=True)
        return False
    return True


async def _recent_chat_ids(user_id: UUID) -> list[UUID]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Chat.id)
            .where(Chat.user_id == user_id, Chat.quiz_mode.is_(None))
            .order_by(Chat.updated_at.desc())
            .limit(HISTORY_SCAN_CHATS)
        )
        return list(result.scalars().all())


async def _chat_transcript(chat_id: UUID) -> str:
    async with SessionLocal() as session:
        rows = await messages_repo.list_user_contents_since(session, chat_id, limit=_LINES_PER_CHAT)
    return history_transcript([row.content for row in rows])


async def _extract_chat(settings: Settings, user_id: UUID, chat_id: UUID, transcript: str) -> None:
    for attempt in range(_LOCK_RETRIES):
        outcome = await extract_and_store_memories(
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript=transcript,
            from_history=True,
        )
        if outcome != "skipped_lock":
            return
        await asyncio.sleep(_LOCK_RETRY_SECONDS * (attempt + 1))
    logger.info("memory history scan skipped a busy chat user_id=%s", user_id)


async def scan_recent_chats(settings: Settings, *, user_id: UUID) -> None:
    async with SessionLocal() as session:
        user = await users_repo.get_by_id(session, user_id)
        if user is None or not user.memory_enabled or user.memory_history_scanned_at:
            return
    chat_ids = await _recent_chat_ids(user_id)
    for chat_id in chat_ids:
        try:
            transcript = await _chat_transcript(chat_id)
            if transcript.strip():
                await _extract_chat(settings, user_id, chat_id, transcript)
        except Exception:
            # One bad chat must not stop the rest of the pass.
            logger.warning(
                "memory history scan chat failed user_id=%s chat_id=%s",
                user_id,
                chat_id,
                exc_info=True,
            )
    async with SessionLocal() as session:
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(memory_history_scanned_at=datetime.now(UTC))
        )
        await session.commit()
    logger.info("memory history scan done user_id=%s chats=%s", user_id, len(chat_ids))

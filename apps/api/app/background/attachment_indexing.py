"""Background job: index an attachment into pgvector chunks for RAG."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.services import attachment_rag

logger = logging.getLogger(__name__)


async def index_attachment_job(settings: Settings, payload: dict[str, Any]) -> None:
    """Best-effort — never raises into the chat path (jobs runner catches)."""
    if not settings.attachment_rag_enabled:
        return
    try:
        attachment_id = UUID(str(payload["attachment_id"]))
        user_id = UUID(str(payload["user_id"]))
        chat_raw = payload.get("chat_id")
        chat_id = UUID(str(chat_raw)) if chat_raw else None
    except (KeyError, TypeError, ValueError):
        logger.warning("attachment_index job missing ids payload=%s", payload)
        return

    async with SessionLocal() as session:
        count = await attachment_rag.index_attachment(
            session,
            settings,
            user_id=user_id,
            attachment_id=attachment_id,
            chat_id=chat_id,
        )
        if count:
            logger.info(
                "Indexed attachment_id=%s chunks=%s chat_id=%s",
                attachment_id,
                count,
                chat_id,
            )

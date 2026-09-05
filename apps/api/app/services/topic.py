import asyncio
import logging
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.repositories import chats as chats_repo
from app.services import chat_titles
from app.services.chat_titles import normalize_chat_title

logger = logging.getLogger(__name__)


async def generate_chat_title(
    settings: Settings,
    chat_id: UUID,
    user_message: str,
    assistant_message: str,
    *,
    user_id: UUID | None = None,
) -> None:
    if not user_message.strip() or not assistant_message.strip():
        await _release_topic_dedupe(chat_id)
        return
    if user_id is None:
        # Backward-compat: older in-flight job payloads may omit user_id.
        # Fall back to an unscoped update rather than dropping the title,
        # but log so the missing scope is visible.
        logger.warning(
            "Topic job missing user_id; falling back to unscoped title update chat_id=%s",
            chat_id,
        )
    try:
        title = await asyncio.wait_for(
            chat_titles.generate_title(settings, user_message, assistant_message),
            timeout=15.0,
        )
        title = normalize_chat_title(title)
        if not title:
            # LLM returned nothing usable — release the dedupe so a later
            # retry (e.g. list_messages backfill) can try again.
            await _release_topic_dedupe(chat_id)
            return
        async with SessionLocal() as session:
            applied = await chats_repo.set_title_if_empty(
                session, chat_id, title, user_id=user_id, commit=False
            )
            await session.commit()
        if not applied:
            # Chat already had a title (user renamed or a prior job won the
            # race). Release the dedupe so a future retry isn't blocked.
            await _release_topic_dedupe(chat_id)
    except Exception:
        logger.exception("Topic generation failed for chat_id=%s", chat_id)
        # On failure the retry loop handles dedupe; but if this is the final
        # attempt, release so a later retry can run.
        await _release_topic_dedupe(chat_id)
        raise


async def _release_topic_dedupe(chat_id: UUID) -> None:
    """Release the ``topic:{chat_id}`` dedupe key so a future retry can run.

    The worker claims the dedupe before dispatch and extends it on success.
    When the title is NOT applied (empty LLM output, chat already titled, or
    error), the claim would otherwise block retries for 24h — silently
    preventing a title from ever being generated for this chat.
    """
    try:
        from app.core.jobs import job_done_key
        from app.core.redis import get_redis_client

        await get_redis_client().delete(job_done_key(f"topic:{chat_id}"))
    except Exception:
        logger.debug("Failed to release topic dedupe chat_id=%s", chat_id, exc_info=True)

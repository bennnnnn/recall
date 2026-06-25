import logging
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways import litellm_gateway
from app.models.orm import Chat
from app.repositories import messages as messages_repo
from app.services.context_window import select_recent_window

logger = logging.getLogger(__name__)


async def compress_chat_history(settings: Settings, chat_id: UUID) -> None:
    """Fold messages older than the recent window into a rolling chat summary.

    Best-effort and batched: only runs once enough messages have aged out, so it
    keeps the prompt small on long chats without summarising on every turn.
    """
    try:
        async with SessionLocal() as session:
            chat = await session.get(Chat, chat_id)
            if chat is None:
                return

            total = await messages_repo.count_for_chat(session, chat_id)
            recent_all = await messages_repo.list_recent(
                session, chat_id, limit=settings.recent_message_window
            )
            # Keep the most recent turns that fit the token budget verbatim;
            # everything older is eligible to be folded into the summary.
            keep = select_recent_window(
                recent_all, settings.context_token_budget, settings.recent_message_window
            )

            aged_out = total - keep
            already = chat.summary_message_count or 0
            if aged_out - already < settings.history_summary_batch:
                return

            slice_msgs = await messages_repo.list_range(
                session, chat_id, offset=already, limit=aged_out - already
            )
            if not slice_msgs:
                return

            transcript = [{"role": m.role, "content": m.content} for m in slice_msgs]
            new_summary = await litellm_gateway.summarize_conversation(
                settings, chat.summary, transcript
            )
            if not new_summary:
                return

            chat.summary = new_summary
            chat.summary_message_count = aged_out
            await session.commit()
    except Exception:
        logger.exception("History compression failed for chat_id=%s", chat_id)

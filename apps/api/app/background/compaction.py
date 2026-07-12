import logging
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.core.redis_lock import acquire_lock, release_lock
from app.gateways import litellm_gateway
from app.models.orm import Chat
from app.repositories import messages as messages_repo
from app.services.context_window import (
    cap_summary,
    compute_history_split,
    should_run_compression,
    trim_message_for_summary,
)

logger = logging.getLogger(__name__)

# Generous relative to one summarize_conversation call so a normal run never
# has its lock expire mid-flight (acquire_lock/release_lock are the same
# token-based compare-and-delete lock used for the periodic schedulers).
_COMPRESS_LOCK_TTL_SECONDS = 120


async def compress_chat_history(settings: Settings, chat_id: UUID) -> None:
    """Fold messages older than the recent window into a rolling chat summary.

    Best-effort and batched: runs when enough messages have aged out, or sooner
    when the token budget is tight on long threads.
    """
    # BUG FIX (was silent, latent): a "compress" job is enqueued on essentially
    # every turn (see services/chat/post_turn.py) and this worker currently
    # runs as a single instance, so this was never exploitable in practice —
    # but nothing stopped two "compress" jobs for the *same* chat_id being
    # picked up by two different worker instances concurrently once the
    # worker is scaled beyond 1 (a documented future step). Both would read
    # the same chat.summary_message_count, summarize overlapping ranges, and
    # the last commit would silently clobber the other's work. Lock per-chat
    # for the duration of one compression pass before scaling workers past 1.
    redis = get_redis_client()
    lock_key = f"chatcompress:{chat_id}"
    token = await acquire_lock(redis, lock_key, _COMPRESS_LOCK_TTL_SECONDS)
    if token is None:
        return
    try:
        async with SessionLocal() as session:
            chat = await session.get(Chat, chat_id)
            if chat is None:
                return

            total = await messages_repo.count_for_chat(session, chat_id)
            recent_all = await messages_repo.list_recent(
                session, chat_id, limit=settings.recent_message_window
            )
            split = compute_history_split(
                total,
                recent_all,
                settings.context_token_budget,
                settings.recent_message_window,
            )

            already = chat.summary_message_count or 0
            if not should_run_compression(
                split,
                already,
                settings.history_summary_batch,
                urgent_min_pending=settings.history_summary_urgent_pending,
            ):
                return

            pending = split.summarized_count - already
            slice_msgs = await messages_repo.list_range(
                session, chat_id, offset=already, limit=pending
            )
            if not slice_msgs:
                return

            transcript = [
                {
                    "role": m.role,
                    "content": trim_message_for_summary(m.content),
                }
                for m in slice_msgs
            ]
            new_summary = await litellm_gateway.summarize_conversation(
                settings, chat.summary, transcript
            )
            if not new_summary:
                return

            chat.summary = cap_summary(new_summary)
            chat.summary_message_count = split.summarized_count
            await session.commit()
    except Exception:
        logger.exception("History compression failed for chat_id=%s", chat_id)
    finally:
        await release_lock(redis, lock_key, token)

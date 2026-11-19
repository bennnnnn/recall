"""Chat history compaction workflow."""

import logging
from dataclasses import dataclass
from functools import partial
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.core.redis_lock import acquire_lock, release_lock
from app.models.orm import Chat
from app.modules.chat.context_window import (
    cap_summary,
    compute_history_split,
    should_run_compression,
    trim_message_for_summary,
)
from app.modules.chat.prompt_window import strip_prompt_owned_fences
from app.modules.chat.summarize import summarize_conversation
from app.modules.conversation import history as conversation_history
from app.services.md_fence_scan import map_closed_fences

logger = logging.getLogger(__name__)

_COMPRESS_LOCK_TTL_SECONDS = 120


# A picture the phone draws from the saved reply, by its fence, and what the summary model is
# told was shown in its place.
_SHOWN = {
    "graph": "graph",
    "geometry": "figure",
    "simulation": "diagram",
    "chart": "chart",
    "vega": "chart",
    "vega-lite": "chart",
    "plot": "chart",
    "mermaid": "diagram",
    "chem_scene": "diagram",
    "smiles": "molecule",
    "chemistry": "molecule",
    "molecule": "molecule",
    "molecule3d": "molecule",
    "photo": "photo",
}


def summary_text(reply: str) -> str:
    """A saved reply as the summary model reads it: each picture the phone draws from it
    marked "[shown: a graph]", and the fences the prompt owns left out (``strip_prompt_owned_
    fences``: a reply's search results are not what was said, and a summary kept their stale
    figures as facts). A summary of a 53-turn chat recorded "graphs provided" and "diagram
    drawn" where the reply only said so and nothing was drawn (2026-11-18): only a marked
    picture was shown (``SUMMARY_SYSTEM_PROMPT``)."""
    marked = reply
    for lang, shown in _SHOWN.items():
        marked = map_closed_fences(marked, lang, partial(_shown_mark, shown))
    return strip_prompt_owned_fences(marked)


def _shown_mark(shown: str, _body: str) -> str:
    return f"[shown: a {shown}]"


@dataclass(frozen=True, slots=True)
class _Fold:
    """What one compaction folds into the summary, read before the model runs."""

    summary: str | None
    transcript: list[dict[str, str]]
    already: int
    summarized_count: int


async def compress_chat_history(
    settings: Settings,
    chat_id: UUID,
    *,
    user_id: UUID | None = None,
) -> None:
    redis = get_redis_client()
    lock_key = f"chatcompress:{chat_id}"
    token = await acquire_lock(redis, lock_key, _COMPRESS_LOCK_TTL_SECONDS)
    if token is None:
        return
    try:
        fold = await _pending_fold(settings, chat_id, user_id)
        if fold is None:
            return
        # The summary model runs between two short transactions, never inside one: a pooled
        # connection held idle-in-transaction through a slow provider call starves the rest.
        new_summary = await summarize_conversation(settings, fold.summary, fold.transcript)
        if not new_summary:
            return
        await _save_summary(chat_id, user_id, fold, cap_summary(new_summary))
    except Exception:
        logger.exception("History compression failed for chat_id=%s", chat_id)
        raise
    finally:
        await release_lock(redis, lock_key, token)


async def _load_chat(session: AsyncSession, chat_id: UUID, user_id: UUID | None) -> Chat | None:
    if user_id is not None:
        return await conversation_history.get_chat(session, chat_id, user_id)
    return await session.get(Chat, chat_id)


async def _pending_fold(settings: Settings, chat_id: UUID, user_id: UUID | None) -> _Fold | None:
    """The messages that have aged out of the window and are not yet summarized, if enough."""
    async with SessionLocal() as session:
        chat = await _load_chat(session, chat_id, user_id)
        if chat is None:
            return None
        total = await conversation_history.message_count(session, chat_id)
        recent_all = await conversation_history.recent_messages(
            session,
            chat_id,
            limit=settings.recent_message_window,
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
            return None
        slice_messages = await conversation_history.messages_page(
            session,
            chat_id,
            offset=already,
            limit=split.summarized_count - already,
        )
        if not slice_messages:
            return None
        transcript = [
            {
                "role": message.role,
                "content": trim_message_for_summary(
                    summary_text(message.content)
                    if message.role == "assistant"
                    else message.content
                ),
            }
            for message in slice_messages
        ]
        return _Fold(chat.summary, transcript, already, split.summarized_count)


async def _save_summary(chat_id: UUID, user_id: UUID | None, fold: _Fold, summary: str) -> None:
    async with SessionLocal() as session:
        chat = await _load_chat(session, chat_id, user_id)
        # Deleted, or folded by someone else while the model ran: this summary is stale.
        if chat is None or (chat.summary_message_count or 0) != fold.already:
            return
        chat.summary = summary
        chat.summary_message_count = fold.summarized_count
        await session.commit()

"""Chat history compaction workflow."""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs
from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis import get_redis_client
from app.core.redis_lock import acquire_lock, release_lock
from app.models.orm import Chat
from app.modules.chat.context_window import FoldRule, cap_summary, trim_message_for_summary
from app.modules.chat.prompt_window import strip_prompt_owned_fences
from app.modules.chat.summarize import summarize_conversation
from app.modules.conversation import history as conversation_history
from app.services.md_fence_scan import iter_fences

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
    "mermaid": "flowchart",
    "chem_scene": "diagram",
    "smiles": "molecule",
    "chemistry": "molecule",
    "molecule": "molecule",
    "molecule3d": "molecule",
    "mol3d": "molecule",
    "3dmol": "molecule",
    "photo": "photo",
}
# A 3D view the phone folds into the molecule card just above it: one molecule shown, not two.
_VIEW_OF_THE_CARD_ABOVE = (
    frozenset({"molecule3d", "mol3d", "3dmol"}),
    frozenset({"smiles", "chemistry"}),
)


def summary_text(reply: str) -> str:
    """A saved reply as the summary model reads it: each picture the phone draws from it
    marked "[shown: a graph]", and the fences the prompt owns left out (``strip_prompt_owned_
    fences``: a reply's search results are not what was said, and a summary kept their stale
    figures as facts). A summary of a 53-turn chat recorded "graphs provided" and "diagram
    drawn" where the reply only said so and nothing was drawn (2026-11-18): only a marked
    picture was shown (``SUMMARY_SYSTEM_PROMPT``)."""
    return strip_prompt_owned_fences(_marked(reply))


def _marked(reply: str) -> str:
    """Each closed picture fence as its mark; a 3D view folded into the card above, none."""
    views, cards = _VIEW_OF_THE_CARD_ABOVE
    pieces: list[str] = []
    at, previous = 0, None
    for fence in iter_fences(reply):
        if not fence.closed or fence.lang not in _SHOWN:
            previous = None
            continue
        folded = (
            fence.lang in views
            and previous is not None
            and previous.lang in cards
            and not reply[previous.end : fence.start].strip()
        )
        mark = "" if folded else f"[shown: a {_SHOWN[fence.lang]}]"
        pieces += [reply[at : fence.start], mark]
        at, previous = fence.end, fence
    return "".join([*pieces, reply[at:]])


@dataclass(frozen=True, slots=True)
class _Fold:
    """What one compaction folds into the summary, read before the model runs."""

    summary: str | None
    transcript: list[dict[str, str]]
    already: int
    summarized_count: int
    # A backlog past one run's cap: more is waiting once this fold is saved.
    more: bool = False


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
    more = False
    try:
        fold = await _pending_fold(settings, chat_id, user_id)
        if fold is None:
            return
        # The summary model runs between two short transactions, never inside one: a pooled
        # connection held idle-in-transaction through a slow provider call starves the rest.
        new_summary = await summarize_conversation(settings, fold.summary, fold.transcript)
        if not new_summary:
            return
        saved = await _save_summary(chat_id, user_id, fold, cap_summary(new_summary))
        more = saved and fold.more
    except Exception:
        logger.exception("History compression failed for chat_id=%s", chat_id)
        raise
    finally:
        await release_lock(redis, lock_key, token)
    if more and user_id is not None:
        await _enqueue_next_fold(chat_id, user_id)


async def _enqueue_next_fold(chat_id: UUID, user_id: UUID) -> None:
    """Queue the backlog's next window, after the lock is released (a run that found it
    held would return). Until the backlog drains, the prompt cannot reach the summary's
    edge and slides, leaving the rows between the two out of both. The job is skipped
    like any other while the global spend cap holds (``background/handlers``), and each
    run folds older rows, so the chain ends."""
    await jobs.enqueue(
        get_redis_client(),
        "compress",
        {"chat_id": str(chat_id), "user_id": str(user_id)},
        dedupe_key=jobs.unique_dedupe_key(f"compress:{chat_id}"),
    )


async def _load_chat(session: AsyncSession, chat_id: UUID, user_id: UUID | None) -> Chat | None:
    if user_id is not None:
        return await conversation_history.get_chat(session, chat_id, user_id)
    return await session.get(Chat, chat_id)


async def _pending_fold(settings: Settings, chat_id: UUID, user_id: UUID | None) -> _Fold | None:
    """The oldest unsummarized messages, once they pass the fold trigger (``FoldRule``)."""
    async with SessionLocal() as session:
        chat = await _load_chat(session, chat_id, user_id)
        if chat is None:
            return None
        total = await conversation_history.message_count(session, chat_id)
        already = chat.summary_message_count or 0
        waiting = total - already
        if waiting <= 0:
            return None
        loaded = await conversation_history.recent_messages(
            session,
            chat_id,
            limit=min(waiting, settings.history_max_messages),
        )
        fold = FoldRule.of(settings).to_fold(loaded, unseen=waiting - len(loaded))
        if fold <= 0:
            return None
        # A backlog (a chat older than the rule, a job that failed) folds a window's worth
        # a run, oldest first, so the summary model never reads hundreds of messages at once.
        more = fold > settings.history_max_messages
        fold = min(fold, settings.history_max_messages)
        summarized_count = already + fold
        slice_messages = await conversation_history.messages_page(
            session,
            chat_id,
            offset=already,
            limit=fold,
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
        return _Fold(chat.summary, transcript, already, summarized_count, more)


async def _save_summary(chat_id: UUID, user_id: UUID | None, fold: _Fold, summary: str) -> bool:
    """Whether the summary was saved."""
    async with SessionLocal() as session:
        chat = await _load_chat(session, chat_id, user_id)
        # Deleted, or folded by someone else while the model ran: this summary is stale.
        if chat is None or (chat.summary_message_count or 0) != fold.already:
            return False
        chat.summary = summary
        chat.summary_message_count = fold.summarized_count
        await session.commit()
    return True

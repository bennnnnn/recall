"""What a saved turn sets off: the durable post-turn jobs (``core/jobs``).

Title, memory, lesson progress, the to-do repair, compression and indexing are
best-effort background work: enqueued after the reply commits, never on the
stream's path. The commit itself is ``turn_settle``. ``POST_TURN_JOBS`` is the
list, in order: each entry reads the ``FinishedTurn`` and returns the jobs it
wants (none, one, or one per attachment).
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from redis.asyncio import Redis

from app.core import jobs
from app.core.config import Settings
from app.core.db import SessionLocal
from app.modules import todos as todos_service
from app.modules.chat.prompt_constants.lesson_flow import lesson_step
from app.modules.chat.turn_prep import StreamContext
from app.modules.memory import (
    is_explicit_memory_command,
    is_memory_correction,
    memory_extract_user_text,
)
from app.services import quota as quota_service
from app.services.text_normalize import cap_text_head_tail

logger = logging.getLogger(__name__)

# Memory extraction only needs recent head+tail; keep the job payload bounded.
_MEMORY_TRANSCRIPT_MAX_CHARS = 4000


@dataclass(frozen=True)
class PostTurnJob:
    """One durable job a finished turn enqueues (``core/jobs``)."""

    name: str
    payload: dict[str, str]
    # Delivery is at least once: the key keeps a redelivered job from applying
    # its side effects twice (duplicate todos, etc.).
    dedupe_key: str | None


@dataclass(frozen=True)
class FinishedTurn:
    """What the post-turn jobs read about the turn they follow."""

    settings: Settings
    ctx: StreamContext
    assistant_text: str
    # This turn as "User: …\nAssistant: …".
    transcript: str
    # The user line only (stripped): assistant restatements and attachment OCR
    # must not become durable memories.
    memory_user_text: str
    # The assistant message id, or the turn's place in the chat before one exists.
    turn_key: str
    # Jobs that call a model wait while the global spend cap is reached.
    spend_capped: bool


async def _memory_job(turn: FinishedTurn) -> list[PostTurnJob]:
    ctx, settings = turn.ctx, turn.settings
    memory_transcript = f"User: {turn.memory_user_text}" if turn.memory_user_text else ""
    turn_number = (ctx.prior_count + 2) // 2
    should_extract_memory = (
        turn_number == 1
        or (
            settings.memory_extract_every_n_turns > 0
            and turn_number % settings.memory_extract_every_n_turns == 0
        )
        or is_explicit_memory_command(turn.memory_user_text)
        # "That's wrong, I'm at Stripe now": the saved fact changes on this turn.
        or is_memory_correction(turn.memory_user_text)
    )
    if (
        turn.spend_capped
        or ctx.skip_memory_jobs
        or not should_extract_memory
        or ctx.user is None
        or not ctx.user.memory_enabled
        or not memory_transcript
    ):
        return []
    # Dedupe per assistant message. Lock-busy retries use `{stem}:lock{n}`.
    return [
        PostTurnJob(
            "memory",
            {
                "user_id": str(ctx.user_id),
                "chat_id": str(ctx.chat_id),
                "transcript": cap_text_head_tail(memory_transcript, _MEMORY_TRANSCRIPT_MAX_CHARS),
                "assistant_message_id": turn.turn_key,
            },
            f"memory:{turn.turn_key}",
        )
    ]


async def _lesson_progress_job(turn: FinishedTurn) -> list[PostTurnJob]:
    """A lesson reply updates the chat's one "Learning X" memory line (no LLM)."""
    ctx = turn.ctx
    if (
        ctx.skip_memory_jobs
        or ctx.user is None
        or not ctx.user.memory_enabled
        or lesson_step(turn.assistant_text) is None
    ):
        return []
    return [
        PostTurnJob(
            "lesson_progress",
            {
                "user_id": str(ctx.user_id),
                "chat_id": str(ctx.chat_id),
                "assistant_message_id": turn.turn_key,
            },
            f"lesson_progress:{turn.turn_key}",
        )
    ]


async def _todos_job(turn: FinishedTurn) -> list[PostTurnJob]:
    """The background repair of a reminder change the reply missed.

    It writes without a card, so it stays off while reminder changes wait for the
    user's tap.
    """
    ctx = turn.ctx
    if (
        turn.spend_capped
        or ctx.skip_memory_jobs
        or turn.settings.reminder_proposals_enabled
        or not todos_service.should_recover_todo_writes(ctx.user_message_content, turn.transcript)
    ):
        return []
    todo_transcript = turn.transcript
    try:
        async with SessionLocal() as session:
            todo_transcript = await todos_service.build_todo_sync_transcript(
                session,
                ctx.chat_id,
                user_message=ctx.user_message_content,
                assistant_text=turn.assistant_text,
            )
    except Exception:
        logger.exception("Failed to expand todo sync transcript; using current turn only")
    return [
        PostTurnJob(
            "todos",
            {
                "user_id": str(ctx.user_id),
                "chat_id": str(ctx.chat_id),
                "transcript": todo_transcript,
            },
            f"todosync:{ctx.chat_id}:{turn.turn_key}",
        )
    ]


async def _topic_job(turn: FinishedTurn) -> list[PostTurnJob]:
    ctx = turn.ctx
    if not ctx.run_title:
        return []
    return [
        PostTurnJob(
            "topic",
            {
                "chat_id": str(ctx.chat_id),
                "user_id": str(ctx.user_id),
                "user_message": ctx.user_message_content,
                "assistant_message": turn.assistant_text,
            },
            f"topic:{ctx.chat_id}",
        )
    ]


async def _compress_job(turn: FinishedTurn) -> list[PostTurnJob]:
    """Dedupe by chat: rapid successive turns on one chat coalesce.

    The worker skips a duplicate enqueue, and the one job that runs compresses
    whatever is pending then (the later turn's messages too), instead of a no-op
    compress job on every turn.
    """
    ctx = turn.ctx
    if turn.spend_capped or not turn.settings.history_compression_enabled:
        return []
    return [
        PostTurnJob(
            "compress",
            {"chat_id": str(ctx.chat_id), "user_id": str(ctx.user_id)},
            f"compress:{ctx.chat_id}",
        )
    ]


async def _attachment_index_jobs(turn: FinishedTurn) -> list[PostTurnJob]:
    ctx = turn.ctx
    if turn.spend_capped:
        return []
    return [
        PostTurnJob(
            "attachment_index",
            {
                "attachment_id": attachment_id,
                "user_id": str(ctx.user_id),
                "chat_id": str(ctx.chat_id),
            },
            f"attachment_index:{attachment_id}:{ctx.chat_id}",
        )
        for attachment_id in ctx.indexable_attachment_ids
    ]


async def _message_index_job(turn: FinishedTurn) -> list[PostTurnJob]:
    """Memory off means no personal recall: past turns are not indexed for it either."""
    ctx = turn.ctx
    if (
        turn.spend_capped
        or not turn.settings.chat_history_rag_enabled
        or ctx.assistant_message_id is None
        or ctx.skip_memory_jobs
        or not (ctx.user is None or ctx.user.memory_enabled is not False)
    ):
        return []
    return [
        PostTurnJob(
            "message_index",
            {
                "user_id": str(ctx.user_id),
                "chat_id": str(ctx.chat_id),
                "assistant_message_id": str(ctx.assistant_message_id),
            },
            f"message_index:{ctx.assistant_message_id}",
        )
    ]


# The jobs a finished turn enqueues, in this order. A new post-turn job is one
# entry here (and its handler in ``background/handlers.py``).
POST_TURN_JOBS: tuple[Callable[[FinishedTurn], Awaitable[list[PostTurnJob]]], ...] = (
    _memory_job,
    _lesson_progress_job,
    _todos_job,
    _topic_job,
    _compress_job,
    _attachment_index_jobs,
    _message_index_job,
)


async def enqueue_post_turn_jobs(
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    assistant_text: str,
) -> None:
    spend_capped = await quota_service.global_spend_exceeded(redis, settings)
    if spend_capped:
        logger.warning(
            "skipping background LLM jobs: global spend cap user_id=%s chat_id=%s",
            ctx.user_id,
            ctx.chat_id,
        )
    turn = FinishedTurn(
        settings=settings,
        ctx=ctx,
        assistant_text=assistant_text,
        transcript=f"User: {ctx.user_message_content}\nAssistant: {assistant_text}",
        memory_user_text=memory_extract_user_text(ctx.user_message_content),
        turn_key=(
            str(ctx.assistant_message_id)
            if ctx.assistant_message_id is not None
            else f"prior{ctx.prior_count}"
        ),
        spend_capped=spend_capped,
    )
    queued = [job for build in POST_TURN_JOBS for job in await build(turn)]
    await asyncio.gather(
        *(jobs.enqueue(redis, job.name, job.payload, dedupe_key=job.dedupe_key) for job in queued)
    )

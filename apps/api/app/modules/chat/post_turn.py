"""What a saved turn sets off: the durable post-turn jobs (``core/jobs``).

Title, memory, lesson progress, the to-do repair, compression and indexing are
best-effort background work: enqueued after the reply commits, never on the
stream's path. The commit itself is ``turn_settle``.
"""

import asyncio
import logging

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


async def enqueue_post_turn_jobs(
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    assistant_text: str,
) -> None:
    transcript = f"User: {ctx.user_message_content}\nAssistant: {assistant_text}"
    # Extract from the user line only (stripped). Assistant restatements and
    # attachment OCR must not become durable memories.
    memory_user_text = memory_extract_user_text(ctx.user_message_content)
    memory_transcript = f"User: {memory_user_text}" if memory_user_text else ""
    # (job_type, payload, dedupe_key|None) — dedupe prevents at-least-once
    # redelivery from double-applying side effects (duplicate todos, etc.).
    job_specs: list[tuple[str, dict[str, str], str | None]] = []
    turn_number = (ctx.prior_count + 2) // 2
    turn_key = (
        str(ctx.assistant_message_id)
        if ctx.assistant_message_id is not None
        else f"prior{ctx.prior_count}"
    )
    spend_capped = await quota_service.global_spend_exceeded(redis, settings)
    if spend_capped:
        logger.warning(
            "skipping background LLM jobs: global spend cap user_id=%s chat_id=%s",
            ctx.user_id,
            ctx.chat_id,
        )
    should_extract_memory = (
        turn_number == 1
        or (
            settings.memory_extract_every_n_turns > 0
            and turn_number % settings.memory_extract_every_n_turns == 0
        )
        or is_explicit_memory_command(memory_user_text)
        # "That's wrong, I'm at Stripe now": the saved fact changes on this turn.
        or is_memory_correction(memory_user_text)
    )
    if (
        not spend_capped
        and not ctx.skip_memory_jobs
        and should_extract_memory
        and ctx.user is not None
        and ctx.user.memory_enabled
        and memory_transcript
    ):
        # Dedupe per assistant message. Lock-busy retries use `{stem}:lock{n}`.
        job_specs.append(
            (
                "memory",
                {
                    "user_id": str(ctx.user_id),
                    "chat_id": str(ctx.chat_id),
                    "transcript": cap_text_head_tail(
                        memory_transcript, _MEMORY_TRANSCRIPT_MAX_CHARS
                    ),
                    "assistant_message_id": turn_key,
                },
                f"memory:{turn_key}",
            ),
        )
    # A lesson reply updates the chat's one "Learning X" memory line (no LLM).
    if (
        not ctx.skip_memory_jobs
        and ctx.user is not None
        and ctx.user.memory_enabled
        and lesson_step(assistant_text) is not None
    ):
        job_specs.append(
            (
                "lesson_progress",
                {
                    "user_id": str(ctx.user_id),
                    "chat_id": str(ctx.chat_id),
                    "assistant_message_id": turn_key,
                },
                f"lesson_progress:{turn_key}",
            ),
        )
    # The background repair writes without a card, so it stays off while
    # reminder changes wait for the user's tap.
    if (
        not spend_capped
        and not ctx.skip_memory_jobs
        and not settings.reminder_proposals_enabled
        and todos_service.should_recover_todo_writes(ctx.user_message_content, transcript)
    ):
        todo_transcript = transcript
        try:
            async with SessionLocal() as session:
                todo_transcript = await todos_service.build_todo_sync_transcript(
                    session,
                    ctx.chat_id,
                    user_message=ctx.user_message_content,
                    assistant_text=assistant_text,
                )
        except Exception:
            logger.exception("Failed to expand todo sync transcript; using current turn only")
        job_specs.append(
            (
                "todos",
                {
                    "user_id": str(ctx.user_id),
                    "chat_id": str(ctx.chat_id),
                    "transcript": todo_transcript,
                },
                f"todosync:{ctx.chat_id}:{turn_key}",
            ),
        )
    if ctx.run_title:
        job_specs.append(
            (
                "topic",
                {
                    "chat_id": str(ctx.chat_id),
                    "user_id": str(ctx.user_id),
                    "user_message": ctx.user_message_content,
                    "assistant_message": assistant_text,
                },
                f"topic:{ctx.chat_id}",
            ),
        )
    if not spend_capped and settings.history_compression_enabled:
        # Dedupe by chat: rapid successive turns on the same chat coalesce —
        # the worker skips a duplicate enqueue, and the one job that runs
        # compresses whatever is pending at that time (including the later
        # turn's messages). Avoids churning the worker with a no-op compress
        # job on every turn.
        job_specs.append(
            (
                "compress",
                {"chat_id": str(ctx.chat_id), "user_id": str(ctx.user_id)},
                f"compress:{ctx.chat_id}",
            )
        )
    for attachment_id in ctx.indexable_attachment_ids if not spend_capped else []:
        job_specs.append(
            (
                "attachment_index",
                {
                    "attachment_id": attachment_id,
                    "user_id": str(ctx.user_id),
                    "chat_id": str(ctx.chat_id),
                },
                f"attachment_index:{attachment_id}:{ctx.chat_id}",
            ),
        )
    # Memory off means no personal recall: past turns are not indexed for it either.
    if (
        not spend_capped
        and settings.chat_history_rag_enabled
        and ctx.assistant_message_id is not None
        and not ctx.skip_memory_jobs
        and (ctx.user is None or ctx.user.memory_enabled is not False)
    ):
        job_specs.append(
            (
                "message_index",
                {
                    "user_id": str(ctx.user_id),
                    "chat_id": str(ctx.chat_id),
                    "assistant_message_id": str(ctx.assistant_message_id),
                },
                f"message_index:{ctx.assistant_message_id}",
            ),
        )

    await asyncio.gather(
        *(
            jobs.enqueue(redis, name, payload, dedupe_key=dedupe_key)
            for name, payload, dedupe_key in job_specs
        )
    )

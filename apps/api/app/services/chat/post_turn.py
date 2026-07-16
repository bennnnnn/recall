import asyncio
import json
import logging
import math
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs
from app.core.config import Settings, get_settings
from app.core.db import SessionLocal
from app.services import model_catalog
from app.services import projects as projects_service
from app.services import quota as quota_service
from app.services import todos as todos_service
from app.services.chat.turn_prep import RegenerateBackup, StreamContext
from app.services.context_window import estimate_tokens
from app.services.quota import utc_today

logger = logging.getLogger(__name__)


async def seed_usage_from_db(redis: Redis, session: AsyncSession, user_id: UUID) -> None:
    """Best-effort: re-seed the Redis daily usage counter from the DB total."""
    import app.services.chat as chat_pkg

    try:
        if await quota_service.has_daily_usage_key(redis, str(user_id)):
            return
        db_total = await chat_pkg.usage_repo.get_total_for_date(session, user_id, utc_today())
        await quota_service.seed_usage_if_missing(redis, str(user_id), db_total)
    except Exception:
        logger.debug("Usage DB-seed skipped (best-effort)", exc_info=True)


async def restore_regenerate_backup(
    user_id: UUID,
    chat_id: UUID,
    backup: RegenerateBackup,
) -> None:
    import app.services.chat as chat_pkg

    async with SessionLocal() as session:
        await chat_pkg.messages_repo.create(
            session,
            chat_id=chat_id,
            user_id=user_id,
            role="assistant",
            content=backup.content,
            model=backup.model,
        )


async def finalize_stream_turn_db(
    redis: Redis,
    ctx: StreamContext,
    assistant_text: str,
    usage: dict[str, int],
    result: dict[str, object] | None,
) -> None:
    import app.services.chat as chat_pkg

    usage_input = usage.get("input")
    input_tokens = (
        usage_input
        if usage_input is not None
        else sum(estimate_tokens(m["content"]) for m in ctx.prompt_messages)
    )
    usage_output = usage.get("output")
    output_tokens = usage_output if usage_output is not None else estimate_tokens(assistant_text)
    total_tokens = input_tokens + output_tokens
    multiplier = model_catalog.quota_multiplier(ctx.model)
    weighted_total = math.ceil(total_tokens * multiplier)

    # The daily usage aggregate must store WEIGHTED tokens (the same units
    # Redis uses), not raw — otherwise `seed_usage_from_db` re-seeds Redis
    # with a raw total after an eviction and the user silently gets
    # `multiplier`x more quota for the rest of the day. The per-message row
    # below keeps raw input/output for per-message display; only the daily
    # aggregate (used for re-seeding) is weighted.
    weighted_input = math.ceil(input_tokens * multiplier)
    weighted_output = math.ceil(output_tokens * multiplier)

    persisted_text = assistant_text

    try:
        async with SessionLocal() as session:
            assistant_message = await chat_pkg.messages_repo.create(
                session,
                chat_id=ctx.chat_id,
                user_id=ctx.user_id,
                role="assistant",
                content=persisted_text,
                model=ctx.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                message_id=ctx.assistant_message_id,
                commit=False,  # batch with touch + usage into one commit below
            )
            if result is not None:
                # `done` is sent before this task finishes; stream_and_finalize
                # already filled these. Kept for callers that await the task.
                result.setdefault("message_id", str(assistant_message.id))
                result.setdefault("resolved_model", ctx.model)
                if ctx.recalled_count:
                    result.setdefault("recalled", str(ctx.recalled_count))
                if ctx.memory_hints:
                    result.setdefault("memory_hints", json.dumps(ctx.memory_hints))
                if ctx.context_summarized:
                    result.setdefault("context_summarized", str(ctx.context_summarized))

            await chat_pkg.chats_repo.touch_by_id(session, ctx.chat_id, commit=False)

            try:
                await chat_pkg.usage_repo.add_tokens(
                    session,
                    ctx.user_id,
                    utc_today(),
                    # Weighted so the daily aggregate matches Redis units and
                    # re-seeds correctly after an eviction (see header comment).
                    input_tokens=weighted_input,
                    output_tokens=weighted_output,
                    commit=False,
                )
            except Exception:
                logger.exception("Failed to record usage tokens")

            # Single commit for message + chat touch + usage (was 3 Neon
            # round-trips per turn). Refresh the message so its server-side
            # id/created_at are populated for callers that read them.
            await session.commit()
            await session.refresh(assistant_message)

        # Cap overshoot at the user's daily limit so one turn's actual >
        # reserved delta can't push the counter past the cap (which would
        # make subsequent reserve_usage checks under-report remaining quota).
        daily_limit = (
            quota_service.daily_limit_for_user(ctx.user, get_settings())
            if ctx.user is not None
            else None
        )
        await quota_service.adjust_usage(
            redis,
            str(ctx.user_id),
            ctx.reserved_tokens,
            weighted_total,
            daily_limit=daily_limit,
        )
    except Exception:
        logger.exception("Stream-turn finalize failed; refunding reserved quota")
        await quota_service.refund_usage(redis, str(ctx.user_id), ctx.reserved_tokens)
        raise


async def enqueue_post_turn_jobs(
    redis: Redis,
    settings: Settings,
    ctx: StreamContext,
    assistant_text: str,
) -> None:
    transcript = f"User: {ctx.user_message_content}\nAssistant: {assistant_text}"
    job_specs: list[tuple[str, dict[str, str]]] = []
    turn_number = (ctx.prior_count + 2) // 2
    should_extract_memory = turn_number == 1 or (
        settings.memory_extract_every_n_turns > 0
        and turn_number % settings.memory_extract_every_n_turns == 0
    )
    if (
        not ctx.skip_memory_jobs
        and should_extract_memory
        and ctx.user is not None
        and ctx.user.memory_enabled
    ):
        job_specs.append(
            (
                "memory",
                {
                    "user_id": str(ctx.user_id),
                    "chat_id": str(ctx.chat_id),
                    "transcript": transcript,
                },
            ),
        )
    if not ctx.skip_memory_jobs and todos_service.transcript_implies_todo_sync(transcript):
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
            ),
        )
    if not ctx.skip_memory_jobs and projects_service.transcript_implies_project_sync(
        transcript,
        chat_project_id=ctx.chat_project_id,
    ):
        job_specs.append(
            (
                "projects",
                {
                    "user_id": str(ctx.user_id),
                    "chat_id": str(ctx.chat_id),
                    "transcript": transcript,
                },
            ),
        )
    if ctx.run_title:
        job_specs.append(
            (
                "topic",
                {
                    "chat_id": str(ctx.chat_id),
                    "user_message": ctx.user_message_content,
                    "assistant_message": assistant_text,
                },
            ),
        )
    if settings.history_compression_enabled:
        job_specs.append(("compress", {"chat_id": str(ctx.chat_id)}))
    if ctx.prior_count % 10 == 0:
        job_specs.append(("suggestions", {"user_id": str(ctx.user_id)}))
    for attachment_id in ctx.indexable_attachment_ids:
        job_specs.append(
            (
                "attachment_index",
                {
                    "attachment_id": attachment_id,
                    "user_id": str(ctx.user_id),
                    "chat_id": str(ctx.chat_id),
                },
            ),
        )

    await asyncio.gather(*(jobs.enqueue(redis, name, payload) for name, payload in job_specs))

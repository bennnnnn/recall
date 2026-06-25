import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs
from app.core.config import Settings
from app.core.db import SessionLocal
from app.exceptions import ChatNotFoundError, QuotaExceededError
from app.gateways import litellm_gateway
from app.gateways.litellm_gateway import ModelUnavailableError
from app.models.orm import User
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.repositories import usage as usage_repo
from app.repositories import users as users_repo
from app.services import memory as memory_service
from app.services import quota as quota_service
from app.services import routing
from app.services.context_window import estimate_tokens, select_recent_window
from app.services.quota import utc_today

logger = logging.getLogger(__name__)

STYLE_HINTS = {
    "short": "Keep responses concise.",
    "balanced": "Use a balanced level of detail.",
    "detailed": "Provide thorough, detailed answers.",
}


@dataclass
class _StreamContext:
    user_id: UUID
    chat_id: UUID
    model: str
    prompt_messages: list[dict[str, str]]
    run_title: bool
    user_message_content: str
    reserved_tokens: int
    recalled_count: int = 0


async def build_prompt_messages(
    session: AsyncSession,
    user: User,
    chat_id: UUID,
    settings: Settings,
    *,
    summary: str | None = None,
    out: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    memory_block = await memory_service.get_memory_block(session, user, settings)
    if out is not None:
        # Number of memories injected this turn (one "- " bullet per memory).
        out["recalled"] = memory_block.count("\n- ") if memory_block else 0
    recent_all = await messages_repo.list_recent(
        session, chat_id, limit=settings.recent_message_window
    )
    keep = select_recent_window(
        recent_all, settings.context_token_budget, settings.recent_message_window
    )
    recent = recent_all[-keep:] if keep else []

    system_parts = [
        "You are Recall, a helpful personal AI assistant.",
        STYLE_HINTS.get(user.response_style, STYLE_HINTS["balanced"]),
    ]
    if memory_block:
        system_parts.append(memory_block)
    if summary:
        system_parts.append(f"Summary of earlier conversation:\n{summary}")

    messages: list[dict[str, str]] = [{"role": "system", "content": "\n\n".join(system_parts)}]
    for msg in recent:
        messages.append({"role": msg.role, "content": msg.content})
    return messages


async def stream_chat_response(
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    content: str,
    model_alias: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
    result: dict[str, str] | None = None,
) -> AsyncIterator[str]:
    reserved = estimate_tokens(content) + settings.max_output_tokens
    if not await quota_service.reserve_usage(redis, str(user_id), reserved, settings):
        raise QuotaExceededError(
            "Daily token limit reached. Try again tomorrow or reduce message length."
        )

    try:
        ctx = await _prepare_chat_turn(
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            model_alias=model_alias,
            settings=settings,
            reserved_tokens=reserved,
        )
    except ChatNotFoundError:
        await quota_service.refund_usage(redis, str(user_id), reserved)
        raise
    except Exception:
        await quota_service.refund_usage(redis, str(user_id), reserved)
        raise

    try:
        async for token in _stream_and_finalize(
            redis,
            settings,
            ctx,
            should_cancel=should_cancel,
            result=result,
        ):
            yield token
    except ModelUnavailableError:
        await quota_service.refund_usage(redis, str(user_id), reserved)
        raise
    except Exception:
        await quota_service.refund_usage(redis, str(user_id), reserved)
        raise


async def stream_regenerate_response(
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    model_alias: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
    result: dict[str, str] | None = None,
) -> AsyncIterator[str]:
    async with SessionLocal() as session:
        user = await users_repo.get_by_id(session, user_id)
        if user is None:
            raise ChatNotFoundError("User not found.")

        chat = await chats_repo.get_by_id(session, chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError("Chat not found.")

        last = await messages_repo.get_last(session, chat_id)
        if last is None:
            raise ChatNotFoundError("No messages to regenerate.")
        if last.role == "assistant":
            await messages_repo.delete_message(session, last)

        last_user = await messages_repo.get_last_user(session, chat_id)
        if last_user is None:
            raise ChatNotFoundError("No user message to regenerate from.")

        model = model_alias or chat.model or user.default_model
        model = routing.resolve_alias(model, last_user.content)
        meta: dict[str, int] = {}
        prompt_messages = await build_prompt_messages(
            session, user, chat_id, settings, summary=chat.summary, out=meta
        )
        user_message_content = last_user.content

    reserved = estimate_tokens(user_message_content) + settings.max_output_tokens
    if not await quota_service.reserve_usage(redis, str(user_id), reserved, settings):
        raise QuotaExceededError("Daily token limit reached. Try again tomorrow.")

    ctx = _StreamContext(
        user_id=user_id,
        chat_id=chat_id,
        model=model,
        prompt_messages=prompt_messages,
        run_title=False,
        user_message_content=user_message_content,
        reserved_tokens=reserved,
        recalled_count=meta.get("recalled", 0),
    )

    try:
        async for token in _stream_and_finalize(
            redis,
            settings,
            ctx,
            should_cancel=should_cancel,
            result=result,
        ):
            yield token
    except ModelUnavailableError:
        await quota_service.refund_usage(redis, str(user_id), reserved)
        raise
    except Exception:
        await quota_service.refund_usage(redis, str(user_id), reserved)
        raise


async def stream_edit_last_response(
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    content: str,
    model_alias: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
    result: dict[str, str] | None = None,
) -> AsyncIterator[str]:
    """Replace the last user message with `content`, drop the last reply, re-run."""
    async with SessionLocal() as session:
        user = await users_repo.get_by_id(session, user_id)
        if user is None:
            raise ChatNotFoundError("User not found.")

        chat = await chats_repo.get_by_id(session, chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError("Chat not found.")

        last = await messages_repo.get_last(session, chat_id)
        if last is not None and last.role == "assistant":
            await messages_repo.delete_message(session, last)

        last_user = await messages_repo.get_last_user(session, chat_id)
        if last_user is None:
            raise ChatNotFoundError("No user message to edit.")

        await messages_repo.update_content(session, last_user, content, estimate_tokens(content))

        model = model_alias or chat.model or user.default_model
        model = routing.resolve_alias(model, content)
        meta: dict[str, int] = {}
        prompt_messages = await build_prompt_messages(
            session, user, chat_id, settings, summary=chat.summary, out=meta
        )

    reserved = estimate_tokens(content) + settings.max_output_tokens
    if not await quota_service.reserve_usage(redis, str(user_id), reserved, settings):
        raise QuotaExceededError("Daily token limit reached. Try again tomorrow.")

    ctx = _StreamContext(
        user_id=user_id,
        chat_id=chat_id,
        model=model,
        prompt_messages=prompt_messages,
        run_title=False,
        user_message_content=content,
        reserved_tokens=reserved,
        recalled_count=meta.get("recalled", 0),
    )

    try:
        async for token in _stream_and_finalize(
            redis,
            settings,
            ctx,
            should_cancel=should_cancel,
            result=result,
        ):
            yield token
    except ModelUnavailableError:
        await quota_service.refund_usage(redis, str(user_id), reserved)
        raise
    except Exception:
        await quota_service.refund_usage(redis, str(user_id), reserved)
        raise


async def _prepare_chat_turn(
    *,
    user_id: UUID,
    chat_id: UUID,
    content: str,
    model_alias: str | None,
    settings: Settings,
    reserved_tokens: int,
) -> _StreamContext:
    async with SessionLocal() as session:
        user = await users_repo.get_by_id(session, user_id)
        if user is None:
            raise ChatNotFoundError("User not found.")

        chat = await chats_repo.get_by_id(session, chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError("Chat not found.")

        model = model_alias or chat.model or user.default_model
        model = routing.resolve_alias(model, content)
        prior_count = await messages_repo.count_for_chat(session, chat_id)

        await messages_repo.create(
            session,
            chat_id=chat_id,
            user_id=user.id,
            role="user",
            content=content,
            model=model,
            input_tokens=estimate_tokens(content),
        )
        meta: dict[str, int] = {}
        prompt_messages = await build_prompt_messages(
            session, user, chat_id, settings, summary=chat.summary, out=meta
        )

        return _StreamContext(
            user_id=user_id,
            chat_id=chat_id,
            model=model,
            prompt_messages=prompt_messages,
            run_title=prior_count == 0,
            user_message_content=content,
            reserved_tokens=reserved_tokens,
            recalled_count=meta.get("recalled", 0),
        )


async def _stream_and_finalize(
    redis: Redis,
    settings: Settings,
    ctx: _StreamContext,
    *,
    should_cancel: Callable[[], bool] | None,
    result: dict[str, str] | None = None,
) -> AsyncIterator[str]:
    usage: dict[str, int] = {}
    assistant_parts: list[str] = []

    async for token in litellm_gateway.stream_chat_completion(
        settings=settings,
        model_alias=ctx.model,
        messages=ctx.prompt_messages,
        max_tokens=settings.max_output_tokens,
        usage=usage,
    ):
        if should_cancel and should_cancel():
            break
        assistant_parts.append(token)
        yield token

    assistant_text = "".join(assistant_parts).strip()
    if not assistant_text:
        await quota_service.refund_usage(redis, str(ctx.user_id), ctx.reserved_tokens)
        return

    input_tokens = usage.get("input") or sum(
        estimate_tokens(m["content"]) for m in ctx.prompt_messages
    )
    output_tokens = usage.get("output") or estimate_tokens(assistant_text)
    total_tokens = input_tokens + output_tokens

    async with SessionLocal() as session:
        assistant_message = await messages_repo.create(
            session,
            chat_id=ctx.chat_id,
            user_id=ctx.user_id,
            role="assistant",
            content=assistant_text,
            model=ctx.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        if result is not None:
            result["message_id"] = str(assistant_message.id)
            if ctx.recalled_count:
                result["recalled"] = str(ctx.recalled_count)

        chat = await chats_repo.get_by_id(session, ctx.chat_id, ctx.user_id)
        if chat is not None:
            await chats_repo.touch(session, chat)

        try:
            await usage_repo.add_tokens(
                session,
                ctx.user_id,
                utc_today(),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception:
            logger.exception("Failed to record usage tokens")

    await quota_service.adjust_usage(redis, str(ctx.user_id), ctx.reserved_tokens, total_tokens)

    await jobs.enqueue(
        redis,
        "memory",
        {
            "user_id": str(ctx.user_id),
            "chat_id": str(ctx.chat_id),
            "transcript": f"User: {ctx.user_message_content}\nAssistant: {assistant_text}",
        },
    )
    if ctx.run_title:
        await jobs.enqueue(
            redis,
            "topic",
            {
                "chat_id": str(ctx.chat_id),
                "user_message": ctx.user_message_content,
                "assistant_message": assistant_text,
            },
        )
    if settings.history_compression_enabled:
        await jobs.enqueue(redis, "compress", {"chat_id": str(ctx.chat_id)})

import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.background import memory_extraction, topic_generation
from app.background.tasks import spawn
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
from app.services.quota import utc_today

logger = logging.getLogger(__name__)

STYLE_HINTS = {
    "short": "Keep responses concise.",
    "balanced": "Use a balanced level of detail.",
    "detailed": "Provide thorough, detailed answers.",
}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class _StreamContext:
    user_id: UUID
    chat_id: UUID
    model: str
    prompt_messages: list[dict[str, str]]
    run_title: bool
    user_message_content: str
    reserved_tokens: int


async def build_prompt_messages(
    session: AsyncSession,
    user: User,
    chat_id: UUID,
    settings: Settings,
) -> list[dict[str, str]]:
    memories = await memory_service.load_relevant_memories(session, user, settings)
    memory_block = memory_service.format_memory_block(memories)
    recent = await messages_repo.list_recent(session, chat_id, limit=settings.recent_message_window)

    system_parts = [
        "You are Recall, a helpful personal AI assistant.",
        STYLE_HINTS.get(user.response_style, STYLE_HINTS["balanced"]),
    ]
    if memory_block:
        system_parts.append(memory_block)

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
        prompt_messages = await build_prompt_messages(session, user, chat_id, settings)
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
    )

    try:
        async for token in _stream_and_finalize(
            redis,
            settings,
            ctx,
            should_cancel=should_cancel,
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
        prompt_messages = await build_prompt_messages(session, user, chat_id, settings)

        return _StreamContext(
            user_id=user_id,
            chat_id=chat_id,
            model=model,
            prompt_messages=prompt_messages,
            run_title=prior_count == 0,
            user_message_content=content,
            reserved_tokens=reserved_tokens,
        )


async def _stream_and_finalize(
    redis: Redis,
    settings: Settings,
    ctx: _StreamContext,
    *,
    should_cancel: Callable[[], bool] | None,
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
        await messages_repo.create(
            session,
            chat_id=ctx.chat_id,
            user_id=ctx.user_id,
            role="assistant",
            content=assistant_text,
            model=ctx.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

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

    spawn(
        _background_memory(
            settings,
            ctx.user_id,
            ctx.chat_id,
            ctx.user_message_content,
            assistant_text,
        )
    )
    if ctx.run_title:
        spawn(
            _background_topic(settings, ctx.chat_id, ctx.user_message_content, assistant_text),
        )


async def _background_topic(
    settings: Settings,
    chat_id: UUID,
    user_message: str,
    assistant_message: str,
) -> None:
    async with SessionLocal() as session:
        await topic_generation.generate_chat_title(
            session, settings, chat_id, user_message, assistant_message
        )


async def _background_memory(
    settings: Settings,
    user_id: UUID,
    chat_id: UUID,
    user_message: str,
    assistant_message: str,
) -> None:
    async with SessionLocal() as session:
        await memory_extraction.extract_and_store_memories(
            session,
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript=f"User: {user_message}\nAssistant: {assistant_message}",
        )

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from datetime import date
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.background import memory_extraction, topic_generation
from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways import litellm_gateway
from app.models.orm import Chat, User
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.repositories import usage as usage_repo
from app.services import memory as memory_service
from app.services import quota as quota_service

logger = logging.getLogger(__name__)

STYLE_HINTS = {
    "short": "Keep responses concise.",
    "balanced": "Use a balanced level of detail.",
    "detailed": "Provide thorough, detailed answers.",
}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


async def build_prompt_messages(
    session: AsyncSession,
    user: User,
    chat_id: UUID,
    settings: Settings,
) -> list[dict[str, str]]:
    memories = await memory_service.load_relevant_memories(session, user, settings)
    memory_block = memory_service.format_memory_block(memories)
    recent = await messages_repo.list_recent(
        session, chat_id, limit=settings.recent_message_window
    )

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
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    content: str,
    model_alias: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> AsyncIterator[str]:
    estimated = estimate_tokens(content) + settings.max_output_tokens
    if not await quota_service.can_spend(redis, str(user.id), estimated, settings):
        yield "Daily token limit reached. Try again tomorrow or reduce message length."
        return

    chat = await chats_repo.get_by_id(session, chat_id, user.id)
    if chat is None:
        yield "Chat not found."
        return

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

    run_background = prior_count == 0
    async for token in _stream_assistant(
        session,
        redis,
        settings,
        user=user,
        chat_id=chat_id,
        model=model,
        should_cancel=should_cancel,
        run_background=run_background,
        chat=chat,
        # Pass content directly — avoids an extra get_last_user query
        user_message_content=content if run_background else None,
    ):
        yield token


async def stream_regenerate_response(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    model_alias: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> AsyncIterator[str]:
    chat = await chats_repo.get_by_id(session, chat_id, user.id)
    if chat is None:
        yield "Chat not found."
        return

    last = await messages_repo.get_last(session, chat_id)
    if last is None:
        yield "No messages to regenerate."
        return
    if last.role == "assistant":
        await messages_repo.delete_message(session, last)

    last_user = await messages_repo.get_last_user(session, chat_id)
    if last_user is None:
        yield "No user message to regenerate from."
        return

    model = model_alias or chat.model or user.default_model
    estimated = estimate_tokens(last_user.content) + settings.max_output_tokens
    if not await quota_service.can_spend(redis, str(user.id), estimated, settings):
        yield "Daily token limit reached. Try again tomorrow."
        return

    async for token in _stream_assistant(
        session,
        redis,
        settings,
        user=user,
        chat_id=chat_id,
        model=model,
        should_cancel=should_cancel,
        run_background=False,
        chat=chat,
    ):
        yield token



async def _stream_assistant(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    model: str,
    should_cancel: Callable[[], bool] | None,
    run_background: bool,
    chat: Chat | None = None,
    user_message_content: str | None = None,
) -> AsyncIterator[str]:
    prompt_messages = await build_prompt_messages(session, user, chat_id, settings)

    assistant_parts: list[str] = []
    async for token in litellm_gateway.stream_chat_completion(
        settings=settings,
        model_alias=model,
        messages=prompt_messages,
        max_tokens=settings.max_output_tokens,
    ):
        if should_cancel and should_cancel():
            break
        assistant_parts.append(token)
        yield token

    assistant_text = "".join(assistant_parts).strip()
    if not assistant_text:
        return

    output_tokens = estimate_tokens(assistant_text)
    input_tokens = sum(estimate_tokens(m["content"]) for m in prompt_messages)

    await messages_repo.create(
        session,
        chat_id=chat_id,
        user_id=user.id,
        role="assistant",
        content=assistant_text,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    total_tokens = input_tokens + output_tokens
    await quota_service.record_usage(redis, str(user.id), total_tokens)
    try:
        await usage_repo.add_tokens(
            session,
            user.id,
            date.today(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    except Exception:
        logger.exception("Failed to record usage tokens")

    if chat is not None:
        await chats_repo.touch(session, chat)
    elif run_background:
        chat = await chats_repo.get_by_id(session, chat_id, user.id)
        if chat:
            await chats_repo.touch(session, chat)

    if run_background:
        if user_message_content is None:
            last_user_msg = await messages_repo.get_last_user(session, chat_id)
            user_message_content = last_user_msg.content if last_user_msg else ""
        asyncio.create_task(
            _background_topic(settings, chat_id, user_message_content, assistant_text),
        )
        asyncio.create_task(
            _background_memory(settings, user.id, chat_id, user_message_content, assistant_text),
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

import asyncio
import logging
from collections.abc import Awaitable
from typing import Any, TypeVar
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.db import SessionLocal
from app.models.orm import User
from app.repositories import messages as messages_repo
from app.services import calendar as calendar_service
from app.services import email as email_service
from app.services.chat.stream_status import StreamStatusFn
from app.services.prompt_safety import wrap_untrusted

logger = logging.getLogger(__name__)

INTEGRATION_LOAD_TIMEOUT_SECONDS = 5.0

_T = TypeVar("_T")


async def _timed_integration_load(label: str, coro: Awaitable[_T]) -> _T | None:
    try:
        return await asyncio.wait_for(coro, timeout=INTEGRATION_LOAD_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning("%s integration load timed out", label)
        return None
    except Exception:
        logger.exception("%s integration load failed", label)
        return None


async def _load_calendar_prompt_block(
    user: User,
    redis: Redis,
    settings: Settings,
    *,
    cache_only: bool,
) -> str | None:
    async with SessionLocal() as session:
        return await calendar_service.load_calendar_for_prompt(
            session,
            redis,
            user,
            settings,
            cache_only=cache_only,
        )


async def _load_gmail_prompt_block(
    user: User,
    redis: Redis,
    settings: Settings,
) -> str | None:
    async with SessionLocal() as session:
        return await email_service.load_gmail_for_prompt(session, redis, user, settings)


async def _load_gmail_context_block(
    user: User,
    redis: Redis,
    settings: Settings,
) -> tuple[str, list[Any], list[Any], str | None] | None:
    async with SessionLocal() as session:
        return await email_service.load_gmail_context(session, redis, user, settings)


async def _load_prior_user_messages(chat_id: UUID) -> list[str]:
    async with SessionLocal() as session:
        return await messages_repo.recent_user_contents(session, chat_id)


async def _load_has_calendar_write(user_id: UUID) -> bool:
    async with SessionLocal() as session:
        return await calendar_service.has_write_access(session, user_id)


async def _load_gmail_context_if_needed(
    content: str,
    user: User,
    redis: Redis,
    settings: Settings,
    *,
    instant_reply: str | None,
    on_status: StreamStatusFn | None,
) -> tuple[str, list[Any], list[Any], str | None] | None:
    """Prefetch inbox context for external email asks (even if injection is later skipped)."""
    if instant_reply is not None:
        return None
    if not email_service.is_external_email_question(content):
        return None
    async with SessionLocal() as session:
        connected = await email_service.is_connected(session, user.id)
    if not connected:
        return None
    if on_status is not None:
        await on_status("checking_inbox")
    return await _timed_integration_load(
        "gmail_prefetch",
        _load_gmail_context_block(user, redis, settings),
    )


async def _inject_integration_blocks(
    prompt_messages: list[dict[str, str]],
    content: str,
    user: User,
    redis: Redis,
    settings: Settings,
    *,
    instant_reply: str | None,
    lightweight: bool,
    minimal_personal: bool,
    minimal_quiz: bool,
    day_reflection: bool,
    has_calendar_write: bool,
    gmail_context: tuple[str, list[Any], list[Any], str | None] | None,
    on_status: StreamStatusFn | None,
) -> list[dict[str, str]]:
    """Load calendar/gmail blocks (best-effort) and append to the system message."""
    if instant_reply is not None or minimal_personal or minimal_quiz or lightweight:
        return prompt_messages

    integration_blocks: list[str] = []
    load_calendar = calendar_service.should_inject_calendar_block(content)
    load_gmail = email_service.should_inject_gmail_block(content)
    calendar_block: str | None = None
    gmail_block: str | None = None

    pending: list[tuple[str, Awaitable[str | None]]] = []
    if load_calendar:
        if on_status is not None:
            await on_status("loading_calendar")
        pending.append(
            (
                "calendar",
                _timed_integration_load(
                    "calendar",
                    _load_calendar_prompt_block(
                        user,
                        redis,
                        settings,
                        cache_only=day_reflection,
                    ),
                ),
            )
        )
    if gmail_context is not None:
        google_email, messages, pending_suggestions, fetch_error = gmail_context
        gmail_block = email_service.format_gmail_block(
            google_email=google_email,
            messages=messages,
            pending_suggestions=pending_suggestions,
            fetch_error=fetch_error,
        )
    elif load_gmail:
        if on_status is not None:
            await on_status("checking_inbox")
        pending.append(
            (
                "gmail",
                _timed_integration_load(
                    "gmail",
                    _load_gmail_prompt_block(user, redis, settings),
                ),
            )
        )

    if pending:
        results = await asyncio.gather(*(task for _, task in pending))
        for (label, _), result in zip(pending, results, strict=True):
            if label == "calendar":
                calendar_block = result
            elif label == "gmail":
                gmail_block = result

    if calendar_block:
        integration_blocks.append(wrap_untrusted("calendar", calendar_block))
    if gmail_block:
        integration_blocks.append(wrap_untrusted("gmail", gmail_block))
        if email_service.is_external_email_question(content):
            integration_blocks.append(email_service.GMAIL_INBOX_ANSWER_HINT)
    if (
        not settings.mcp_tools_enabled
        and calendar_service.is_calendar_create_request(content)
        and has_calendar_write
    ):
        integration_blocks.append(calendar_service.CALENDAR_WRITE_HINT)
    if integration_blocks:
        prompt_messages[0] = {
            "role": "system",
            "content": f"{prompt_messages[0]['content']}\n\n" + "\n\n".join(integration_blocks),
        }
    return prompt_messages

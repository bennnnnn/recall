import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any
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
from app.services.quota import QUOTA_EXCEEDED_MESSAGE, utc_today

logger = logging.getLogger(__name__)

CLARIFICATION_HINT = (
    "When you lack information needed to complete a task correctly, ask concise clarifying "
    "questions instead of guessing, inventing details, or filling gaps with placeholders. "
    "Never use bracket placeholders like [name], [topic], or [TBD]. Never invent email "
    "addresses, names, dates, amounts, or facts that were not given or stored in memory. "
    "If the user has not given enough context for a send-ready draft (email, message, reply, "
    "etc.), ask 1-3 specific questions first and do not include a copy/send fence until you "
    "have what you need. Use known facts from memory when available; if memory does not "
    "cover something, ask — never assume."
)

COPY_DELIVERABLE_HINT = (
    "When drafting text the user will copy and send (SMS, text message, email, reply, "
    "caption, social post, etc.), put ONLY the final send-ready wording inside a fenced "
    "code block with a language tag: ```email, ```message, ```sms, ```twitter, ```linkedin, "
    "or ```copy. "
    "Use at most ONE sendable fence per response (e.g. ```email only — never a second ```copy "
    "for the same draft). "
    "Copy blocks must be ready to paste and send as-is: complete sentences, real names and "
    "subjects from context or memory — never [placeholders], TBD, or fill-in-the-blank "
    "templates. If you do not have enough detail to write that, ask clarifying questions "
    "outside the block and skip the copy fence until you have what you need. "
    "Never wrap assistant notes, disclaimers, caveats, or follow-ups in ```copy — write those "
    "as plain text or a > [!NOTE] callout after the deliverable. "
    "Never use ```copy or ```text for explanations, tutorials, markdown notes, advice, "
    "recommendations, comparisons, or blockquotes (lines starting with >) — only for "
    "text the user will paste and send (email body, SMS, caption, etc.). "
    "Use > [!NOTE] or a normal blockquote for tips and notes, not a copy fence. "
    "For emails include To:/Subject: lines when known from the user or memory; omit To if "
    "unknown rather than guessing an address. "
    "Use ```compare for pros/cons, ```kv for key-value summaries, ```steps for step-by-step "
    "instructions, and GitHub callouts like > [!TIP]. Keep explanations and questions outside "
    "copy blocks."
)

INTENT_FORMAT_HINT = (
    "Match output structure to what the user is trying to do:\n"
    "1) Writing/editing (email, rewrite, tone change): one-line summary, then ```email / "
    "```message / ```copy with the final text only; optional 2-3 numbered revision notes "
    "after (not inside the fence).\n"
    "2) How-to / troubleshooting: ## Goal, then numbered ```steps (1. …\\n2. …), then "
    "> [!TIP] for one pitfall and > [!NOTE] if a step needs a warning.\n"
    "3) Explain / learn / summarize: ## Short answer (1-2 sentences), ## Key points "
    "(bullets), optional ```kv for facts; use ## Example only when it clarifies.\n"
    "4) Decision / compare (X vs Y, which to pick): pipe table when ≥3 attributes, else "
    "```compare or Pros/Cons bullets; end with ## Recommendation (one clear pick + why).\n"
    "5) Planning (trip, meal, study, week): ## Overview, then day-by-day or phase "
    "numbered list; use a pipe table for schedules with times/columns.\n"
    "6) Coding / work: brief ## Approach, then tagged code fence (```python etc.), then "
    "## Notes bullets (edge cases, how to run) — never bury code in prose.\n"
    "7) Creative (ideas, names, stories): numbered list of options (5-10), each 1-2 lines; "
    "using ### headings if grouping by theme.\n"
    "8) Personal / emotional: short empathetic opener (1 sentence), ## What I'm hearing "
    "bullets — task execution or lookup, "
    "```copy — no lectures.\\n"
    "9) Lookup / facts / recommendations: ```kv or bullets first; pipe table if comparing "
    "≥3 items; one-line source/caveat in > [!NOTE] when uncertain.\n"
    "10) Task execution (send, remind, research): ## Done / ## Next if acting; numbered "
    "checklist for multi-step tasks; ask clarifying questions (numbered) before executing "
    "when details are missing.\n"
    "Default when intent is unclear: short opener + bullets, not paragraphs."
)

RESPONSE_FORMAT_HINT = (
    "Format for readability — avoid long prose paragraphs. Prefer scannable structure:\n"
    "- One short opening line at most, then bullets, headings (##), or a ```kv block "
    "(Capital: …\\nPopulation: …\\nLanguage: …).\n"
    "- When the user asks for a table or tabular data, use ONLY GitHub-Flavored Markdown "
    "pipe tables — every row must start and end with |, with a single | --- | separator "
    "row after the header.\n"
    "  WRONG — do not do this: lines of dashes/underscores between rows (---, ___, "
    "====), ASCII box-drawing (+---+), or columns separated only by spaces.\n"
    "  WRONG:\\n"
    "  Method | Speed\\n"
    "  ---\\n"
    "  Slicing | Fast\\n"
    "  RIGHT:\\n"
    "  | Method | Speed |\\n"
    "  | --- | --- |\\n"
    "  | Slicing | Fast |\\n"
    "  Example:\\n"
    "  | Country | Population |\\n"
    "  | --- | --- |\\n"
    "  | Ethiopia | ~120M |\\n"
    "  Never put tables inside ``` code fences. Never insert blank, dash-only, or "
    "underscore-only rows between data rows.\n"
    "- Use markdown pipe tables when comparing several items with the same columns "
    "(methods, pros/cons, features, etc.).\n"
    "- For a single place, person, or topic ('tell me about X'), use a ```kv block or "
    "bullets under 2-3 short headings — not a wall of text.\n"
    "- Use > [!NOTE] callouts for one standout fact or caveat.\n"
    "- Keep paragraphs to 1-2 sentences only when bullets or kv would not work.\n"
    "- For source code, always use fenced blocks with the **correct** language tag on the "
    "first line (```python, ```java, ```c, ```cpp, ```javascript, ```typescript, ```bash, "
    "etc.) — never ```text, never the wrong language, never untagged code fences."
)

STYLE_HINTS = {
    "short": "Keep responses concise and structured — bullets over paragraphs.",
    "balanced": "Use a balanced level of detail with headings and bullets, not long prose.",
    "detailed": (
        "Be thorough but stay scannable: sections, bullets, tables, "
        "and ```kv blocks — not essay-style paragraphs."
    ),
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
    memory_hints: list[str] = field(default_factory=list)


async def build_prompt_messages(
    session: AsyncSession,
    user: User,
    chat_id: UUID,
    settings: Settings,
    *,
    summary: str | None = None,
    out: dict[str, object] | None = None,
) -> list[dict[str, str]]:
    memory_block = await memory_service.get_memory_block(session, user, settings)
    if out is not None:
        bullets = [line[2:].strip() for line in memory_block.split("\n") if line.startswith("- ")]
        out["recalled"] = len(bullets)
        out["memory_hints"] = bullets[:3]
    recent_all = await messages_repo.list_recent(
        session, chat_id, limit=settings.recent_message_window
    )
    keep = select_recent_window(
        recent_all, settings.context_token_budget, settings.recent_message_window
    )
    recent = recent_all[-keep:] if keep else []

    system_parts: list[str] = [
        "You are Recall, a helpful personal AI assistant.",
        STYLE_HINTS.get(user.response_style, STYLE_HINTS["balanced"]),
        CLARIFICATION_HINT,
        INTENT_FORMAT_HINT,
        RESPONSE_FORMAT_HINT,
        COPY_DELIVERABLE_HINT,
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
    result: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    reserved = estimate_tokens(content) + settings.max_output_tokens
    if not await quota_service.reserve_usage(redis, str(user_id), reserved, settings):
        raise QuotaExceededError(QUOTA_EXCEEDED_MESSAGE)

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
    result: dict[str, Any] | None = None,
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
        meta: dict[str, Any] = {}
        prompt_messages = await build_prompt_messages(
            session, user, chat_id, settings, summary=chat.summary, out=meta
        )
        user_message_content = last_user.content

    reserved = estimate_tokens(user_message_content) + settings.max_output_tokens
    if not await quota_service.reserve_usage(redis, str(user_id), reserved, settings):
        raise QuotaExceededError(QUOTA_EXCEEDED_MESSAGE)

    ctx = _StreamContext(
        user_id=user_id,
        chat_id=chat_id,
        model=model,
        prompt_messages=prompt_messages,
        run_title=False,
        user_message_content=user_message_content,
        reserved_tokens=reserved,
        recalled_count=int(meta.get("recalled") or 0),
        memory_hints=list(meta.get("memory_hints") or []),
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
        meta: dict[str, Any] = {}
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
            recalled_count=int(meta.get("recalled") or 0),
            memory_hints=list(meta.get("memory_hints") or []),
        )


async def _finalize_stream_turn(
    redis: Redis,
    settings: Settings,
    ctx: _StreamContext,
    assistant_text: str,
    usage: dict[str, int],
    result: dict[str, Any] | None,
) -> None:
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
            if ctx.memory_hints:
                result["memory_hints"] = json.dumps(ctx.memory_hints)

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


async def _stream_and_finalize(
    redis: Redis,
    settings: Settings,
    ctx: _StreamContext,
    *,
    should_cancel: Callable[[], bool] | None,
    result: dict[str, Any] | None = None,
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

    finalize_task = asyncio.create_task(
        _finalize_stream_turn(redis, settings, ctx, assistant_text, usage, result),
    )
    if result is not None:
        result["_finalize_task"] = finalize_task

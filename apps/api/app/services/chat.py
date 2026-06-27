import asyncio
import json
import logging
import random
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
    "When drafting text the user will copy and send (SMS, email, reply, caption, "
    "social post, etc.), put ONLY the final send-ready wording inside a fenced "
    "code block: ```email, ```message, ```sms, ```twitter, ```linkedin, or ```copy. "
    "Use at most ONE such fence per response. "
    "Copy blocks must be ready to paste and send as-is: complete sentences, real names "
    "and subjects from context or memory — never [placeholders] or TBD. If you lack "
    "details, ask clarifying questions instead and skip the copy fence. "
    "Never use ```copy or ```text for explanations, notes, advice, or comparisons — "
    "those belong in plain text or bullets. "
    "For emails include To:/Subject: lines when known; omit To if unknown rather than "
    "guessing an address."
)

INTENT_FORMAT_HINT = (
    "Adapt your output to the user's goal. Be direct and natural — not every answer "
    "needs a table or a special format.\n"
    "\n"
    "Default (facts, lists, rankings, lookups, recommendations):\n"
    "  - Use a simple **numbered list** or **bullets** for most answers. "
    "This is the right format for rankings (\"top N …\"), lists of facts, "
    "recommendations, pros/cons, and general Q&A.\n"
    "  - Only use a pipe table when the user explicitly asks for a table, or "
    "when comparing 4+ items across 3+ clear columns where a table is genuinely "
    "easier to read than a list.\n"
    "  - For a single topic (\"tell me about X\"), use 2-3 short headings with "
    "bullets — not a wall of text and not a kv block.\n"
    "\n"
    "Writing helper (email, message, reply, caption, social post):\n"
    "  - Put the final send-ready text inside ```email, ```message, ```sms, or "
    "```copy. At most ONE such fence per response. Skip the fence if you lack "
    "details — ask questions instead.\n"
    "\n"
    "How-to / troubleshooting:\n"
    "  - Numbered steps (1. … 2. …). Add a brief tip or warning only when needed.\n"
    "\n"
    "Coding:\n"
    "  - Brief approach sentence, then tagged code fence (```python, etc.), "
    "then notes.\n"
    "\n"
    "Decision / compare (X vs Y):\n"
    "  - Bullets for each side, then a clear recommendation.\n"
    "  - Use a table only when asked or when there are many structured attributes."
)

RESPONSE_FORMAT_HINT = (
    "Be scannable — avoid long prose paragraphs:\n"
    "- Prefer **numbered lists** for rankings, steps, and ordered information. "
    "Prefer **bullets** for unordered facts, key points, and options.\n"
    "- Use pipe tables ONLY when the user asks for a table, or when comparing "
    "4+ items across 3+ structured columns where a table is genuinely clearer "
    "than a list. Most comparisons are fine as bullets.\n"
    "- When you do use pipe tables: use proper GFM format — every row starts "
    "and ends with |, one |---| separator row after the header. Never put "
    "tables inside ``` fences. Never insert dash-only or blank rows between data rows.\n"
    "- Keep paragraphs to 1-2 sentences. Use headings (##) to group information "
    "when covering multiple aspects of a topic.\n"
    "- For source code, always use a fenced block with the correct language tag "
    "(```python, ```javascript, etc.)."
)

VISUALIZATION_HINTS = (
    "IMPORTANT — You CAN and SHOULD generate visual content using fenced blocks. "
    "The app renders these natively. Never say you can't render something — output "
    "the code in the correct fence and the app handles rendering.\n\n"
    "**HTML UI** (```html) — RULE: When a user asks for a UI, page, form, card, "
    "layout, login screen, dashboard, or any styled visual design, you MUST output "
    "it inside a ```html fence block. Include a <style> block with CSS. Do NOT "
    "describe what it looks like — output the actual HTML code. The app renders "
    "HTML natively with full CSS support. Use for: styled forms, login pages, "
    "dashboards, cards, grids, landing pages, email templates, comparison layouts, "
    "and any rich visual content markdown can't express.\n\n"
    "**Mermaid diagrams** (```mermaid) — RULE: When explaining a process, workflow, "
    "architecture, relationship, or decision tree, use a mermaid diagram. The app "
    "renders these as vector graphics. Use flowchart/sequence/class/gantt/erd/mindmap. "
    "Prefer a diagram over a bullet list when showing how things connect.\n\n"
    "**Charts** (```chart) — RULE: When comparing numeric data, showing trends, or "
    "visualizing statistics, output a Vega-Lite JSON spec in a ```chart fence. "
    "Format: {\"mark\": \"bar\"|\"line\"|\"point\", \"data\": {\"values\": [...]}, "
    "\"encoding\": {\"x\": {...}, \"y\": {...}}}. Use when a chart is clearer than a table.\n\n"
    "CRITICAL: Never say \"I can't render\" or \"save this as a file\" or \"open in a browser.\" "
    "The app renders these formats. Just output the code in the correct fence block."
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
        VISUALIZATION_HINTS,
        COPY_DELIVERABLE_HINT,
    ]
    if user.custom_instructions:
        system_parts.append(
            f"User-specified instructions (follow these above general formatting "
            f"guidance):\n{user.custom_instructions}"
        )
    if user.locale and user.locale != "en":
        system_parts.append(
            f"The user's preferred language is {user.locale}. "
            f"Respond in {user.locale} unless the user writes in another language."
        )
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
    input_tokens = (
        usage.get("input")
        if usage.get("input") is not None
        else sum(estimate_tokens(m["content"]) for m in ctx.prompt_messages)
    )
    output_tokens = (
        usage.get("output")
        if usage.get("output") is not None
        else estimate_tokens(assistant_text)
    )
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

        await chats_repo.touch_by_id(session, ctx.chat_id)

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
    # Regenerate proactive suggestions ~10% of turns.
    if random.random() < 0.1:
        await jobs.enqueue(redis, "suggestions", {"user_id": str(ctx.user_id)})


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
    # Prevent silent failures — log any exception in the background finalization.
    finalize_task.add_done_callback(
        lambda t: logger.exception("Background finalization failed", exc_info=t.exception())
        if t.exception()
        else None
    )
    if result is not None:
        result["_finalize_task"] = finalize_task

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways.web_search_gateway import WebSearchHit
from app.models.math_schemas import MathImageExtract
from app.models.orm import Chat, User
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.services import calendar as calendar_service
from app.services import chat_tools as chat_tools_service
from app.services import email as email_service
from app.services import locale as locale_service
from app.services import math_tools as math_tools_service
from app.services import memory as memory_service
from app.services import profile as profile_service
from app.services import projects as projects_service
from app.services import response_tone as response_tone_service
from app.services import time_context as time_context_service
from app.services import todos as todos_service
from app.services import web_search as web_search_service
from app.services.chat.prompt_constants import (
    BROAD_SELF_ANSWER_HINT,
    CLARIFICATION_HINT,
    COMPARISON_FORMAT_HINT,
    COPY_DELIVERABLE_HINT,
    DAY_LEARNING_SNAPSHOT_HINT,
    DAY_PLANNING_ANSWER_HINT,
    EMAIL_DRAFT_HINT,
    INTENT_FORMAT_HINT,
    LIGHTWEIGHT_REPLY_HINT,
    MATH_SOLVER_HINT,
    PRIVACY_HINT,
    QUIZ_ANSWER_HINT,
    QUIZ_RECENT_MESSAGE_LIMIT,
    RESPONSE_FORMAT_HINT,
    SHORT_MATH_SAFETY_HINT,
    SHORT_RESPONSE_FORMAT_HINT,
    STYLE_HINTS,
    VISUALIZATION_HINTS,
    VOCAB_CHAT_ANSWER_HINT,
    format_quiz_grading_hint,
    is_comparison_question,
    is_writing_deliverable_request,
)
from app.services.chat.stream_status import StreamStatusFn
from app.services.context_window import select_recent_window
from app.services.day_planning import is_day_planning_question, is_day_reflection_question
from app.services.math_tools import VerifiedMathBlock
from app.services.prompt_inject import inject_before_last_user
from app.services.prompt_safety import wrap_persisted_attachment_excerpts, wrap_untrusted
from app.services.vocab_quiz import QuizAnswerGrade

logger = logging.getLogger(__name__)

StreamReasoningFn = Callable[[str], Awaitable[None]]

# Account email is PII — only inject when the turn clearly needs it.
_PROFILE_EMAIL_ASK = re.compile(
    r"\b("
    r"what(?:'s| is) my (?:e-?mail|email address)|"
    r"remind me (?:of |what )?my (?:e-?mail|email)|"
    r"(?:tell|show|give) me my (?:e-?mail|email address)"
    r")\b",
    re.IGNORECASE,
)


def should_include_profile_email(query_text: str | None) -> bool:
    """True when the turn needs the account email (ask / draft / inbox / tools)."""
    cleaned = (query_text or "").strip()
    if not cleaned:
        return False
    if _PROFILE_EMAIL_ASK.search(cleaned):
        return True
    if is_writing_deliverable_request(cleaned):
        return True
    if email_service.should_inject_gmail_block(cleaned):
        return True
    return False


def format_user_profile_block(
    user: User,
    *,
    location_override: str | None = None,
    include_email: bool = False,
) -> str:
    """Basic identity — injected into every chat prompt."""
    lines = [
        "User profile (internal — from their account; do not quote email or location "
        "unless they explicitly ask for those details):"
    ]
    if user.name and user.name.strip():
        lines.append(f"- Name: {user.name.strip()}")
    if include_email and user.email and user.email.strip():
        lines.append(f"- Email: {user.email.strip()}")
    plan = (getattr(user, "plan", None) or "free").strip().lower()
    if plan not in {"free", "pro"}:
        plan = "free"
    lines.append(f"- Plan: {plan}")
    if user.age is not None:
        lines.append(f"- Age: {user.age}")
    if user.country and user.country.strip():
        lines.append(f"- Country: {user.country.strip()}")
    if user.job and user.job.strip():
        lines.append(f"- Job: {user.job.strip()}")
    location = location_override or profile_service.user_location_label(user)
    if location:
        lines.append(f"- Location: {location}")
    lines.append(
        "Share profile fields only when the user asks for that specific field — never recite "
        "email or location in a general 'who am I' answer. Do not say their name is missing "
        "from memory if it is listed here."
    )
    return "\n".join(lines)


def format_user_name_only_block(user: User) -> str:
    """First name only — for broad 'who am I' turns without leaking other profile fields."""
    name = (user.name or "").strip()
    if not name:
        return (
            "User name is not on file — for a 'who am I' reply, say you don't have their name yet "
            "without inventing one."
        )
    first = name.split()[0]
    return f"User's first name (for a 'who am I' reply — use this name only): {first}"


async def _augment_web_and_tools(
    prompt_messages: list[dict[str, str]],
    user_content: str,
    settings: Settings,
    *,
    user_timezone: str | None = None,
    user_location: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    prior_user_messages: list[str] | None = None,
    has_image_attachment: bool = False,
    image_math_extract: MathImageExtract | None = None,
    on_status: StreamStatusFn | None = None,
    user: User | None = None,
    redis: Redis | None = None,
    has_calendar_write: bool = False,
) -> tuple[list[dict[str, str]], list[WebSearchHit], VerifiedMathBlock | None]:
    """Web search always uses the full direct path; MCP handles calendar hints.

    Web search (network) and SymPy (subprocess) are independent — gather both
    against the same base messages, then inject blocks in the historical order
    web → MCP calendar → math so prompt shape stays stable.
    """
    # Model-initiated tool loop owns web_search + sympy when enabled — skip
    # heuristic pre-fetch so we don't double-search / double-solve.
    if settings.mcp_tool_loop_enabled:
        return prompt_messages, [], None

    if (
        settings.math_tools_enabled
        and math_tools_service.needs_symbolic_math(
            user_content, has_image_attachment=has_image_attachment
        )
        and on_status is not None
    ):
        await on_status("calculating")

    (web_block, search_sources), (math_block, verified_math) = await asyncio.gather(
        web_search_service.build_search_augmentation(
            user_content,
            settings,
            messages=prompt_messages,
            user_timezone=user_timezone,
            user_location=user_location,
            latitude=latitude,
            longitude=longitude,
            prior_user_messages=prior_user_messages,
            on_status=on_status,
            user=user,
            redis=redis,
        ),
        math_tools_service.build_math_augmentation(
            user_content,
            settings,
            has_image_attachment=has_image_attachment,
            image_math_extract=image_math_extract,
        ),
    )

    updated = prompt_messages
    if web_block:
        updated = inject_before_last_user(updated, web_block)

    if settings.mcp_tools_enabled:
        updated = await chat_tools_service.augment_prompt_with_mcp_tools(
            updated,
            user_content,
            settings,
            user_timezone=user_timezone,
            user_location=user_location,
            prior_user_messages=prior_user_messages,
            on_status=on_status,
            has_calendar_write=has_calendar_write,
        )

    if math_block:
        updated = inject_before_last_user(updated, math_block)
    return updated, search_sources, verified_math


@dataclass
class _PromptContextBlocks:
    memory_block: str
    todos_section: str | None
    projects_block: str
    recent_all: list[Any]
    attachment_rag_block: str
    chat: Chat | None


async def _load_context_blocks(
    user: User,
    chat_id: UUID,
    settings: Settings,
    *,
    chat: Chat | None,
    query_text: str | None,
    recent_limit: int,
    is_day_plan: bool,
    slim_context: bool,
    client_timezone: str | None,
    out: dict[str, object] | None,
    on_status: StreamStatusFn | None,
) -> _PromptContextBlocks:
    """Load memory/todos/projects/RAG + recent messages for the system prompt.

    Each gather branch opens a short-lived session so external HTTP (RAG/memory
    embed) cannot pin a caller's connection across the concurrent load.
    """
    if slim_context:
        async with SessionLocal() as s:
            recent_all = await messages_repo.list_recent(s, chat_id, limit=recent_limit)
        if out is not None:
            out["recalled"] = 0
            out["memory_hints"] = []
        return _PromptContextBlocks(
            memory_block="",
            todos_section=None,
            projects_block="",
            recent_all=recent_all,
            attachment_rag_block="",
            chat=chat,
        )

    if chat is None:
        async with SessionLocal() as s:
            chat = await chats_repo.get_by_id(s, chat_id, user.id)

    if on_status is not None and user.memory_enabled:
        await on_status("remembering")

    # Each of these is an independent read with no dependency on the others'
    # output — give each its own short-lived session (a single AsyncSession
    # cannot safely run concurrent operations) and gather them, instead of
    # awaiting four DB round-trips back-to-back before the LLM call starts.
    # Cap concurrent DB checkouts so one turn cannot saturate the pool.
    db_slots = asyncio.Semaphore(max(1, settings.context_db_concurrency))

    async def _memory_block() -> str:
        async with db_slots, SessionLocal() as s:
            return await memory_service.get_memory_block(
                s,
                user,
                settings,
                query_text=query_text,
                chat_project_id=chat.project_id if chat is not None else None,
            )

    async def _todos_section() -> str | None:
        async with db_slots, SessionLocal() as s:
            return await todos_service.build_todos_system_section(
                s,
                user,
                settings,
                client_timezone=client_timezone,
                query_text=query_text,
            )

    async def _projects_block() -> str:
        async with db_slots, SessionLocal() as s:
            if is_day_plan:
                return await projects_service.load_daily_learning_summary_for_prompt(
                    s,
                    user,
                    settings,
                    client_timezone=client_timezone,
                )
            if chat and chat.project_id:
                return await projects_service.load_project_for_prompt(
                    s,
                    user.id,
                    chat.project_id,
                    settings,
                    quiz_mode=getattr(chat, "quiz_mode", None),
                    client_timezone=client_timezone,
                )
            return await projects_service.load_projects_for_prompt(s, user.id, settings)

    async def _attachment_rag_block() -> str:
        # HTTP/embed-bound — do not hold a DB pool slot.
        if not settings.attachment_rag_enabled or not query_text:
            return ""
        from app.services import attachment_rag as attachment_rag_service

        return await attachment_rag_service.retrieve_for_prompt(
            settings,
            user_id=user.id,
            chat_id=chat_id,
            query=query_text,
        )

    async def _recent_messages() -> list[Any]:
        # Own session so the caller's connection is not pinned across the gather
        # (RAG embed / memory embed can take seconds).
        async with db_slots, SessionLocal() as s:
            return await messages_repo.list_recent(s, chat_id, limit=recent_limit)

    (
        memory_block,
        todos_section,
        projects_block,
        recent_all,
        attachment_rag_block,
    ) = await asyncio.gather(
        _memory_block(),
        _todos_section(),
        _projects_block(),
        _recent_messages(),
        _attachment_rag_block(),
    )
    if out is not None:
        labels = set(memory_service.SECTION_LABELS.values())
        hints = [
            line[3:].strip()
            for line in memory_block.split("\n")
            if line.startswith("## ") and line[3:].strip() in labels
        ]
        out["recalled"] = len(hints)
        out["memory_hints"] = hints[:3]
    return _PromptContextBlocks(
        memory_block=memory_block,
        todos_section=todos_section,
        projects_block=projects_block,
        recent_all=recent_all,
        attachment_rag_block=attachment_rag_block,
        chat=chat,
    )


async def _quiz_hints(
    user: User,
    chat_id: UUID,
    settings: Settings,
    *,
    chat: Chat | None,
    quiz_grade: QuizAnswerGrade | None,
    minimal_quiz_context: bool,
    minimal_vocab_answer_context: bool,
) -> tuple[list[str], Chat | None]:
    """Quiz grading + minimal quiz/vocab answer system hints (and project quiz context)."""
    parts: list[str] = []
    if quiz_grade is not None:
        parts.append(
            format_quiz_grading_hint(
                is_correct=quiz_grade.is_correct,
                user_letter=quiz_grade.user_letter,
                correct_letter=quiz_grade.correct_letter,
                word=quiz_grade.word,
                quiz_type=quiz_grade.quiz_type,
                question=quiz_grade.question,
                attempt=quiz_grade.attempt,
                tries_exhausted=quiz_grade.tries_exhausted,
            )
        )
    needs_project_ctx = (minimal_quiz_context or minimal_vocab_answer_context) and (
        chat is None or chat.project_id is not None
    )
    if minimal_quiz_context:
        parts.extend([QUIZ_ANSWER_HINT, PRIVACY_HINT])
    elif minimal_vocab_answer_context:
        parts.extend([VOCAB_CHAT_ANSWER_HINT, PRIVACY_HINT])
    else:
        return parts, chat

    if needs_project_ctx:
        async with SessionLocal() as session:
            if chat is None:
                chat = await chats_repo.get_by_id(session, chat_id, user.id)
            if chat and chat.project_id:
                quiz_ctx = await projects_service.load_project_quiz_context(
                    session, user.id, chat.project_id, settings, quiz_grade=quiz_grade
                )
                if quiz_ctx:
                    parts.append(quiz_ctx)
    return parts, chat


def _style_format_hints(
    *,
    query_text: str | None,
    style: str,
    is_day_plan: bool,
    minimal_personal_context: bool,
) -> list[str]:
    """Clarification / day-planning / response-format hints for non-quiz turns."""
    parts: list[str] = [CLARIFICATION_HINT, PRIVACY_HINT]
    if query_text and is_day_planning_question(query_text):
        parts.append(DAY_PLANNING_ANSWER_HINT)
        parts.append(DAY_LEARNING_SNAPSHOT_HINT)
        if is_day_reflection_question(query_text):
            parts.append(
                "This is an end-of-day reflection — keep reminders, lists, calendar, and "
                "loose ends as the main focus."
            )
    if minimal_personal_context:
        parts.append(BROAD_SELF_ANSWER_HINT)
    if style == "short":
        parts.append(SHORT_RESPONSE_FORMAT_HINT)
        parts.append(SHORT_MATH_SAFETY_HINT)
    elif not is_day_plan:
        parts.extend(
            [INTENT_FORMAT_HINT, MATH_SOLVER_HINT, RESPONSE_FORMAT_HINT, VISUALIZATION_HINTS]
        )
    else:
        parts.append(RESPONSE_FORMAT_HINT)
    # Turn-specific: overrides soft format map (and short-mode "no tables") for X vs Y.
    if query_text and is_comparison_question(query_text):
        parts.append(COMPARISON_FORMAT_HINT)
    parts.append(COPY_DELIVERABLE_HINT)
    if query_text and is_writing_deliverable_request(query_text):
        parts.append(EMAIL_DRAFT_HINT)
    return parts


def _integration_hints(
    *,
    settings: Settings,
    query_text: str | None,
    local_tz: str,
    user_locale: str | None,
    location_for_context: str | None,
    prompt_location: str | None,
    memory_block: str,
    attachment_rag_block: str,
    todos_section: str | None,
    todo_sync_feedback: str | None,
    is_day_plan: bool,
    projects_block: str,
    summary: str | None,
) -> list[str]:
    """Time / web / calendar / gmail / memory / todos / projects / summary hints."""
    parts: list[str] = [
        time_context_service.format_time_context(local_tz, user_locale, location_for_context)
    ]
    if settings.web_search_enabled:
        parts.append(web_search_service.WEB_SEARCH_HINT)
        if query_text and web_search_service.is_ambiguous_local_places_query(query_text):
            parts.append(web_search_service.AMBIGUOUS_NEARBY_HINT)
        elif query_text and web_search_service.is_places_list_query(query_text):
            parts.append(web_search_service.LOCAL_PLACES_FORMAT_HINT)
        elif query_text and web_search_service.is_distance_query(query_text):
            parts.append(web_search_service.GEO_DISTANCE_HINT)
        if prompt_location and query_text and web_search_service.is_geo_query(query_text):
            parts.append(web_search_service.GEO_ACTIVE_LOCATION_HINT)
    if settings.google_calendar_enabled:
        parts.append(calendar_service.CALENDAR_HINT)
    if settings.gmail_enabled:
        parts.append(email_service.GMAIL_HINT)
    if memory_block:
        parts.append(wrap_untrusted("memory", memory_block, first_party=True))
    if attachment_rag_block:
        parts.append(attachment_rag_block)
    if todos_section:
        parts.append(todos_section)
    if todo_sync_feedback:
        parts.append(todo_sync_feedback)
    if not is_day_plan:
        parts.append(projects_service.PROJECT_HINT)
    if projects_block:
        parts.append(projects_block)
    if summary:
        parts.append(
            wrap_untrusted("conversation summary", f"Summary of earlier conversation:\n{summary}")
        )
    return parts


async def build_prompt_messages(
    user: User,
    chat_id: UUID,
    settings: Settings,
    *,
    summary: str | None = None,
    chat: Chat | None = None,
    out: dict[str, object] | None = None,
    query_text: str | None = None,
    minimal_personal_context: bool = False,
    minimal_quiz_context: bool = False,
    minimal_vocab_answer_context: bool = False,
    lightweight: bool = False,
    rich_context: bool = True,
    quiz_grade: QuizAnswerGrade | None = None,
    client_timezone: str | None = None,
    prompt_location: str | None = None,
    todo_sync_feedback: str | None = None,
    on_status: StreamStatusFn | None = None,
    omit_message_ids: set[UUID] | None = None,
) -> list[dict[str, str]]:
    """Assemble system + recent messages for a chat turn.

    Context loading uses short-lived sessions so embeds cannot pin a caller
    connection across the concurrent gather.
    """
    recent_limit = (
        QUIZ_RECENT_MESSAGE_LIMIT
        if minimal_quiz_context or minimal_vocab_answer_context
        else settings.recent_message_window
    )
    # Opt-in rich context: casual chat skips memory embed / todos / projects.
    # ``lightweight`` is only the ultra-brief social reply style (hi/thanks).
    is_day_plan = bool(query_text and is_day_planning_question(query_text))
    slim_context = (
        minimal_personal_context
        or minimal_quiz_context
        or minimal_vocab_answer_context
        or lightweight
        or not rich_context
    )
    blocks = await _load_context_blocks(
        user,
        chat_id,
        settings,
        chat=chat,
        query_text=query_text,
        recent_limit=recent_limit,
        is_day_plan=is_day_plan,
        slim_context=slim_context,
        client_timezone=client_timezone,
        out=out,
        on_status=on_status,
    )
    chat = blocks.chat
    recent_source = blocks.recent_all
    if omit_message_ids:
        recent_source = [m for m in recent_source if m.id not in omit_message_ids]
    keep = select_recent_window(recent_source, settings.context_token_budget, recent_limit)
    recent = recent_source[-keep:] if keep else []
    if out is not None and chat and chat.summary and (chat.summary_message_count or 0) > 0:
        out["context_summarized"] = chat.summary_message_count
    local_tz = time_context_service.effective_timezone(user.timezone, client_timezone)

    style = user.response_style if user.response_style in STYLE_HINTS else "balanced"
    location_for_context = prompt_location or profile_service.user_location_label(user)
    system_parts: list[str] = [
        "You are Recall, a helpful personal AI assistant.",
        format_user_name_only_block(user)
        if slim_context
        else format_user_profile_block(
            user,
            location_override=prompt_location,
            include_email=should_include_profile_email(query_text),
        ),
        STYLE_HINTS["short"] if lightweight else STYLE_HINTS[style],
    ]
    # Grade hint (if any) then quiz/vocab path — same order as the prior inline assembly.
    quiz_parts, chat = await _quiz_hints(
        user,
        chat_id,
        settings,
        chat=chat,
        quiz_grade=quiz_grade,
        minimal_quiz_context=minimal_quiz_context,
        minimal_vocab_answer_context=minimal_vocab_answer_context,
    )
    system_parts.extend(quiz_parts)
    if lightweight:
        system_parts.append(LIGHTWEIGHT_REPLY_HINT)
        system_parts.append(SHORT_RESPONSE_FORMAT_HINT)
    elif not minimal_quiz_context and not minimal_vocab_answer_context:
        system_parts.extend(
            _style_format_hints(
                query_text=query_text,
                style=style,
                is_day_plan=is_day_plan,
                minimal_personal_context=minimal_personal_context,
            )
        )
    system_parts.append(response_tone_service.tone_hint(getattr(user, "response_tone", None)))
    if not slim_context:
        ci = getattr(user, "custom_instructions", None)
        custom_instructions = ci.strip() if isinstance(ci, str) and ci.strip() else ""
        if custom_instructions:
            # User-authored; still untrusted relative to system policy (injection).
            bounded = custom_instructions[:2000]
            system_parts.append(
                wrap_untrusted(
                    "user personal instructions",
                    f"User's personal instructions:\n{bounded}",
                )
            )
    locale_hint = locale_service.locale_system_hint(user.locale)
    if locale_hint:
        system_parts.append(locale_hint)
    if not slim_context:
        system_parts.extend(
            _integration_hints(
                settings=settings,
                query_text=query_text,
                local_tz=local_tz,
                user_locale=user.locale,
                location_for_context=location_for_context,
                prompt_location=prompt_location,
                memory_block=blocks.memory_block,
                attachment_rag_block=blocks.attachment_rag_block,
                todos_section=blocks.todos_section,
                todo_sync_feedback=todo_sync_feedback,
                is_day_plan=is_day_plan,
                projects_block=blocks.projects_block,
                summary=summary,
            )
        )

    messages: list[dict[str, str]] = [{"role": "system", "content": "\n\n".join(system_parts)}]
    for msg in recent:
        content = msg.content
        if msg.role == "user":
            content = wrap_persisted_attachment_excerpts(content)
        messages.append({"role": msg.role, "content": content})
    return messages

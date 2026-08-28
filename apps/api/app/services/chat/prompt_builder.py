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
    COMPACT_RESPONSE_FORMAT_HINT,
    COPY_DELIVERABLE_HINT,
    DAY_LEARNING_SNAPSHOT_HINT,
    DAY_PLANNING_ANSWER_HINT,
    EMAIL_DRAFT_HINT,
    FORMAT_CONTRACT,
    LIGHTWEIGHT_REPLY_HINT,
    MATH_INTENT_HINT,
    MATH_SOLVER_HINT,
    MATH_TUTORING_HINT,
    PRIVACY_HINT,
    QUIZ_ANSWER_HINT,
    SHORT_MATH_SAFETY_HINT,
    SHORT_RESPONSE_FORMAT_HINT,
    STYLE_HINTS,
    TONE_FORMAT_GUARD,
    UNIVERSAL_FORMAT_BASELINE,
    VISUALIZATION_HINTS,
    VOCAB_CHAT_ANSWER_HINT,
    WRITING_LINE_HINT,
    format_quiz_grading_hint,
    is_bare_writing_line,
    is_learning_progress_question,
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


async def fetch_web_and_tools(
    user_content: str,
    settings: Settings,
    *,
    prompt_messages: list[dict[str, str]],
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
) -> tuple[str | None, str | None, list[WebSearchHit], VerifiedMathBlock | None]:
    """Fetch web-search and SymPy augmentation blocks WITHOUT mutating prompt_messages.

    Web search (network) and SymPy (subprocess) are independent — gather both.
    Returns ``(web_block, math_block, search_sources, verified_math)``; injection
    is a separate step so this fetch can run concurrently with integration fetches.
    """
    # Compute the math-intent signal ONCE: it gates the "calculating" status
    # below AND build_math_augmentation's own needs_symbolic_math check, so
    # passing it through avoids re-scanning the same message twice per turn
    # (needs_symbolic_math runs ~30 substring/matcher passes over the text).
    needs_math = settings.math_tools_enabled and math_tools_service.needs_symbolic_math(
        user_content, has_image_attachment=has_image_attachment
    )
    if needs_math and on_status is not None:
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
            needs_math=needs_math,
        ),
    )
    return web_block, math_block, search_sources, verified_math


async def inject_web_and_tools(
    prompt_messages: list[dict[str, str]],
    web_block: str | None,
    math_block: str | None,
    settings: Settings,
    *,
    user_content: str,
    user_timezone: str | None = None,
    user_location: str | None = None,
    prior_user_messages: list[str] | None = None,
    on_status: StreamStatusFn | None = None,
    has_calendar_write: bool = False,
) -> list[dict[str, str]]:
    """Inject web → MCP calendar → math blocks in the historical order.

    Mutation order is what keeps prompt shape stable; fetch order is irrelevant.
    """
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
    return updated


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
    """Backward-compatible fetch + inject (used by tests). Prefer the split pair."""
    web_block, math_block, search_sources, verified_math = await fetch_web_and_tools(
        user_content,
        settings,
        prompt_messages=prompt_messages,
        user_timezone=user_timezone,
        user_location=user_location,
        latitude=latitude,
        longitude=longitude,
        prior_user_messages=prior_user_messages,
        has_image_attachment=has_image_attachment,
        image_math_extract=image_math_extract,
        on_status=on_status,
        user=user,
        redis=redis,
    )
    updated = await inject_web_and_tools(
        prompt_messages,
        web_block,
        math_block,
        settings,
        user_content=user_content,
        user_timezone=user_timezone,
        user_location=user_location,
        prior_user_messages=prior_user_messages,
        on_status=on_status,
        has_calendar_write=has_calendar_write,
    )
    return updated, search_sources, verified_math


@dataclass
class _PromptContextBlocks:
    memory_block: str
    todos_section: str | None
    projects_block: str
    recent_all: list[Any]
    attachment_rag_block: str
    chat: Chat | None
    history_rag_query_vec: list[float] | None = None


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
    history_rag: bool = False,
    recent_messages: list[Any] | None = None,
) -> _PromptContextBlocks:
    """Load memory/todos/projects/RAG + recent messages for the system prompt.

    Each gather branch opens a short-lived session so external HTTP (RAG/memory
    embed) cannot pin a caller's connection across the concurrent load.
    Chat-history query embed overlaps the gather; recent-window excludes are
    applied later when hits are filtered.
    """

    async def _history_rag_embed() -> list[float] | None:
        if not history_rag or not query_text or not query_text.strip():
            return None
        from app.services import chat_history_rag as chat_history_rag_service

        return await chat_history_rag_service.embed_query_for_prompt(
            settings, user_id=user.id, query=query_text
        )

    async def _fetch_recent() -> list[Any]:
        if recent_messages is not None:
            return recent_messages
        async with SessionLocal() as s:
            return await messages_repo.list_recent(s, chat_id, limit=recent_limit)

    if slim_context:
        if history_rag:
            recent_all, history_rag_query_vec = await asyncio.gather(
                _fetch_recent(),
                _history_rag_embed(),
            )
        else:
            recent_all = await _fetch_recent()
            history_rag_query_vec = None
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
            history_rag_query_vec=history_rag_query_vec,
        )

    if chat is None:
        async with SessionLocal() as s:
            chat = await chats_repo.get_by_id(s, chat_id, user.id)

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
                exclude_sensitive=True,
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
                block = await projects_service.load_project_for_prompt(
                    s,
                    user.id,
                    chat.project_id,
                    settings,
                    quiz_mode=getattr(chat, "quiz_mode", None),
                    client_timezone=client_timezone,
                )
            else:
                block = await projects_service.load_projects_for_prompt(s, user.id, settings)
            if query_text and is_learning_progress_question(query_text):
                today = await projects_service.load_today_learning_words_for_prompt(
                    s,
                    user,
                    settings,
                    client_timezone=client_timezone,
                )
                return "\n\n".join(part for part in (block, today) if part)
            return block

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

    async def _load_recent() -> list[Any]:
        if recent_messages is not None:
            return recent_messages
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
        history_rag_query_vec,
    ) = await asyncio.gather(
        _memory_block(),
        _todos_section(),
        _projects_block(),
        _load_recent(),
        _attachment_rag_block(),
        _history_rag_embed(),
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
        history_rag_query_vec=history_rag_query_vec,
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
        parts.extend([UNIVERSAL_FORMAT_BASELINE, QUIZ_ANSWER_HINT, PRIVACY_HINT])
    elif minimal_vocab_answer_context:
        parts.extend([UNIVERSAL_FORMAT_BASELINE, VOCAB_CHAT_ANSWER_HINT, PRIVACY_HINT])
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
    compact: bool = False,
) -> list[str]:
    """Clarification / day-planning / response-format hints for non-quiz turns.

    ``compact`` is for slim/casual chat (not rich context): keep math-safety
    guardrails without the full intent/viz/solver pack (~4.5k tokens).
    """
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
        parts.append(UNIVERSAL_FORMAT_BASELINE)
        parts.append(SHORT_RESPONSE_FORMAT_HINT)
        parts.append(SHORT_MATH_SAFETY_HINT)
    elif is_day_plan:
        # Day-plan used to miss math guardrails. Keep compact math safety so
        # any math in a plan still renders; keep the richer format pack so a
        # day outline can use headings.
        parts.append(UNIVERSAL_FORMAT_BASELINE)
        parts.append(FORMAT_CONTRACT)
        parts.append(SHORT_MATH_SAFETY_HINT)
    elif compact:
        # Slim/casual used to still get RESPONSE_FORMAT_HINT (tips/headings/
        # tables), so a pasted phrase became a funny essay with a clipped
        # table. ChatGPT-shaped: answer first, no invented chrome.
        parts.append(UNIVERSAL_FORMAT_BASELINE)
        parts.append(COMPACT_RESPONSE_FORMAT_HINT)
        parts.append(SHORT_MATH_SAFETY_HINT)
    else:
        parts.append(UNIVERSAL_FORMAT_BASELINE)
        parts.extend(
            [
                FORMAT_CONTRACT,
                MATH_INTENT_HINT,
                MATH_SOLVER_HINT,
                MATH_TUTORING_HINT,
                VISUALIZATION_HINTS,
            ]
        )
    # FORMAT_CONTRACT already covers X vs Y → table. A shallow vs/versus
    # regex must not append a second comparison sermon (false positives).
    parts.append(COPY_DELIVERABLE_HINT)
    if query_text and is_writing_deliverable_request(query_text):
        parts.append(EMAIL_DRAFT_HINT)
    if query_text and is_bare_writing_line(query_text):
        parts.append(WRITING_LINE_HINT)
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
    is_day_plan: bool,
    projects_block: str,
    summary: str | None,
    chat_history_rag_block: str = "",
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
        parts.append(wrap_untrusted("reminders and lists", todos_section, first_party=True))
    if not is_day_plan:
        parts.append(projects_service.PROJECT_HINT)
    if projects_block:
        parts.append(projects_block)
    if chat_history_rag_block:
        parts.append(chat_history_rag_block)
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
    on_status: StreamStatusFn | None = None,
    omit_message_ids: set[UUID] | None = None,
    probe_attachment_rag: bool = True,
    recent_messages: list[Any] | None = None,
) -> list[dict[str, str]]:
    """Assemble system + recent messages for a chat turn.

    Context loading uses short-lived sessions so embeds cannot pin a caller
    connection across the concurrent gather.
    """
    # M9: quiz/vocab turns used a smaller recent window (12) than compaction
    # (20), so messages 13-20 were neither in the quiz prompt's recent window
    # nor in the summary — dropped entirely on long quiz threads. Align the
    # quiz limit with the compaction window so the boundary agrees.
    recent_limit = settings.recent_message_window
    # Opt-in rich context: casual chat skips memory embed / todos / projects.
    # ``lightweight`` is only the ultra-brief social reply style (hi/thanks).
    is_day_plan = bool(query_text and is_day_planning_question(query_text))
    # If this chat has indexed attachment chunks, force rich context so a
    # casual follow-up ("what's on page 10?") still retrieves RAG chunks.
    # Without this, a lightweight query after uploading a PDF skips RAG
    # entirely and the user gets no document context on follow-ups.
    if not rich_context and settings.attachment_rag_enabled and probe_attachment_rag:
        from app.repositories import attachment_chunks as chunks_repo

        try:
            async with SessionLocal() as s:
                rich_context = await chunks_repo.has_chunks_for_chat(s, user.id, chat_id)
        except Exception:
            logger.debug("has_chunks_for_chat probe failed for chat_id=%s", chat_id, exc_info=True)
    slim_context = (
        minimal_personal_context
        or minimal_quiz_context
        or minimal_vocab_answer_context
        or lightweight
        or not rich_context
    )
    # M9: enable chat-history RAG for quiz/vocab turns too — grading a quiz
    # answer may need the original quiz context from older messages that
    # fell out of the recent window. ``lightweight`` and ``not rich_context``
    # stay excluded (ultra-brief / casual turns don't need RAG).
    quiz_rag_eligible = minimal_quiz_context or minimal_vocab_answer_context
    history_rag = bool(
        (not slim_context or quiz_rag_eligible)
        and settings.chat_history_rag_enabled
        and query_text
        and query_text.strip()
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
        history_rag=history_rag,
        recent_messages=recent_messages,
    )
    chat = blocks.chat
    recent_source = blocks.recent_all
    if omit_message_ids:
        recent_source = [m for m in recent_source if m.id not in omit_message_ids]
    keep = select_recent_window(recent_source, settings.context_token_budget, recent_limit)
    recent = recent_source[-keep:] if keep else []
    chat_history_rag_block = ""
    if history_rag:
        from app.services import chat_history_rag as chat_history_rag_service

        exclude = {m.id for m in recent}
        if omit_message_ids:
            exclude |= omit_message_ids
        chat_history_rag_block = await chat_history_rag_service.retrieve_for_prompt(
            settings,
            user_id=user.id,
            query=query_text or "",
            exclude_message_ids=exclude,
            query_vec=blocks.history_rag_query_vec,
        )
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
        # Lightweight/chit-chat turns skipped the math guardrails entirely,
        # so a math question mis-classified as lightweight lost the rules
        # that keep math from rendering as raw ```latex/```copy. Keep the
        # compact safety hint on every turn.
        system_parts.append(SHORT_MATH_SAFETY_HINT)
    elif not minimal_quiz_context and not minimal_vocab_answer_context:
        system_parts.extend(
            _style_format_hints(
                query_text=query_text,
                style=style,
                is_day_plan=is_day_plan,
                minimal_personal_context=minimal_personal_context,
                compact=slim_context,
            )
        )
    else:
        # Quiz / vocab answer turns skipped _style_format_hints entirely, so
        # any math in a quiz explanation rendered as raw LaTeX. Keep the
        # compact math safety hint so verified/inline math still renders.
        system_parts.append(SHORT_MATH_SAFETY_HINT)
    system_parts.append(response_tone_service.tone_hint(getattr(user, "response_tone", None)))
    system_parts.append(TONE_FORMAT_GUARD)
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
    # M8: inject the rolling summary even on the slim path. A slim long thread
    # (lightweight / not rich_context) still drops everything older than the
    # recent window from the prompt — without the summary the model loses all
    # context from earlier in the conversation. The summary is already
    # computed and is just a string, so including it is free.
    if summary:
        system_parts.append(
            wrap_untrusted("conversation summary", f"Summary of earlier conversation:\n{summary}")
        )
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
                is_day_plan=is_day_plan,
                projects_block=blocks.projects_block,
                summary=summary,
                chat_history_rag_block=chat_history_rag_block,
            )
        )

    messages: list[dict[str, str]] = [{"role": "system", "content": "\n\n".join(system_parts)}]
    for msg in recent:
        content = msg.content
        if msg.role == "user":
            content = wrap_persisted_attachment_excerpts(content)
        messages.append({"role": msg.role, "content": content})
    return messages

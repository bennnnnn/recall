import asyncio
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import Chat, User
from app.services import profile as profile_service
from app.services.chat.prompt_constants import (
    BROAD_SELF_ANSWER_HINT,
    CLARIFICATION_HINT,
    COPY_DELIVERABLE_HINT,
    DAY_LEARNING_SNAPSHOT_HINT,
    DAY_PLANNING_ANSWER_HINT,
    EMAIL_DRAFT_HINT,
    INTENT_FORMAT_HINT,
    MATH_SOLVER_HINT,
    PLAIN_CHAT_QUIZ_ANSWER_HINT,
    PRIVACY_HINT,
    QUIZ_ANSWER_HINT,
    QUIZ_RECENT_MESSAGE_LIMIT,
    RESPONSE_FORMAT_HINT,
    SHORT_RESPONSE_FORMAT_HINT,
    STYLE_HINTS,
    VISUALIZATION_HINTS,
    is_writing_deliverable_request,
)
from app.services.context_window import select_recent_window
from app.services.day_planning import is_day_planning_question, is_day_reflection_question
from app.services.math_tools import VerifiedMathBlock
from app.services.prompt_safety import wrap_untrusted

logger = logging.getLogger(__name__)

StreamStatusFn = Callable[[str], Awaitable[None]]
StreamReasoningFn = Callable[[str], Awaitable[None]]


def format_user_profile_block(user: User, *, location_override: str | None = None) -> str:
    """Basic identity from Google sign-in — injected into every chat prompt."""
    lines = [
        "User profile (internal — from Google sign-in; do not quote email or location "
        "unless they explicitly ask for those details):"
    ]
    if user.name and user.name.strip():
        lines.append(f"- Name: {user.name.strip()}")
    if user.email and user.email.strip():
        lines.append(f"- Email: {user.email.strip()}")
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
    on_status: StreamStatusFn | None = None,
    user: User | None = None,
    redis: Redis | None = None,
    has_calendar_write: bool = False,
) -> tuple[list[dict[str, str]], list[WebSearchHit], VerifiedMathBlock | None]:
    """Web search always uses the full direct path; MCP handles calendar/sympy only."""
    import app.services.chat as chat_pkg

    updated, search_sources = await chat_pkg.web_search_service.augment_prompt_messages(
        prompt_messages,
        user_content,
        settings,
        user_timezone=user_timezone,
        user_location=user_location,
        latitude=latitude,
        longitude=longitude,
        prior_user_messages=prior_user_messages,
        on_status=on_status,
        user=user,
        redis=redis,
    )

    if settings.mcp_tools_enabled:
        updated = await chat_pkg.chat_tools_service.augment_prompt_with_mcp_tools(
            updated,
            user_content,
            settings,
            user_timezone=user_timezone,
            user_location=user_location,
            prior_user_messages=prior_user_messages,
            on_status=on_status,
            has_calendar_write=has_calendar_write,
        )

    if (
        settings.math_tools_enabled
        and chat_pkg.math_tools_service.needs_symbolic_math(
            user_content, has_image_attachment=has_image_attachment
        )
        and on_status is not None
    ):
        await on_status("calculating")

    updated, verified_math = await chat_pkg.math_tools_service.augment_prompt_messages(
        updated,
        user_content,
        settings,
        has_image_attachment=has_image_attachment,
    )
    return updated, search_sources, verified_math


async def build_prompt_messages(
    session: AsyncSession,
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
    quiz_grading_hint: str | None = None,
    client_timezone: str | None = None,
    prompt_location: str | None = None,
    todo_sync_feedback: str | None = None,
) -> list[dict[str, str]]:
    import app.services.chat as chat_pkg

    recent_limit = (
        QUIZ_RECENT_MESSAGE_LIMIT if minimal_quiz_context else settings.recent_message_window
    )
    is_day_plan = bool(query_text and is_day_planning_question(query_text))
    todos_section: str | None = None
    if minimal_personal_context or minimal_quiz_context:
        recent_all = await chat_pkg.messages_repo.list_recent(session, chat_id, limit=recent_limit)
        memory_block = ""
        projects_block = ""
        if out is not None:
            out["recalled"] = 0
            out["memory_hints"] = []
    else:
        if chat is None:
            chat = await chat_pkg.chats_repo.get_by_id(session, chat_id, user.id)

        # Each of these is an independent read with no dependency on the others'
        # output — give each its own short-lived session (a single AsyncSession
        # cannot safely run concurrent operations) and gather them, instead of
        # awaiting four DB round-trips back-to-back before the LLM call starts.
        async def _memory_block() -> str:
            async with SessionLocal() as s:
                return await chat_pkg.memory_service.get_memory_block(
                    s, user, settings, query_text=query_text
                )

        async def _todos_section() -> str | None:
            async with SessionLocal() as s:
                return await chat_pkg.todos_service.build_todos_system_section(
                    s,
                    user,
                    settings,
                    client_timezone=client_timezone,
                    query_text=query_text,
                )

        async def _projects_block() -> str:
            async with SessionLocal() as s:
                if is_day_plan:
                    return await chat_pkg.projects_service.load_daily_learning_summary_for_prompt(
                        s,
                        user,
                        settings,
                        client_timezone=client_timezone,
                    )
                if chat and chat.project_id:
                    return await chat_pkg.projects_service.load_project_for_prompt(
                        s,
                        user.id,
                        chat.project_id,
                        settings,
                        quiz_mode=getattr(chat, "quiz_mode", None),
                        client_timezone=client_timezone,
                    )
                return await chat_pkg.projects_service.load_projects_for_prompt(
                    s, user.id, settings
                )

        memory_block, todos_section, projects_block, recent_all = await asyncio.gather(
            _memory_block(),
            _todos_section(),
            _projects_block(),
            chat_pkg.messages_repo.list_recent(session, chat_id, limit=recent_limit),
        )
        if out is not None:
            labels = set(chat_pkg.memory_service.SECTION_LABELS.values())
            hints = [
                line[3:].strip()
                for line in memory_block.split("\n")
                if line.startswith("## ") and line[3:].strip() in labels
            ]
            out["recalled"] = len(hints)
            out["memory_hints"] = hints[:3]
    keep = select_recent_window(recent_all, settings.context_token_budget, recent_limit)
    recent = recent_all[-keep:] if keep else []
    if out is not None and chat and chat.summary and (chat.summary_message_count or 0) > 0:
        out["context_summarized"] = chat.summary_message_count
    local_tz = chat_pkg.time_context_service.effective_timezone(user.timezone, client_timezone)

    style = user.response_style if user.response_style in STYLE_HINTS else "balanced"
    location_for_context = prompt_location or profile_service.user_location_label(user)
    system_parts: list[str] = [
        "You are Recall, a helpful personal AI assistant.",
        format_user_name_only_block(user)
        if minimal_personal_context or minimal_quiz_context
        else format_user_profile_block(user, location_override=prompt_location),
        STYLE_HINTS[style],
    ]
    if minimal_quiz_context:
        quiz_mode = getattr(chat, "quiz_mode", None) if chat else None
        system_parts.append(
            PLAIN_CHAT_QUIZ_ANSWER_HINT if quiz_mode == "chat" else QUIZ_ANSWER_HINT
        )
        if quiz_grading_hint:
            system_parts.append(quiz_grading_hint)
        system_parts.append(PRIVACY_HINT)
        if chat is None:
            chat = await chat_pkg.chats_repo.get_by_id(session, chat_id, user.id)
        if chat and chat.project_id:
            quiz_ctx = await chat_pkg.projects_service.load_project_quiz_context(
                session, user.id, chat.project_id, settings
            )
            if quiz_ctx:
                system_parts.append(quiz_ctx)
    else:
        system_parts.extend([CLARIFICATION_HINT, PRIVACY_HINT])
        if query_text and is_day_planning_question(query_text):
            system_parts.append(DAY_PLANNING_ANSWER_HINT)
            system_parts.append(DAY_LEARNING_SNAPSHOT_HINT)
            if is_day_reflection_question(query_text):
                system_parts.append(
                    "This is an end-of-day reflection — keep todos, calendar, and loose ends "
                    "as the main focus."
                )
        if minimal_personal_context:
            system_parts.append(BROAD_SELF_ANSWER_HINT)
        if style == "short":
            system_parts.append(SHORT_RESPONSE_FORMAT_HINT)
        elif not is_day_plan:
            system_parts.extend(
                [INTENT_FORMAT_HINT, MATH_SOLVER_HINT, RESPONSE_FORMAT_HINT, VISUALIZATION_HINTS]
            )
        else:
            system_parts.append(RESPONSE_FORMAT_HINT)
        system_parts.append(COPY_DELIVERABLE_HINT)
        if query_text and is_writing_deliverable_request(query_text):
            system_parts.append(EMAIL_DRAFT_HINT)
    system_parts.append(
        chat_pkg.response_tone_service.tone_hint(getattr(user, "response_tone", None))
    )
    ci = getattr(user, "custom_instructions", None)
    custom_instructions = ci.strip() if isinstance(ci, str) and ci.strip() else ""
    if custom_instructions:
        system_parts.append(f"User's personal instructions:\n{custom_instructions}")
    locale_hint = chat_pkg.locale_service.locale_system_hint(user.locale)
    if locale_hint:
        system_parts.append(locale_hint)
    if not minimal_quiz_context and not minimal_personal_context:
        system_parts.append(
            chat_pkg.time_context_service.format_time_context(
                local_tz, user.locale, location_for_context
            )
        )
        if settings.web_search_enabled:
            system_parts.append(chat_pkg.web_search_service.WEB_SEARCH_HINT)
            if query_text and chat_pkg.web_search_service.is_ambiguous_local_places_query(
                query_text
            ):
                system_parts.append(chat_pkg.web_search_service.AMBIGUOUS_NEARBY_HINT)
            elif query_text and chat_pkg.web_search_service.is_places_list_query(query_text):
                system_parts.append(chat_pkg.web_search_service.LOCAL_PLACES_FORMAT_HINT)
            elif query_text and chat_pkg.web_search_service.is_distance_query(query_text):
                system_parts.append(chat_pkg.web_search_service.GEO_DISTANCE_HINT)
            if (
                prompt_location
                and query_text
                and chat_pkg.web_search_service.is_geo_query(query_text)
            ):
                system_parts.append(chat_pkg.web_search_service.GEO_ACTIVE_LOCATION_HINT)
        if settings.google_calendar_enabled:
            system_parts.append(chat_pkg.calendar_service.CALENDAR_HINT)
        if settings.gmail_enabled:
            system_parts.append(chat_pkg.email_service.GMAIL_HINT)
        if memory_block:
            system_parts.append(wrap_untrusted("memory", memory_block))
        if todos_section:
            system_parts.append(todos_section)
        if todo_sync_feedback:
            system_parts.append(todo_sync_feedback)
        if not is_day_plan:
            system_parts.append(chat_pkg.projects_service.PROJECT_HINT)
        if projects_block:
            system_parts.append(projects_block)
        if summary:
            system_parts.append(f"Summary of earlier conversation:\n{summary}")

    messages: list[dict[str, str]] = [{"role": "system", "content": "\n\n".join(system_parts)}]
    for msg in recent:
        messages.append({"role": msg.role, "content": msg.content})
    return messages

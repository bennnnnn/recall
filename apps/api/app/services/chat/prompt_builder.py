import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import Chat, User
from app.models.schemas.math import MathImageExtract
from app.modules import web_search as web_search_service
from app.modules.chemistry.followup import CHEMISTRY_FOLLOWUP_HINT, chemistry_followup_problem
from app.modules.integrations import inbox as email_service
from app.modules.math.followup import (
    MATH_FOLLOWUP_HINT,
    is_math_followup,
    readable_standalone_answer,
)
from app.modules.math.reply_policy import MATH_REPLY_POLICY
from app.modules.math.tools.extract import is_graph_followup
from app.modules.physics.followup import PHYSICS_FOLLOWUP_HINT, physics_followup_problem
from app.services import locale as locale_service
from app.services import profile as profile_service
from app.services import response_tone as response_tone_service
from app.services import time_context as time_context_service
from app.services.chat import tools as chat_tools_service
from app.services.chat.continuation_subject import (
    blocks_math_followup,
)
from app.services.chat.prompt_constants import (
    ADVICE_PERSONALIZE_HINT,
    LIGHTWEIGHT_REPLY_HINT,
    MATH_FENCE_SAFETY_HINT,
    PERSONAL_DISCLOSURE_HINT,
    SHORT_RESPONSE_FORMAT_HINT,
    STYLE_HINTS,
    TONE_FORMAT_GUARD,
    active_lesson_step,
    is_bare_writing_line,
    is_capabilities_question,
    is_email_or_message_request,
    is_learning_plan_request,
    is_personal_disclosure_turn,
    is_short_confirmation,
    is_teaching_request,
    learning_plan_daily_contract,
    programming_lesson_contract,
    recalls_earlier_conversation,
)
from app.services.chat.prompt_context import (
    _load_context_blocks,
    _load_unsummarized_gap,
)
from app.services.chat.prompt_format import (
    _integration_hints,
    _style_format_hints,
)
from app.services.chat.stream_status import StreamStatusFn
from app.services.context_window import (
    estimate_tokens,
    select_recent_window,
    trim_message_for_summary,
)
from app.services.day_planning import is_day_planning_question
from app.services.md_fence_scan import strip_closed_fences
from app.services.prompt_inject import inject_before_last_user
from app.services.prompt_safety import (
    wrap_persisted_attachment_excerpts,
    wrap_untrusted,
    wrap_user_preferences,
)
from app.services.solving import VerifiedSolveBlock
from app.services.subject_solving import (
    SubjectName,
    build_subject_augmentation,
    detect_subject,
)

_PROMPT_STRIP_FENCE_LANGS = ("answer", "geometry", "graph", "sources", "places")


def _strip_prompt_owned_fences(content: str) -> str:
    """Drop solver/search fences from assistant history before the model sees them.

    Persisted messages keep the fences for the client. Re-injecting ```answer /
    ```graph / ```sources into the recent window teaches the model to copy them.
    """
    out = content
    for lang in _PROMPT_STRIP_FENCE_LANGS:
        out = strip_closed_fences(out, lang)
    return out


def _custom_instructions_block(user: User) -> str | None:
    ci = getattr(user, "custom_instructions", None)
    custom = ci.strip() if isinstance(ci, str) and ci.strip() else ""
    if not custom:
        return None
    return wrap_user_preferences(f"User's personal instructions:\n{custom[:2000]}")


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
    if is_email_or_message_request(cleaned):
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
    math_followup_problem: str | None = None,
    chemistry_followup_problem: str | None = None,
    physics_followup_problem: str | None = None,
    on_status: StreamStatusFn | None = None,
    user: User | None = None,
    redis: Redis | None = None,
) -> tuple[str | None, str | None, list[WebSearchHit], VerifiedSolveBlock | None, bool, str | None]:
    """Fetch web-search and subject blocks WITHOUT mutating prompt_messages.

    Web search (network) and the subject solver are independent — gather both.
    Returns ``(web_block, subject_block, search_sources, verified, solver_unverified, unverified_subject)``.
    ``solver_unverified`` is the adapter flag. Callers must not re-derive it from
    the wording of the prompt block. ``unverified_subject`` is set only when that flag is true.
    """
    math_user_content = math_followup_problem or user_content
    subject_user_content = user_content
    subject: SubjectName | None
    if math_followup_problem is not None or is_graph_followup(user_content):
        subject = "math"
    elif chemistry_followup_problem is not None:
        subject = "chemistry"
        subject_user_content = chemistry_followup_problem
    elif physics_followup_problem is not None:
        subject = "physics"
        subject_user_content = physics_followup_problem
    else:
        subject = detect_subject(
            user_content,
            has_image_attachment=has_image_attachment,
            image_math_extract=image_math_extract,
            chemistry_enabled=settings.chemistry_enabled,
        )
    if subject == "chemistry":
        needs_subject = settings.chemistry_enabled
    elif subject in {"math", "physics"}:
        needs_subject = settings.math_tools_enabled
    else:
        needs_subject = False
    if needs_subject and on_status is not None:
        await on_status("physics" if subject == "physics" else "calculating")

    async def _web_for_turn() -> tuple[str | None, list[WebSearchHit]]:
        # Closed symbolic/statistical work is self-contained. Do not ask the
        # web classifier (or a search provider) whether a z-score, equation,
        # derivative, etc. needs live sources. Explicit/current-data requests
        # still pass the ordinary synchronous live-data gate below.
        if needs_subject and not web_search_service.web_search_fast_yes(
            user_content, prior_user_messages=prior_user_messages
        ):
            return None, []
        return await web_search_service.build_search_augmentation(
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
        )

    (web_block, search_sources), subject_result = await asyncio.gather(
        _web_for_turn(),
        build_subject_augmentation(
            subject_user_content,
            settings,
            math_user_content=math_user_content,
            has_image_attachment=has_image_attachment,
            image_math_extract=image_math_extract,
            prior_user_messages=prior_user_messages,
            response_intent_text=user_content if math_followup_problem is not None else None,
            detected_subject=subject,
            redis=redis,
        ),
    )
    return (
        web_block,
        subject_result.prompt_block,
        search_sources,
        subject_result.verified,
        subject_result.unverified,
        subject_result.subject if subject_result.unverified else None,
    )


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
    math_followup_problem: str | None = None,
    on_status: StreamStatusFn | None = None,
    user: User | None = None,
    redis: Redis | None = None,
    has_calendar_write: bool = False,
) -> tuple[list[dict[str, str]], list[WebSearchHit], VerifiedSolveBlock | None]:
    """Backward-compatible fetch + inject (used by tests). Prefer the split pair."""
    (
        web_block,
        math_block,
        search_sources,
        verified_math,
        _solver_unverified,
        _unverified_subject,
    ) = await fetch_web_and_tools(
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
        math_followup_problem=math_followup_problem,
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
    lightweight: bool = False,
    rich_context: bool = True,
    advice_memory: bool = False,
    client_timezone: str | None = None,
    prompt_location: str | None = None,
    on_status: StreamStatusFn | None = None,
    omit_message_ids: set[UUID] | None = None,
    probe_attachment_rag: bool = True,
    recent_messages: list[Any] | None = None,
    current_user_message_id: UUID | None = None,
) -> list[dict[str, str]]:
    """Assemble system + recent messages for a chat turn.

    Context loading uses short-lived sessions so embeds cannot pin a caller
    connection across the concurrent gather.
    """
    recent_limit = settings.recent_message_window
    # Greetings stay on the short-reply style. Other turns load memory and
    # past-chat retrieval only when the text is actually about the user.
    is_day_plan = bool(query_text and is_day_planning_question(query_text))
    # If this chat has indexed attachment chunks, force rich context so a
    # casual follow-up ("what's on page 10?") still retrieves RAG chunks.
    # Without this, a lightweight query after uploading a PDF skips RAG
    # entirely and the user gets no document context on follow-ups.
    if not rich_context and settings.attachment_rag_enabled and probe_attachment_rag:
        from app.modules.attachments import chunks_repository as chunks_repo

        try:
            async with SessionLocal() as s:
                rich_context = await chunks_repo.has_chunks_for_chat(s, user.id, chat_id)
        except Exception:
            logger.debug("has_chunks_for_chat probe failed for chat_id=%s", chat_id, exc_info=True)
    # Personal continuity only when this turn is actually about the user.
    # A normal question ("what is the capital of France") used to embed memory
    # and chat history on every non-greeting, which sat on the first token
    # for seconds before the model started.
    personal_context = (rich_context or advice_memory) and not lightweight
    load_memory = personal_context
    slim_context = minimal_personal_context or lightweight or not rich_context
    recalls_shared_past = bool(query_text and recalls_earlier_conversation(query_text))
    history_rag = bool(
        (personal_context or recalls_shared_past)
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
        slim_context=slim_context,
        load_memory=load_memory,
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
    tail_tokens = sum(
        estimate_tokens(message.content)
        for message in recent
        if isinstance(getattr(message, "content", None), str)
    )
    gap = await _load_unsummarized_gap(
        chat_id,
        chat,
        blocks.recent_all,
        recent,
        recent_limit=recent_limit,
        token_budget=max(0, settings.context_token_budget - tail_tokens),
        current_user_message_id=current_user_message_id,
    )
    if omit_message_ids:
        gap = [m for m in gap if m.id not in omit_message_ids]
    recent_ids = {m.id for m in recent}
    gap = [m for m in gap if m.id not in recent_ids]
    followup_exchange = recent
    # New-turn preparation includes its current user in history, sometimes
    # before persistence completes. Only the caller's explicit ID proves that
    # it is the current turn, rather than an incomplete previous exchange.
    if (
        current_user_message_id is not None
        and recent
        and recent[-1].id == current_user_message_id
        and recent[-1].role == "user"
        and recent[-1].content == query_text
    ):
        followup_exchange = recent[:-1]
    # Regeneration retains the persisted current user while omitting its newest
    # assistant. Classify the preceding completed exchange only with that proof.
    elif (
        omit_message_ids
        and len(blocks.recent_all) >= 2
        and blocks.recent_all[-1].role == "assistant"
        and blocks.recent_all[-1].id in omit_message_ids
        and recent
        and recent[-1] is blocks.recent_all[-2]
        and recent[-1].role == "user"
        and recent[-1].content == query_text
    ):
        followup_exchange = recent[:-1]
    math_followup = is_math_followup(query_text, followup_exchange, blocked=blocks_math_followup)
    chemistry_followup = (
        not math_followup and chemistry_followup_problem(query_text, followup_exchange) is not None
    )
    physics_followup = (
        not math_followup
        and not chemistry_followup
        and physics_followup_problem(query_text, followup_exchange) is not None
    )
    lesson = active_lesson_step(followup_exchange)
    chat_history_rag_block = ""
    # The context gather already attempted the history embed. None means no
    # chunks or a failed/timed-out embed; do not repeat that work serially.
    if history_rag and blocks.history_rag_query_vec is not None:
        from app.services.chat import history_rag as chat_history_rag_service

        exclude = {m.id for m in recent} | {m.id for m in gap}
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
    prior_messages = [
        (message.role, message.content)
        for message in followup_exchange
        if message.role in {"user", "assistant"} and isinstance(message.content, str)
    ]
    compact_format = bool(query_text and is_bare_writing_line(query_text))
    if query_text and is_short_confirmation(query_text) and not lightweight:
        compact_format = True
    if lesson:
        # "ok" / "yes" to a lesson step asks for the next step, not a casual reply.
        compact_format = False
    if lightweight:
        system_parts.append(LIGHTWEIGHT_REPLY_HINT)
        system_parts.append(SHORT_RESPONSE_FORMAT_HINT)
        # Lightweight/chit-chat turns skipped the math guardrails entirely,
        # so incidental `$...$` rendered as raw ```latex. A two-line fence
        # safety hint is enough — not the full math pack.
        system_parts.append(MATH_FENCE_SAFETY_HINT)
    else:
        system_parts.extend(
            _style_format_hints(
                query_text=query_text,
                style=style,
                is_day_plan=is_day_plan,
                minimal_personal_context=minimal_personal_context,
                compact=compact_format,
                image_generation_enabled=settings.image_generation_enabled,
                lesson=lesson,
                prior_messages=prior_messages,
            )
        )
    system_parts.append(response_tone_service.tone_hint(getattr(user, "response_tone", None)))
    system_parts.append(TONE_FORMAT_GUARD)
    custom_block = _custom_instructions_block(user)
    if custom_block:
        system_parts.append(custom_block)
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
                gmail_todos_section=blocks.gmail_todos_section,
                summary=summary,
                chat_history_rag_block=chat_history_rag_block,
            )
        )
    elif load_memory or recalls_shared_past:
        if blocks.memory_block:
            system_parts.append(wrap_untrusted("memory", blocks.memory_block, first_party=True))
        if chat_history_rag_block:
            system_parts.append(chat_history_rag_block)
        if advice_memory and not (query_text and is_capabilities_question(query_text)):
            system_parts.append(ADVICE_PERSONALIZE_HINT)

    if math_followup:
        system_parts.extend([MATH_REPLY_POLICY, MATH_FOLLOWUP_HINT])
    elif chemistry_followup:
        system_parts.append(CHEMISTRY_FOLLOWUP_HINT)
    elif physics_followup:
        system_parts.append(PHYSICS_FOLLOWUP_HINT)

    # Keep the acknowledgement contract closest to the user turn. Memory and
    # integration context is appended after the style pack and can otherwise
    # tempt the model into an unsolicited plan even though no task was asked.
    if query_text and is_personal_disclosure_turn(query_text):
        system_parts.append(PERSONAL_DISCLOSURE_HINT)

    messages: list[dict[str, str]] = [{"role": "system", "content": "\n\n".join(system_parts)}]
    gap_ids = {m.id for m in gap}
    for msg in (*gap, *recent):
        content = msg.content
        if msg.id in gap_ids:
            content = trim_message_for_summary(content)
        if msg.role == "user":
            content = wrap_persisted_attachment_excerpts(content)
        elif msg.role == "assistant":
            prior_result = (
                readable_standalone_answer(content)
                if math_followup and msg is followup_exchange[-1]
                else None
            )
            content = prior_result or _strip_prompt_owned_fences(content)
        messages.append({"role": msg.role, "content": content})
    # Repeat only the machine-checkable turn contract immediately before the
    # current user message. Smaller low-latency models follow nearby system
    # constraints more reliably than a clause inside the large base prompt.
    nearby_contracts: list[str] = []
    if query_text and is_learning_plan_request(query_text):
        daily_contract = learning_plan_daily_contract(query_text)
        if daily_contract:
            nearby_contracts.append(daily_contract)
    if query_text and is_teaching_request(query_text):
        code_contract = programming_lesson_contract(query_text)
        if code_contract:
            nearby_contracts.append(code_contract)
    if nearby_contracts:
        messages = inject_before_last_user(messages, "\n\n".join(nearby_contracts))
    return messages

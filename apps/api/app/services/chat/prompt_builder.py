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
from app.models.orm import Chat, User
from app.models.schemas.math import MathImageExtract
from app.modules import memory as memory_service
from app.modules import todos as todos_service
from app.modules import web_search as web_search_service
from app.modules.integrations import calendar as calendar_service
from app.modules.integrations import inbox as email_service
from app.modules.math.followup import (
    MATH_FOLLOWUP_HINT,
    is_math_followup,
    readable_standalone_answer,
)
from app.modules.math.reply_policy import MATH_REPLY_POLICY
from app.modules.math.tools.extract import is_graph_followup
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.services import locale as locale_service
from app.services import profile as profile_service
from app.services import response_tone as response_tone_service
from app.services import time_context as time_context_service
from app.services.chat import tools as chat_tools_service
from app.services.chat.continuation_subject import (
    blocks_math_followup,
    effective_presentation_subject,
)
from app.services.chat.prompt_constants import (
    ADVICE_PERSONALIZE_HINT,
    BIOLOGY_PRESENTATION_HINT,
    BREVITY_REQUEST_HINT,
    BROAD_SELF_ANSWER_HINT,
    CALLOUT_FORMAT_HINT,
    CAPABILITIES_FORMAT_HINT,
    CHART_FORMAT_HINT,
    CHEMISTRY_PRESENTATION_HINT,
    CLARIFICATION_HINT,
    COMPACT_RESPONSE_FORMAT_HINT,
    COMPARISON_FORMAT_HINT,
    CONFIRM_FOLLOW_THROUGH_HINT,
    COPY_DELIVERABLE_HINT,
    DAY_PLANNING_ANSWER_HINT,
    EMAIL_ASK_PURPOSE_HINT,
    EMAIL_DRAFT_HINT,
    FORMAT_CONTRACT,
    HOWTO_FORMAT_HINT,
    LEARNING_PLAN_HINT,
    LIGHTWEIGHT_REPLY_HINT,
    MATH_FENCE_SAFETY_HINT,
    MATH_INTENT_HINT,
    MATH_SHORT_RESPONSE_HINT,
    MATH_SOLVER_HINT,
    MATH_TUTORING_HINT,
    MERMAID_FORMAT_HINT,
    NON_DRAFT_TURN_HINT,
    PERSONAL_DISCLOSURE_HINT,
    PHYSICS_INTENT_HINT,
    PHYSICS_REPLY_POLICY,
    PHYSICS_SHORT_HINT,
    PRIVACY_HINT,
    PROSE_WRITING_HINT,
    QUOTE_FORMAT_HINT,
    SEQUENCE_FORMAT_HINT,
    SHORT_MATH_SAFETY_HINT,
    SHORT_RESPONSE_FORMAT_HINT,
    SOCIAL_DRAFT_HINT,
    STATISTICS_PRESENTATION_HINT,
    STYLE_HINTS,
    TEACHING_HINT,
    TEACHING_SHORT_NOTE,
    TONE_FORMAT_GUARD,
    TRANSLATION_FORMAT_HINT,
    UNIVERSAL_FORMAT_BASELINE,
    VERIFIED_SOLVE_SAFETY_HINT,
    VISUALIZATION_HINTS,
    WRITING_LINE_HINT,
    active_lesson_step,
    is_bare_writing_line,
    is_brevity_request,
    is_broad_self_question,
    is_callout_question,
    is_capabilities_question,
    is_chart_question,
    is_email_or_message_request,
    is_howto_question,
    is_learning_plan_request,
    is_mermaid_question,
    is_personal_disclosure_turn,
    is_quote_question,
    is_sequence_diagram_question,
    is_short_confirmation,
    is_structured_comparison_question,
    is_teaching_request,
    is_underspecified_writing_request,
    learning_plan_daily_contract,
    lesson_continue_hint,
    programming_lesson_contract,
    recalls_earlier_conversation,
    writing_request_kind,
)
from app.services.chat.prompt_constants.visuals import (
    IMAGE_GEN_HONESTY_HINT,
    IMAGE_GEN_UNAVAILABLE_HINT,
    is_html_ui_question,
    is_image_generation_mention,
)
from app.services.chat.stream_status import StreamStatusFn
from app.services.context_window import (
    UNSUMMARIZED_GAP_MAX_MESSAGES,
    estimate_tokens,
    messages_within_token_budget,
    select_recent_window,
    trim_message_for_summary,
    unsummarized_gap_bounds,
)
from app.services.day_planning import is_day_planning_question, is_day_reflection_question
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
_SLIM_MEMORY_MAX_CHARS = 1000
_BROAD_SELF_HISTORY_QUERY = (
    "Personal details the user stated about their background, work, employer, interests, "
    "preferences, communication style, goals, and active projects"
)


def _cap_slim_memory_block(block: str) -> str:
    if len(block) <= _SLIM_MEMORY_MAX_CHARS:
        return block

    lines = block.splitlines()
    if not lines:
        return ""

    # Memory blocks are rendered as a title followed by section headings and
    # bullet facts. Keep complete facts and skip any one fact that does not fit;
    # slicing the string can turn a remembered detail into a different claim.
    packed = [lines[0]]
    current_heading: str | None = None
    emitted_heading: str | None = None
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            current_heading = stripped
            continue
        if not stripped.startswith("- "):
            continue

        addition: list[str] = []
        if current_heading and current_heading != emitted_heading:
            addition.extend(["", current_heading])
        addition.append(stripped)
        trial = "\n".join([*packed, *addition])
        if len(trial) > _SLIM_MEMORY_MAX_CHARS:
            continue
        packed.extend(addition)
        emitted_heading = current_heading

    return "\n".join(packed) if len(packed) > 1 else ""


def _strip_prompt_owned_fences(content: str) -> str:
    """Drop solver/search fences from assistant history before the model sees them.

    Persisted messages keep the fences for the client. Re-injecting ```answer /
    ```graph / ```sources into the recent window teaches the model to copy them.
    """
    out = content
    for lang in _PROMPT_STRIP_FENCE_LANGS:
        out = strip_closed_fences(out, lang)
    return out


def _subject_viz_intent(query_text: str | None) -> tuple[str | None, bool]:
    if not query_text or not query_text.strip():
        return None, False
    subject = detect_subject(query_text)
    viz_intent = (
        is_chart_question(query_text)
        or is_mermaid_question(query_text)
        or is_html_ui_question(query_text)
    )
    return subject, viz_intent


def _physics_turn(query_text: str | None) -> bool:
    """Compatibility helper for callers/tests; detection is subject-neutral."""
    return bool(query_text and detect_subject(query_text) == "physics")


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


@dataclass
class _PromptContextBlocks:
    memory_block: str
    todos_section: str | None
    gmail_todos_section: str | None
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
    slim_context: bool,
    client_timezone: str | None,
    out: dict[str, object] | None,
    load_memory: bool = False,
    history_rag: bool = False,
    recent_messages: list[Any] | None = None,
) -> _PromptContextBlocks:
    """Load memory/todos/RAG + recent messages for the system prompt.

    Each gather branch opens a short-lived session so external HTTP (RAG/memory
    embed) cannot pin a caller's connection across the concurrent load.
    Chat-history query embed overlaps the gather; recent-window excludes are
    applied later when hits are filtered.
    """

    async def _history_rag_embed() -> list[float] | None:
        if not history_rag or not query_text or not query_text.strip():
            return None
        from app.services.chat import history_rag as chat_history_rag_service

        history_query = (
            _BROAD_SELF_HISTORY_QUERY if is_broad_self_question(query_text) else query_text
        )
        return await chat_history_rag_service.embed_query_for_prompt(
            settings, user_id=user.id, query=history_query
        )

    async def _fetch_recent() -> list[Any]:
        if recent_messages is not None:
            return recent_messages
        async with SessionLocal() as s:
            return await messages_repo.list_recent(s, chat_id, limit=recent_limit)

    if slim_context and not load_memory:
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
            gmail_todos_section=None,
            recent_all=recent_all,
            attachment_rag_block="",
            chat=chat,
            history_rag_query_vec=history_rag_query_vec,
        )

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
                exclude_sensitive=memory_service.exclude_sensitive_for_query(query_text),
            )

    if slim_context and load_memory:
        recent_all, memory_block, history_rag_query_vec = await asyncio.gather(
            _fetch_recent(),
            _memory_block(),
            _history_rag_embed(),
        )
        if out is not None:
            out["recalled"] = 0
            out["memory_hints"] = []
        return _PromptContextBlocks(
            memory_block=_cap_slim_memory_block(memory_block),
            todos_section=None,
            gmail_todos_section=None,
            recent_all=recent_all,
            attachment_rag_block="",
            chat=chat,
            history_rag_query_vec=history_rag_query_vec,
        )

    if chat is None:
        async with SessionLocal() as s:
            chat = await chats_repo.get_by_id(s, chat_id, user.id)

    async def _todos_section() -> tuple[str | None, str | None]:
        async with db_slots, SessionLocal() as s:
            loaded = await todos_service.build_todos_system_section(
                s,
                user,
                settings,
                client_timezone=client_timezone,
                query_text=query_text,
            )
        if loaded is None:
            return None, None
        if isinstance(loaded, todos_service.TodosPromptSections):
            return loaded.own, loaded.gmail
        if isinstance(loaded, str):
            return loaded, None
        return None, None

    async def _attachment_rag_block() -> str:
        # HTTP/embed-bound — do not hold a DB pool slot.
        if not settings.attachment_rag_enabled or not query_text:
            return ""
        from app.modules.attachments import rag as attachment_rag_service

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
        todos_payload,
        recent_all,
        attachment_rag_block,
        history_rag_query_vec,
    ) = await asyncio.gather(
        _memory_block(),
        _todos_section(),
        _load_recent(),
        _attachment_rag_block(),
        _history_rag_embed(),
    )
    todos_section, gmail_todos_section = todos_payload
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
        gmail_todos_section=gmail_todos_section,
        recent_all=recent_all,
        attachment_rag_block=attachment_rag_block,
        chat=chat,
        history_rag_query_vec=history_rag_query_vec,
    )


def _layout_format_hint(query_text: str | None) -> str | None:
    """Turn-specific layout that must win over compact prose."""
    if not query_text:
        return None
    if is_brevity_request(query_text):
        return None
    # A requested deliverable owns its shape. For example, "write a LinkedIn
    # post comparing X and Y" is a post—not a comparison table with a post
    # awkwardly appended afterward. Its writing-specific hint handles any
    # explicit side-by-side/table request inside the deliverable.
    if writing_request_kind(query_text) is not None:
        return None
    if is_chart_question(query_text):
        return CHART_FORMAT_HINT
    if is_sequence_diagram_question(query_text):
        return SEQUENCE_FORMAT_HINT
    if is_mermaid_question(query_text):
        return MERMAID_FORMAT_HINT
    # Explicit "teach me" intent owns the interaction shape. A topic may also
    # contain "vs" / "difference between", but the user asked for a lesson, not
    # a one-shot comparison table. Explicit visual requests above still win.
    if is_learning_plan_request(query_text):
        return LEARNING_PLAN_HINT
    if is_teaching_request(query_text):
        return TEACHING_HINT
    if is_structured_comparison_question(query_text):
        return COMPARISON_FORMAT_HINT
    if is_quote_question(query_text):
        return QUOTE_FORMAT_HINT
    if is_callout_question(query_text):
        return CALLOUT_FORMAT_HINT
    if is_howto_question(query_text):
        return HOWTO_FORMAT_HINT
    return None


def _writing_format_hint(query_text: str | None) -> str | None:
    """Email / message / social / translation / prose shape. Edit stays compact."""
    if not query_text:
        return None
    kind = writing_request_kind(query_text)
    if kind in {"email", "message"}:
        if is_underspecified_writing_request(query_text):
            return EMAIL_ASK_PURPOSE_HINT
        return EMAIL_DRAFT_HINT
    if kind == "social":
        if is_underspecified_writing_request(query_text):
            return EMAIL_ASK_PURPOSE_HINT
        return SOCIAL_DRAFT_HINT
    if kind == "translation":
        return TRANSLATION_FORMAT_HINT
    if kind == "prose":
        return PROSE_WRITING_HINT
    return None


def _style_format_hints(
    *,
    query_text: str | None,
    style: str,
    is_day_plan: bool,
    minimal_personal_context: bool,
    compact: bool = False,
    image_generation_enabled: bool = True,
    lesson: tuple[int, int] | None = None,
    prior_messages: list[tuple[str, str]] | None = None,
) -> list[str]:
    """Clarification / day-planning / response-format hints for non-quiz turns.

    ``lesson`` is the (step, total) the previous reply taught, when it was a
    lesson step: this turn answers its check question, so the lesson goes on.

    ``compact`` is for greetings and pasted fragments only — not for
    "no personal data". Ordinary questions get FORMAT_CONTRACT; math/viz
    packs are intent-gated so general knowledge does not pay ~3k tokens.
    Writing deliverables replace compact / short / FORMAT_CONTRACT so a
    paragraph ask is not also told to use bullets or a compare table.
    """
    if query_text and is_capabilities_question(query_text):
        # FORMAT_CONTRACT / COPY_DELIVERABLE / CLARIFICATION all teach
        # ```email. A "what can you do" list then opens a draft card and
        # swallows the rest of the reply.
        return [
            PRIVACY_HINT,
            UNIVERSAL_FORMAT_BASELINE,
            CAPABILITIES_FORMAT_HINT,
            MATH_FENCE_SAFETY_HINT,
        ]
    if query_text and is_personal_disclosure_turn(query_text) and not lesson:
        # A first-person update is not an invitation to generate a guide. Keep
        # the contract small and decisive so the general rich-format pack
        # cannot turn "I work at Uber..." into an unsolicited career plan.
        # Mid-lesson, "I'm confused" answers the check question instead.
        return [
            CLARIFICATION_HINT,
            PRIVACY_HINT,
            NON_DRAFT_TURN_HINT,
            PERSONAL_DISCLOSURE_HINT,
            UNIVERSAL_FORMAT_BASELINE,
            SHORT_RESPONSE_FORMAT_HINT,
            MATH_FENCE_SAFETY_HINT,
        ]
    parts: list[str] = [CLARIFICATION_HINT, PRIVACY_HINT]
    writing = _writing_format_hint(query_text)
    learning_plan = bool(
        query_text
        and writing is None
        and not is_brevity_request(query_text)
        and is_learning_plan_request(query_text)
    )
    teaching = bool(
        query_text
        and writing is None
        and not is_brevity_request(query_text)
        and is_teaching_request(query_text)
    )
    # A new "teach me" starts its own lesson; otherwise the last step goes on.
    lesson_hint = (
        lesson_continue_hint(*lesson)
        if lesson and not teaching and not learning_plan and not writing
        else None
    )
    if query_text and writing is None:
        parts.append(NON_DRAFT_TURN_HINT)
    _, viz_intent = _subject_viz_intent(query_text)
    subject = effective_presentation_subject(query_text, prior_messages)
    if query_text and is_short_confirmation(query_text):
        parts.append(CONFIRM_FOLLOW_THROUGH_HINT)
    if query_text and is_day_planning_question(query_text):
        parts.append(DAY_PLANNING_ANSWER_HINT)
        if is_day_reflection_question(query_text):
            parts.append(
                "This is an end-of-day reflection — keep reminders, lists, calendar, and "
                "loose ends as the main focus."
            )
    if minimal_personal_context:
        parts.append(BROAD_SELF_ANSWER_HINT)
    if style == "short":
        parts.append(UNIVERSAL_FORMAT_BASELINE)
        # Explicit draft/prose still wins over "plain text, skip fences". A lesson
        # keeps its step headings, only smaller.
        if writing:
            parts.append(writing)
        elif learning_plan:
            # An explicit multi-day roadmap needs enough room to be actionable;
            # account-level short style must not collapse it into a vague paragraph.
            parts.append(LEARNING_PLAN_HINT)
        elif teaching:
            parts.extend([TEACHING_HINT, TEACHING_SHORT_NOTE])
        elif lesson_hint:
            parts.append(TEACHING_SHORT_NOTE)
        else:
            parts.append(SHORT_RESPONSE_FORMAT_HINT)
    elif is_day_plan:
        # Day-plan used to miss math guardrails. Keep a short fence-safety
        # line so incidental `$...$` still renders; keep FORMAT_CONTRACT so
        # a day outline can use headings.
        parts.append(UNIVERSAL_FORMAT_BASELINE)
        parts.append(writing if writing else FORMAT_CONTRACT)
    elif compact:
        # Slim/casual used to still get RESPONSE_FORMAT_HINT (tips/headings/
        # tables), so a pasted phrase became a funny essay with a clipped
        # table. ChatGPT-shaped: answer first, no invented chrome.
        parts.append(UNIVERSAL_FORMAT_BASELINE)
        layout = _layout_format_hint(query_text)
        # Compact "plain prose" turns chart/flowchart/compare asks into a
        # joke, table, or clipped 2-node mermaid. Those turns get a fence hint.
        # Writing kinds must win the same way or "one paragraph" becomes bullets.
        winner = writing or layout
        parts.append(winner if winner else COMPACT_RESPONSE_FORMAT_HINT)
    elif writing:
        parts.append(UNIVERSAL_FORMAT_BASELINE)
        parts.append(writing)
    else:
        parts.append(UNIVERSAL_FORMAT_BASELINE)
        parts.append(FORMAT_CONTRACT)
        if viz_intent:
            parts.append(VISUALIZATION_HINTS)
        layout = _layout_format_hint(query_text)
        if layout:
            parts.append(layout)
    if lesson_hint:
        parts.append(lesson_hint)
    if query_text and is_image_generation_mention(query_text):
        parts.append(
            IMAGE_GEN_HONESTY_HINT if image_generation_enabled else IMAGE_GEN_UNAVAILABLE_HINT
        )
    if subject == "physics":
        parts.append(VERIFIED_SOLVE_SAFETY_HINT)
        if style == "short" or compact:
            parts.append(PHYSICS_SHORT_HINT)
        else:
            parts.append(PHYSICS_INTENT_HINT)
    elif subject == "math":
        parts.append(VERIFIED_SOLVE_SAFETY_HINT)
        if style == "short" or compact:
            parts.append(SHORT_MATH_SAFETY_HINT)
            parts.append(MATH_SHORT_RESPONSE_HINT)
        else:
            parts.extend([MATH_INTENT_HINT, MATH_SOLVER_HINT, MATH_TUTORING_HINT])
    elif subject == "chemistry":
        parts.append(VERIFIED_SOLVE_SAFETY_HINT)
        parts.append(CHEMISTRY_PRESENTATION_HINT)
        parts.append(MATH_FENCE_SAFETY_HINT)
    elif subject == "statistics":
        parts.append(VERIFIED_SOLVE_SAFETY_HINT)
        parts.append(STATISTICS_PRESENTATION_HINT)
        parts.append(MATH_FENCE_SAFETY_HINT)
    elif subject == "biology":
        parts.append(VERIFIED_SOLVE_SAFETY_HINT)
        parts.append(BIOLOGY_PRESENTATION_HINT)
        parts.append(MATH_FENCE_SAFETY_HINT)
    else:
        parts.append(MATH_FENCE_SAFETY_HINT)
    if query_text and is_brevity_request(query_text):
        parts.append(BREVITY_REQUEST_HINT)
    writing_kind = writing_request_kind(query_text) if query_text else None
    # Specialized translation/prose hints already own the shape; the copy-fence
    # contract would tell the model to wrap an article in ```copy.
    if writing_kind not in {"translation", "prose"}:
        parts.append(COPY_DELIVERABLE_HINT)
    if query_text and is_bare_writing_line(query_text):
        parts.append(WRITING_LINE_HINT)
    if subject == "physics":
        parts.append(PHYSICS_REPLY_POLICY)
    elif subject == "math":
        # Keep requested detail last, after general layout and tutoring hints.
        parts.append(MATH_REPLY_POLICY)
    # Turn-derived hard contracts come after generic format/math/copy guidance
    # so smaller models cannot treat exact day coverage or a tagged example as
    # an optional style preference.
    if learning_plan and query_text:
        daily_contract = learning_plan_daily_contract(query_text)
        if daily_contract:
            parts.append(daily_contract)
    if teaching and query_text:
        code_contract = programming_lesson_contract(query_text)
        if code_contract:
            parts.append(code_contract)
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
    gmail_todos_section: str | None = None,
    summary: str | None,
    chat_history_rag_block: str = "",
) -> list[str]:
    """Time / web / calendar / gmail / memory / todos / summary hints."""
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
        parts.append(wrap_untrusted("schedule", todos_section, first_party=True))
    if gmail_todos_section:
        parts.append(wrap_untrusted("gmail reminders", gmail_todos_section))
    if chat_history_rag_block:
        parts.append(chat_history_rag_block)
    return parts


def _persisted_messages(window: list[Any], current_user_message_id: UUID | None) -> list[Any]:
    """Drop the synthetic current turn. It is not a stored row yet."""
    if current_user_message_id is None:
        return window
    return [
        message for message in window if getattr(message, "id", None) != current_user_message_id
    ]


async def _load_unsummarized_gap(
    chat_id: UUID,
    chat: Chat | None,
    window: list[Any],
    tail: list[Any],
    *,
    recent_limit: int,
    token_budget: int,
    current_user_message_id: UUID | None,
) -> list[Any]:
    """Messages after the summary and before the messages the prompt kept.

    ``tail`` is that kept list. A synthetic current user row can push one
    stored message out of a full window; that row is included here, then the
    whole gap is cut to the tokens the recent window did not already use.
    """
    tail_ids = {message.id for message in tail}
    dropped = [
        message
        for message in _persisted_messages(window, current_user_message_id)
        if message.id not in tail_ids
    ]
    older: list[Any] = []
    persisted = _persisted_messages(window, current_user_message_id)
    if chat is not None and len(persisted) >= recent_limit and persisted:
        oldest = persisted[0]
        created_at = getattr(oldest, "created_at", None)
        oldest_id = getattr(oldest, "id", None)
        if created_at is not None and oldest_id is not None:
            summarized = int(getattr(chat, "summary_message_count", 0) or 0)
            async with SessionLocal() as session:
                total = await messages_repo.count_for_chat(session, chat_id)
                bounds = unsummarized_gap_bounds(
                    total=total,
                    summarized=summarized,
                    loaded=len(persisted),
                )
                if bounds is not None:
                    _offset, count = bounds
                    older = await messages_repo.list_before(
                        session,
                        chat_id,
                        before_created_at=created_at,
                        before_id=oldest_id,
                        limit=count,
                    )
    return messages_within_token_budget(
        [*older, *dropped],
        token_budget,
        max_messages=UNSUMMARIZED_GAP_MAX_MESSAGES,
    )


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

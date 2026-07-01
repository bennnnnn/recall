import asyncio
import json
import logging
import random
import re
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
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import User
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.repositories import usage as usage_repo
from app.repositories import users as users_repo
from app.services import calendar as calendar_service
from app.services import chat_tools as chat_tools_service
from app.services import email as email_service
from app.services import locale as locale_service
from app.services import math_fence as math_fence_service
from app.services import math_tools as math_tools_service
from app.services import memory as memory_service
from app.services import plan as plan_service
from app.services import profile as profile_service
from app.services import projects as projects_service
from app.services import quota as quota_service
from app.services import response_tone as response_tone_service
from app.services import time_context as time_context_service
from app.services import todos as todos_service
from app.services import web_search as web_search_service
from app.services.context_window import estimate_tokens, select_recent_window
from app.services.quota import quota_exceeded_message, utc_today

logger = logging.getLogger(__name__)

CLARIFICATION_HINT = (
    "When you lack information needed to complete a task correctly, ask concise clarifying "
    "questions instead of guessing, inventing details, or filling gaps with placeholders. "
    "Never use bracket placeholders like [name], [topic], or [TBD]. Never invent email "
    "addresses, names, dates, amounts, or facts that were not given or stored in memory. "
    "Exception — email/message drafting: when the user asks you to write or send an email, "
    "text, or message to someone (including relationships like my wife, my boss, mom), "
    "draft immediately in a ```email or ```message fence using memory; do NOT ask what the "
    "message should say. Omit To: if the address is not in memory — never invent it. "
    "For other tasks, if the user has not given enough context for a send-ready deliverable, "
    "ask 1-3 specific questions first and skip the copy fence until you have what you need. "
    "Use known facts from memory when available; if memory does not cover something, ask — "
    "never assume."
)

EMAIL_DRAFT_HINT = (
    "Email and message drafting (ChatGPT-style — draft first, refine after):\n"
    "When the user wants an email, text, or message written or sent:\n"
    "1. Put a complete, warm, send-ready draft inside ```email (or ```message for SMS). "
    "Include Subject: when you can infer one. Use To: only when the address is in memory or "
    "profile — never invent addresses.\n"
    "2. Resolve relationships from memory (my wife, my husband, mom, boss, etc.) to real "
    "names and emails when stored. Greet them by name in the body even if To: is omitted.\n"
    "3. After the fence, add at most ONE short line offering to adjust tone or length — "
    "not a questionnaire about content or recipient.\n"
    "4. Never ask 'what should the email say?' when they already named a recipient."
)

PRIVACY_HINT = (
    "Privacy: Profile, memory, reminders, lists, projects, calendar, and Gmail blocks in this "
    "prompt are internal context only — never dump them into a reply.\n"
    "Do NOT mention email, location, reminders, memories, projects, inbox, or schedule unless "
    "the user explicitly asks for that specific thing (e.g. 'what's my email?', 'what's due "
    "today?', 'what projects am I working on?') or the task obviously requires it.\n"
    "'Who are you?' / 'What can you do?' → describe Recall as an assistant; no personal data.\n"
    "'Who am I?' / 'Tell me about me' → at most their first name (or name from profile) and "
    "a brief, friendly line — do NOT list email, location, schedule, reminders, memories, "
    "or projects. Offer to share more if they ask for something specific.\n"
    "'What's my name?' → name only. 'What's my email?' → email only. 'Where am I?' → location only."
)

_BROAD_SELF_QUESTION = re.compile(
    r"^\s*(?:"
    r"who am i\??"
    r"|tell me about me\??"
    r"|what do you know about me\??"
    r"|describe me\??"
    r"|what(?:'re| are) i like\??"
    r")\s*[.!?]*\s*$",
    re.IGNORECASE,
)

BROAD_SELF_ANSWER_HINT = (
    "The user asked a general 'who am I' question. Reply with their first name (from profile) "
    "and ONE short friendly sentence — keep your configured tone. Do NOT mention location, email, "
    "work, projects, schedule, reminders, or memories. Offer to help if they ask for something "
    "specific."
)


def is_broad_self_question(text: str) -> bool:
    """Broad identity questions — name only, no personal context dump."""
    cleaned = text.strip()
    if not cleaned or time_context_service.is_location_question(cleaned):
        return False
    return bool(_BROAD_SELF_QUESTION.match(cleaned))


_WRITING_DELIVERABLE = re.compile(
    r"\b("
    r"send (?:me )?(?:an? )?email|"
    r"email (?:to|my)|"
    r"write (?:me )?(?:an? )?email|"
    r"draft (?:an? )?email|"
    r"compose (?:an? )?email|"
    r"send (?:a )?(?:text|message)|"
    r"text (?:to|my)|"
    r"message (?:to|my)"
    r")\b",
    re.IGNORECASE,
)


def is_writing_deliverable_request(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_WRITING_DELIVERABLE.search(cleaned))


QUIZ_ANSWER_HINT = (
    "The user just answered a vocabulary quiz with A, B, C, or D. "
    "The previous assistant message has the question and choices.\n"
    "If correct: congratulate briefly, give one example sentence, then ask the next question.\n"
    "If wrong: gently correct, explain the meaning, encourage them, then offer to continue.\n"
    "When asking the next question, use the quiz card format:\n"
    f"{projects_service.VOCAB_QUIZ_FORMAT_BLOCK}\n"
    "One question per message — wait for their letter before revealing the answer.\n"
    "On every correct answer, sync MUST master the quizzed word immediately.\n"
    "Keep feedback short and encouraging."
)

_QUIZ_RECENT_MESSAGE_LIMIT = 12

COPY_DELIVERABLE_HINT = (
    "When drafting text the user will copy and send (SMS, email, reply, caption, "
    "social post, etc.), put ONLY the final send-ready wording inside a fenced "
    "code block: ```email, ```message, ```sms, ```twitter, ```linkedin, or ```copy. "
    "Use at most ONE such fence per response. "
    "Copy blocks must be ready to paste and send as-is: complete sentences, real names "
    "and subjects from context or memory — never [placeholders] or TBD. "
    "For email/message requests with a named recipient, ALWAYS include the ```email fence "
    "with a full draft — do not ask what to write first. "
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
    'This is the right format for rankings ("top N …"), lists of facts, '
    "recommendations, pros/cons, and general Q&A.\n"
    "  - Only use a pipe table when the user explicitly asks for a table, or "
    "when comparing 4+ items across 3+ clear columns where a table is genuinely "
    "easier to read than a list.\n"
    '  - For a single topic ("tell me about X"), use 2-3 short headings with '
    "bullets — not a wall of text and not a kv block.\n"
    "\n"
    "Writing helper (email, message, reply, caption, social post):\n"
    "  - Put the final send-ready text inside ```email, ```message, ```sms, or "
    "```copy. At most ONE such fence per response. For email/message to a named "
    "person, draft immediately — do not ask what to write.\n"
    "\n"
    "How-to / troubleshooting:\n"
    "  - Numbered steps (1. … 2. …). Add a brief tip or warning only when needed.\n"
    "\n"
    "Math / algebra / numeric answers:\n"
    "  - For display formulas use a ```math fence or inline `$x^2 + 2 = 6$` — "
    "NEVER ```latex or a plain code block with raw LaTeX.\n"
    "  - ALWAYS use caret exponents (`x^2`, never `x2`). Use LaTeX: \\pm, \\sqrt{}, "
    "\\frac{a}{b}.\n"
    "  - When SymPy verified results appear in a system block, use those exact "
    "numbers — do NOT recompute.\n"
    "  - Show numbered solution steps, then the final answer.\n"
    '  - Add a short verification block titled "You can check:" (or '
    '"Verification:") with bullet lines that substitute each intermediate step '
    "or the final result back into the original expression. Wrap each check "
    "expression in $...$ and end the line with `- [x]` or a trailing ✓.\n"
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

MATH_SOLVER_HINT = (
    "Math diagrams and plots (NOT image generation):\n"
    "- When the user asks to **draw** a rectangle, square, triangle, or right triangle, emit a ```geometry fence "
    "(NEVER ```json) so the app renders a labeled SVG:\n"
    'Rectangle: ```geometry\n{"type":"rectangle","width":8,"height":5,"unit":"cm",'
    '"show_diagonal":true,"show_angle":true}\n```\n'
    'Square: ```geometry\n{"type":"square","side":5,"unit":"cm","show_diagonal":true,'
    '"show_area":true}\n```\n'
    'Also accepted: `"type":"rect"`, or width/height via length/breadth/w/h fields.\n'
    'Triangle: ```geometry\n{"type":"triangle","base":8,"height":5,"unit":"cm",'
    '"show_labels":true}\n```\n'
    'Right triangle: ```geometry\n{"type":"right_triangle","base":6,"height":4,"unit":"cm",'
    '"show_labels":true,"show_hypotenuse":true,"show_angle":true}\n```\n'
    "- For function plots y=f(x), emit ONLY ```graph (NEVER ```json):\n"
    '```graph\n{"type":"function","expr":"x**2","variable":"x","x_min":-5,'
    '"x_max":5,"points":[[-5,25],[-4,16]]}\n```\n'
    "  Include the points array when provided in verified SymPy results.\n"
    "- For display formulas use ```math or inline $...$ — NEVER ```latex, ```tex, or "
    "untagged code blocks for LaTeX.\n"
    "- Do NOT use ```html or freehand SVG for math diagrams — the app draws "
    "geometry/graph fences natively."
)

VISUALIZATION_HINTS = (
    "In-app visuals (only when appropriate — not for image-generation requests):\n\n"
    "**Image generation** — You CANNOT create photo/image files (PNG, JPG, etc.). "
    "If the user asks to generate, draw, create, or make an image/picture/photo/illustration "
    "and is NOT asking you to analyze an uploaded attachment or render a math diagram, "
    "do NOT output ```html, SVG, or CSS art as a substitute. Math rectangles and function "
    "plots use ```geometry and ```graph JSON fences (see math solver hint). "
    "Say briefly that Recall cannot generate arbitrary images yet when asked for photos/art.\n\n"
    "**HTML UI** (```html) — Use ONLY when the user wants a web UI, page, form, card, layout, "
    "login screen, dashboard, landing page, or interactive mockup — NOT for 'draw me X' or "
    "'create an image of X'. Output actual HTML with a <style> block; the app renders it natively.\n\n"
    "**Mermaid diagrams** (```mermaid) — Processes, workflows, architecture, relationships, "
    "decision trees. Prefer over bullet lists when showing connections.\n\n"
    "**Charts** (```chart) — Vega-Lite JSON for numeric comparisons and trends.\n\n"
    "**Geometry** (```geometry) — JSON spec for rectangles/squares with labels, diagonals, area.\n\n"
    "**Graphs** (```graph) — JSON spec with expr + points for y=f(x) plots.\n\n"
    "**Places** (```places) — JSON array of {name, url, note?, address?, price?} for local "
    "venue recommendations (any nearby place). Use when the user asks for something "
    "near them — nearest/closest/nearby — regardless of category.\n\n"
    "**Quotes** (```quote) — A notable quote with optional attribution on the last line as "
    "“— Author”. Use for pull-quotes; plain `>` blockquotes also work.\n\n"
    "For uploaded images, describe or answer about what you see — do not redraw them in HTML."
)

STYLE_HINTS = {
    "short": (
        "Response length: SHORT. The user chose brevity — this overrides default formatting length. "
        "Answer in 1-3 sentences or at most 4-5 tight bullets. No preamble, no recap of the question, "
        "no closing offers to help further. Skip sections, headings, tables, diagrams, and HTML unless "
        "the user explicitly asked for them."
    ),
    "balanced": (
        "Response length: BALANCED. Be clear and complete without rambling — use short headings and "
        "bullets when helpful, but keep the overall reply moderate in length."
    ),
    "detailed": (
        "Response length: DETAILED. Be thorough but stay scannable: sections, bullets, tables, "
        "and ```kv blocks — not essay-style paragraphs. Include examples and nuance where useful."
    ),
}

SHORT_RESPONSE_FORMAT_HINT = (
    "Formatting for SHORT mode: plain text or a few bullets only. No ## headings. "
    "No pipe tables. No ```html / ```mermaid / ```chart unless the user explicitly requested a visual."
)

STYLE_OUTPUT_TOKEN_CAP = {
    "short": 400,
    "balanced": 1200,
    "detailed": 2200,
}


def max_output_tokens_for_style(response_style: str, settings: Settings) -> int:
    if response_style == "short":
        return min(STYLE_OUTPUT_TOKEN_CAP["short"], settings.max_output_tokens)
    if response_style == "detailed":
        return max(settings.max_output_tokens, STYLE_OUTPUT_TOKEN_CAP["detailed"])
    return settings.max_output_tokens


@dataclass
class _StreamContext:
    user_id: UUID
    chat_id: UUID
    model: str
    prompt_messages: list[dict[str, Any]]
    run_title: bool
    user_message_content: str
    reserved_tokens: int
    max_output_tokens: int
    recalled_count: int = 0
    memory_hints: list[str] = field(default_factory=list)
    context_summarized: int = 0
    instant_reply: str | None = None
    search_sources: list[WebSearchHit] = field(default_factory=list)
    local_places: bool = False
    skip_memory_jobs: bool = False


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
) -> tuple[list[dict[str, str]], list[WebSearchHit]]:
    """Web search always uses the full direct path; MCP handles calendar/sympy only."""
    updated, search_sources = await web_search_service.augment_prompt_messages(
        prompt_messages,
        user_content,
        settings,
        user_timezone=user_timezone,
        user_location=user_location,
        latitude=latitude,
        longitude=longitude,
        prior_user_messages=prior_user_messages,
    )

    if settings.mcp_tools_enabled:
        updated = await chat_tools_service.augment_prompt_with_mcp_tools(
            updated,
            user_content,
            settings,
            user_timezone=user_timezone,
            user_location=user_location,
            prior_user_messages=prior_user_messages,
        )

    updated = await math_tools_service.augment_prompt_messages(
        updated,
        user_content,
        settings,
        has_image_attachment=has_image_attachment,
    )
    return updated, search_sources


async def build_prompt_messages(
    session: AsyncSession,
    user: User,
    chat_id: UUID,
    settings: Settings,
    *,
    summary: str | None = None,
    out: dict[str, object] | None = None,
    query_text: str | None = None,
    minimal_personal_context: bool = False,
    minimal_quiz_context: bool = False,
    client_timezone: str | None = None,
    prompt_location: str | None = None,
) -> list[dict[str, str]]:
    recent_limit = (
        _QUIZ_RECENT_MESSAGE_LIMIT if minimal_quiz_context else settings.recent_message_window
    )
    chat = None
    todos_section: str | None = None
    if minimal_personal_context or minimal_quiz_context:
        recent_all = await messages_repo.list_recent(session, chat_id, limit=recent_limit)
        memory_block = ""
        projects_block = ""
        if out is not None:
            out["recalled"] = 0
            out["memory_hints"] = []
    else:
        chat = await chats_repo.get_by_id(session, chat_id, user.id)

        async def _projects_block() -> str:
            if chat and chat.project_id:
                return await projects_service.load_project_for_prompt(
                    session, user.id, chat.project_id, settings
                )
            return await projects_service.load_projects_for_prompt(session, user.id, settings)

        memory_block, todos_section, projects_block, recent_all = await asyncio.gather(
            memory_service.get_memory_block(session, user, settings, query_text=query_text),
            todos_service.build_todos_system_section(
                session,
                user,
                settings,
                client_timezone=client_timezone,
                query_text=query_text,
            ),
            _projects_block(),
            messages_repo.list_recent(session, chat_id, limit=recent_limit),
        )
        if out is not None:
            # `format_memory_block` emits one `## {Label}` header per injected
            # memory section — count those (not "- " bullets, which it never
            # produces). Guard against memory text that itself contains "## ".
            labels = set(memory_service.SECTION_LABELS.values())
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
    local_tz = time_context_service.effective_timezone(user.timezone, client_timezone)

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
        system_parts.extend([QUIZ_ANSWER_HINT, PRIVACY_HINT])
        chat = await chats_repo.get_by_id(session, chat_id, user.id)
        if chat and chat.project_id:
            quiz_ctx = await projects_service.load_project_quiz_context(
                session, user.id, chat.project_id, settings
            )
            if quiz_ctx:
                system_parts.append(quiz_ctx)
    else:
        system_parts.extend([CLARIFICATION_HINT, PRIVACY_HINT])
        if minimal_personal_context:
            system_parts.append(BROAD_SELF_ANSWER_HINT)
        if style == "short":
            system_parts.append(SHORT_RESPONSE_FORMAT_HINT)
        else:
            system_parts.extend(
                [INTENT_FORMAT_HINT, MATH_SOLVER_HINT, RESPONSE_FORMAT_HINT, VISUALIZATION_HINTS]
            )
        system_parts.append(COPY_DELIVERABLE_HINT)
        if query_text and is_writing_deliverable_request(query_text):
            system_parts.append(EMAIL_DRAFT_HINT)
    system_parts.append(response_tone_service.tone_hint(getattr(user, "response_tone", None)))
    locale_hint = locale_service.locale_system_hint(user.locale)
    if locale_hint:
        system_parts.append(locale_hint)
    if not minimal_quiz_context and not minimal_personal_context:
        system_parts.append(
            time_context_service.format_time_context(local_tz, user.locale, location_for_context)
        )
        if settings.web_search_enabled:
            system_parts.append(web_search_service.WEB_SEARCH_HINT)
            if query_text and web_search_service.is_ambiguous_local_places_query(query_text):
                system_parts.append(web_search_service.AMBIGUOUS_NEARBY_HINT)
            elif query_text and web_search_service.is_places_list_query(query_text):
                system_parts.append(web_search_service.LOCAL_PLACES_FORMAT_HINT)
            elif query_text and web_search_service.is_distance_query(query_text):
                system_parts.append(web_search_service.GEO_DISTANCE_HINT)
            if prompt_location and query_text and web_search_service.is_geo_query(query_text):
                system_parts.append(web_search_service.GEO_ACTIVE_LOCATION_HINT)
        if settings.google_calendar_enabled:
            system_parts.append(calendar_service.CALENDAR_HINT)
        if settings.gmail_enabled:
            system_parts.append(email_service.GMAIL_HINT)
        if memory_block:
            system_parts.append(memory_block)
        if todos_section:
            system_parts.append(todos_section)
        system_parts.append(projects_service.PROJECT_HINT)
        if projects_block:
            system_parts.append(projects_block)
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
    attachment_ids: list[UUID] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    result: dict[str, Any] | None = None,
    client_timezone: str | None = None,
    client_location: str | None = None,
    client_latitude: float | None = None,
    client_longitude: float | None = None,
) -> AsyncIterator[str]:
    async with SessionLocal() as session:
        user = await users_repo.get_by_id(session, user_id)
        if user is None:
            raise ChatNotFoundError("User not found.")
        daily_limit = quota_service.daily_limit_for_user(user, settings)

    reserved = estimate_tokens(content) + settings.max_output_tokens
    if not await quota_service.reserve_usage(
        redis, str(user_id), reserved, daily_limit=daily_limit
    ):
        raise QuotaExceededError(quota_exceeded_message(user))

    try:
        ctx = await _prepare_chat_turn(
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            model_alias=model_alias,
            settings=settings,
            redis=redis,
            reserved_tokens=reserved,
            attachment_ids=attachment_ids or [],
            client_timezone=client_timezone,
            client_location=client_location,
            client_latitude=client_latitude,
            client_longitude=client_longitude,
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
    client_timezone: str | None = None,
    client_location: str | None = None,
    client_latitude: float | None = None,
    client_longitude: float | None = None,
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

        model = plan_service.resolve_user_model_override(
            user, model_alias, last_user.content, settings
        )
        meta: dict[str, Any] = {}
        user_message_content = last_user.content
        minimal_personal = is_broad_self_question(user_message_content)
        minimal_quiz = web_search_service.is_vocab_quiz_answer(user_message_content)
        local_tz = time_context_service.effective_timezone(user.timezone, client_timezone)
        prompt_messages = await build_prompt_messages(
            session,
            user,
            chat_id,
            settings,
            summary=chat.summary,
            out=meta,
            query_text=user_message_content,
            minimal_personal_context=minimal_personal,
            minimal_quiz_context=minimal_quiz,
            client_timezone=client_timezone,
        )
        max_out = (
            max_output_tokens_for_style("short", settings)
            if minimal_quiz
            else max_output_tokens_for_style(user.response_style, settings)
        )
        if not minimal_personal and not minimal_quiz:
            integration_blocks: list[str] = []
            if calendar_service.should_inject_calendar_block(user_message_content):
                calendar_block = await calendar_service.load_calendar_for_prompt(
                    session, redis, user, settings
                )
                if calendar_block:
                    integration_blocks.append(calendar_block)
            if (
                not settings.mcp_tools_enabled
                and calendar_service.is_calendar_create_request(user_message_content)
                and await calendar_service.has_write_access(session, user.id)
            ):
                integration_blocks.append(calendar_service.CALENDAR_WRITE_HINT)
            if integration_blocks:
                prompt_messages[0] = {
                    "role": "system",
                    "content": f"{prompt_messages[0]['content']}\n\n"
                    + "\n\n".join(integration_blocks),
                }
        search_sources: list[WebSearchHit] = []
        local_places = web_search_service.is_places_list_query(user_message_content)
        if (
            not minimal_personal
            and not minimal_quiz
            and not calendar_service.is_external_calendar_question(user_message_content)
        ):
            prior_user_messages = await messages_repo.recent_user_contents(session, chat_id)
            prompt_messages, search_sources = await _augment_web_and_tools(
                prompt_messages,
                user_message_content,
                settings,
                user_timezone=local_tz,
                user_location=profile_service.user_location_label(user),
                prior_user_messages=prior_user_messages,
            )

    reserved = estimate_tokens(user_message_content) + max_out
    daily_limit = quota_service.daily_limit_for_user(user, settings)
    if not await quota_service.reserve_usage(
        redis, str(user_id), reserved, daily_limit=daily_limit
    ):
        raise QuotaExceededError(quota_exceeded_message(user))

    ctx = _StreamContext(
        user_id=user_id,
        chat_id=chat_id,
        model=model,
        prompt_messages=prompt_messages,
        run_title=False,
        user_message_content=user_message_content,
        reserved_tokens=reserved,
        max_output_tokens=max_out,
        recalled_count=int(meta.get("recalled") or 0),
        memory_hints=list(meta.get("memory_hints") or []),
        context_summarized=int(meta.get("context_summarized") or 0),
        search_sources=search_sources,
        local_places=local_places,
        skip_memory_jobs=minimal_quiz,
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


async def stream_edit_response(
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    message_id: UUID,
    new_content: str,
    model_alias: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
    result: dict[str, Any] | None = None,
    client_timezone: str | None = None,
    client_location: str | None = None,
    client_latitude: float | None = None,
    client_longitude: float | None = None,
) -> AsyncIterator[str]:
    """Replace a user message and delete all turns after it, then re-stream."""
    content = new_content.strip()
    if not content:
        raise ChatNotFoundError("Message cannot be empty.")

    async with SessionLocal() as session:
        user = await users_repo.get_by_id(session, user_id)
        if user is None:
            raise ChatNotFoundError("User not found.")
        chat = await chats_repo.get_by_id(session, chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError("Chat not found.")
        target = await messages_repo.get_by_id(session, message_id, chat_id)
        if target is None or target.role != "user":
            raise ChatNotFoundError("Only user messages can be edited.")
        await messages_repo.delete_messages_from(
            session, chat_id, from_created_at=target.created_at
        )

    async for token in stream_chat_response(
        redis,
        settings,
        user_id=user_id,
        chat_id=chat_id,
        content=content,
        model_alias=model_alias,
        should_cancel=should_cancel,
        result=result,
        client_timezone=client_timezone,
    ):
        yield token


async def _prepare_chat_turn(
    *,
    user_id: UUID,
    chat_id: UUID,
    content: str,
    model_alias: str | None,
    settings: Settings,
    redis: Redis,
    reserved_tokens: int,
    attachment_ids: list[UUID] | None = None,
    client_timezone: str | None = None,
    client_location: str | None = None,
    client_latitude: float | None = None,
    client_longitude: float | None = None,
) -> _StreamContext:
    async with SessionLocal() as session:
        user = await users_repo.get_by_id(session, user_id)
        if user is None:
            raise ChatNotFoundError("User not found.")

        chat = await chats_repo.get_by_id(session, chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError("Chat not found.")

        model = plan_service.resolve_user_model_override(user, model_alias, content, settings)
        has_image_attachment = False
        prior_count = await messages_repo.count_for_chat(session, chat_id)

        normalized_client_location = profile_service.normalize_client_location(client_location)
        client_coordinates = profile_service.normalize_client_coordinates(
            client_latitude, client_longitude
        )
        if normalized_client_location and (
            user.location != normalized_client_location or not user.location_enabled
        ):
            user = await users_repo.update(
                session,
                user,
                location=normalized_client_location,
                location_enabled=True,
            )
        user_location = profile_service.effective_location_label(user, normalized_client_location)
        geo_query = web_search_service.is_geo_query(content)
        if geo_query:
            # Geo searches use fresh device GPS only — not a stale profile city.
            user_location = normalized_client_location
        client_lat: float | None = None
        client_lng: float | None = None
        if client_coordinates is not None:
            client_lat, client_lng = client_coordinates
        has_geo_fix = bool(user_location) or client_coordinates is not None

        user_content = content
        gateway = None
        image_attachments: list[tuple[str, str]] = []
        if attachment_ids and settings.attachments_enabled:
            from app.gateways.storage_gateway import get_storage_gateway
            from app.repositories import attachments as attachments_repo
            from app.services import attachment_content as attachment_content_service

            gateway = get_storage_gateway(settings)
            attachment_lines: list[str] = []
            for attachment_id in attachment_ids:
                row = await attachments_repo.get_by_id(session, attachment_id, user.id)
                if row is None:
                    continue
                lines, is_image = await attachment_content_service.format_attachment_lines(
                    gateway,
                    attachment_id=str(attachment_id),
                    content_type=row.content_type,
                    storage_key=row.storage_key,
                    size_bytes=row.size_bytes,
                )
                if is_image:
                    has_image_attachment = True
                    image_attachments.append((row.content_type, row.storage_key))
                attachment_lines.extend(lines)
            if attachment_lines:
                if user_content.strip():
                    user_content = f"{user_content}\n\n" + "\n".join(attachment_lines)
                else:
                    user_content = "\n".join(attachment_lines)

        if attachment_ids and settings.attachments_enabled and has_image_attachment:
            model = "vision-chat"

        await messages_repo.create(
            session,
            chat_id=chat_id,
            user_id=user.id,
            role="user",
            content=user_content,
            model=model,
            input_tokens=estimate_tokens(user_content),
        )
        meta: dict[str, Any] = {}
        minimal_personal = is_broad_self_question(content)
        minimal_quiz = web_search_service.is_vocab_quiz_answer(content)
        local_tz = time_context_service.effective_timezone(user.timezone, client_timezone)
        prompt_messages = await build_prompt_messages(
            session,
            user,
            chat_id,
            settings,
            summary=chat.summary,
            out=meta,
            query_text=content,
            minimal_personal_context=minimal_personal,
            minimal_quiz_context=minimal_quiz,
            client_timezone=client_timezone,
            prompt_location=user_location if geo_query and has_geo_fix else None,
        )
        if has_image_attachment and image_attachments and gateway is not None:
            await attachment_content_service.inject_vision_content(
                prompt_messages,
                gateway,
                image_attachments,
                caption=content,
            )
        instant_reply = None
        gmail_context: tuple[str, list, list, str | None] | None = None
        if time_context_service.is_time_question(content):
            instant_reply = time_context_service.format_time_answer(local_tz, user.locale)
        elif time_context_service.is_location_question(content):
            instant_reply = time_context_service.format_location_answer(user_location, local_tz)

        elif calendar_service.is_external_calendar_question(content):
            if not await calendar_service.is_connected(session, user.id):
                instant_reply = calendar_service.format_not_connected_answer()
        elif email_service.is_external_email_question(content):
            if not await email_service.is_connected(session, user.id):
                instant_reply = email_service.format_not_connected_answer()
            else:
                gmail_context = await email_service.load_gmail_context(
                    session, redis, user, settings
                )
                if gmail_context is not None:
                    google_email, messages, pending, fetch_error = gmail_context
                    instant_reply = email_service.format_inbox_answer(
                        google_email=google_email,
                        messages=messages,
                        pending_suggestions=pending,
                        fetch_error=fetch_error,
                    )

        search_sources: list[WebSearchHit] = []
        geo_query = web_search_service.is_geo_query(content)
        local_places = web_search_service.is_places_list_query(content)
        ambiguous_nearby = web_search_service.is_ambiguous_local_places_query(content)
        if ambiguous_nearby:
            local_places = False
        if instant_reply is None and geo_query and not has_geo_fix:
            # No location available — prompt to enable it instead of guessing "near me".
            instant_reply = web_search_service.format_location_not_set_answer()
        if instant_reply is None and not minimal_personal and not minimal_quiz:
            integration_blocks: list[str] = []
            load_calendar = calendar_service.should_inject_calendar_block(content)
            load_gmail = email_service.should_inject_gmail_block(content)
            calendar_block: str | None = None
            gmail_block: str | None = None

            if load_calendar:
                calendar_block = await calendar_service.load_calendar_for_prompt(
                    session, redis, user, settings
                )
            if gmail_context is not None:
                google_email, messages, pending, fetch_error = gmail_context
                gmail_block = email_service.format_gmail_block(
                    google_email=google_email,
                    messages=messages,
                    pending_suggestions=pending,
                    fetch_error=fetch_error,
                )
            elif load_gmail:
                gmail_block = await email_service.load_gmail_for_prompt(
                    session, redis, user, settings
                )

            if calendar_block:
                integration_blocks.append(calendar_block)
            if gmail_block:
                integration_blocks.append(gmail_block)
            if (
                not settings.mcp_tools_enabled
                and calendar_service.is_calendar_create_request(content)
                and await calendar_service.has_write_access(session, user.id)
            ):
                integration_blocks.append(calendar_service.CALENDAR_WRITE_HINT)
            if integration_blocks:
                prompt_messages[0] = {
                    "role": "system",
                    "content": f"{prompt_messages[0]['content']}\n\n"
                    + "\n\n".join(integration_blocks),
                }
        if (
            instant_reply is None
            and not minimal_personal
            and not minimal_quiz
            and not ambiguous_nearby
            and not calendar_service.is_external_calendar_question(content)
            and not email_service.is_external_email_question(content)
        ):
            prior_user_messages = await messages_repo.recent_user_contents(session, chat_id)
            prompt_messages, search_sources = await _augment_web_and_tools(
                prompt_messages,
                content,
                settings,
                user_timezone=local_tz,
                user_location=user_location,
                latitude=client_lat,
                longitude=client_lng,
                prior_user_messages=prior_user_messages,
                has_image_attachment=has_image_attachment,
            )

        quiz_answer = web_search_service.is_vocab_quiz_answer(content)
        max_out = (
            max_output_tokens_for_style("short", settings)
            if quiz_answer
            else max_output_tokens_for_style(user.response_style, settings)
        )

        return _StreamContext(
            user_id=user_id,
            chat_id=chat_id,
            model=model,
            prompt_messages=prompt_messages,
            run_title=prior_count == 0,
            user_message_content=content,
            reserved_tokens=reserved_tokens,
            max_output_tokens=max_out,
            recalled_count=int(meta.get("recalled") or 0),
            memory_hints=list(meta.get("memory_hints") or []),
            context_summarized=int(meta.get("context_summarized") or 0),
            instant_reply=instant_reply,
            search_sources=search_sources,
            local_places=local_places,
            skip_memory_jobs=quiz_answer,
        )


async def _finalize_stream_turn_db(
    redis: Redis,
    ctx: _StreamContext,
    assistant_text: str,
    usage: dict[str, int],
    result: dict[str, Any] | None,
) -> None:
    usage_input = usage.get("input")
    input_tokens = (
        usage_input
        if usage_input is not None
        else sum(estimate_tokens(m["content"]) for m in ctx.prompt_messages)
    )
    usage_output = usage.get("output")
    output_tokens = usage_output if usage_output is not None else estimate_tokens(assistant_text)
    total_tokens = input_tokens + output_tokens

    persisted_text = assistant_text

    async with SessionLocal() as session:
        assistant_message = await messages_repo.create(
            session,
            chat_id=ctx.chat_id,
            user_id=ctx.user_id,
            role="assistant",
            content=persisted_text,
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
            if ctx.context_summarized:
                result["context_summarized"] = str(ctx.context_summarized)

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


async def _enqueue_post_turn_jobs(
    redis: Redis,
    settings: Settings,
    ctx: _StreamContext,
    assistant_text: str,
) -> None:
    transcript = f"User: {ctx.user_message_content}\nAssistant: {assistant_text}"
    job_specs: list[tuple[str, dict[str, str]]] = []
    if not ctx.skip_memory_jobs:
        job_specs.append(
            (
                "memory",
                {
                    "user_id": str(ctx.user_id),
                    "chat_id": str(ctx.chat_id),
                    "transcript": transcript,
                },
            ),
        )
        job_specs.append(
            (
                "todos",
                {
                    "user_id": str(ctx.user_id),
                    "chat_id": str(ctx.chat_id),
                    "transcript": transcript,
                },
            ),
        )
    job_specs.append(
        (
            "projects",
            {"user_id": str(ctx.user_id), "chat_id": str(ctx.chat_id), "transcript": transcript},
        ),
    )
    if ctx.run_title:
        job_specs.append(
            (
                "topic",
                {
                    "chat_id": str(ctx.chat_id),
                    "user_message": ctx.user_message_content,
                    "assistant_message": assistant_text,
                },
            )
        )
    if settings.history_compression_enabled:
        job_specs.append(("compress", {"chat_id": str(ctx.chat_id)}))
    if random.random() < 0.1:  # noqa: S311
        job_specs.append(("suggestions", {"user_id": str(ctx.user_id)}))

    await asyncio.gather(*(jobs.enqueue(redis, name, payload) for name, payload in job_specs))


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
    was_cancelled = False

    if ctx.instant_reply:
        if not (should_cancel and should_cancel()):
            assistant_parts.append(ctx.instant_reply)
            yield ctx.instant_reply
        else:
            was_cancelled = True
    else:
        async for token in litellm_gateway.stream_chat_completion(
            settings=settings,
            model_alias=ctx.model,
            messages=ctx.prompt_messages,
            max_tokens=ctx.max_output_tokens,
            usage=usage,
        ):
            if should_cancel and should_cancel():
                was_cancelled = True
                break
            assistant_parts.append(token)
            yield token

    assistant_text = "".join(assistant_parts).strip()
    if not assistant_text:
        await quota_service.refund_usage(redis, str(ctx.user_id), ctx.reserved_tokens)
        return

    async with SessionLocal() as session:
        user = await users_repo.get_by_id(session, ctx.user_id)
        if user is not None:
            assistant_text = await calendar_service.materialize_calendar_proposals(
                session,
                redis,
                user,
                settings,
                assistant_text,
            )

    assistant_text = math_fence_service.validate_math_fences(assistant_text)

    if ctx.search_sources:
        sources_fence = web_search_service.format_sources_fence(ctx.search_sources)
        if sources_fence and not (should_cancel and should_cancel()):
            assistant_parts.append(sources_fence)
            yield sources_fence
            assistant_text = "".join(assistant_parts).strip()
        if result is not None:
            result["search_sources"] = json.dumps(
                web_search_service.sources_payload(ctx.search_sources)
            )

    if ctx.local_places and ctx.search_sources and "```places" not in assistant_text.lower():
        assistant_text = web_search_service.strip_duplicate_venue_list(assistant_text)
        places_fence = web_search_service.format_places_fence(ctx.search_sources)
        if places_fence and not (should_cancel and should_cancel()):
            assistant_parts[:] = [assistant_text] if assistant_text.strip() else []
            assistant_parts.append(places_fence)
            assistant_text = "".join(assistant_parts).strip()
            if result is not None:
                result["final_content"] = assistant_text

    if ctx.instant_reply and not usage:
        usage["output_tokens"] = estimate_tokens(assistant_text)
        usage["input_tokens"] = 0

    if result is not None and not ctx.skip_memory_jobs:
        transcript = f"User: {ctx.user_message_content}\nAssistant: {assistant_text}"
        if todos_service.transcript_implies_todo_sync(transcript):
            result["todos_sync"] = "1"

    # On a user-initiated stop, the client freezes its local buffer early but the
    # server may persist a few more in-flight tokens. Send the authoritative
    # persisted text so the client can reconcile (only on cancel, to keep normal
    # `done` payloads small).
    if result is not None and was_cancelled and assistant_text:
        result["final_content"] = assistant_text

    finalize_db_task = asyncio.create_task(
        _finalize_stream_turn_db(redis, ctx, assistant_text, usage, result),
    )
    finalize_db_task.add_done_callback(
        lambda t: logger.exception("Background DB finalization failed", exc_info=t.exception())
        if t.exception()
        else None
    )

    async def _run_jobs_after_db() -> None:
        try:
            await finalize_db_task
            await _enqueue_post_turn_jobs(redis, settings, ctx, assistant_text)
        except Exception:
            logger.exception("Background job enqueue failed")

    jobs_task = asyncio.create_task(_run_jobs_after_db())
    jobs_task.add_done_callback(
        lambda t: logger.exception("Background finalization failed", exc_info=t.exception())
        if t.exception()
        else None
    )
    if result is not None:
        result["_finalize_task"] = jobs_task
        result["_finalize_db_task"] = finalize_db_task

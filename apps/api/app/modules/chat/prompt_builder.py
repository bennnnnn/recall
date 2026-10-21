from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, NamedTuple
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import Chat, User
from app.modules import web_search as web_search_service
from app.modules.attachments import service as attachments_service
from app.modules.chat import history_rag as chat_history_rag_service
from app.modules.chat.prompt_context import _load_context_blocks
from app.modules.chat.prompt_format import render_rules
from app.modules.chat.prompt_memory import (
    is_work_turn,
    memory_saving_paused,
    memory_scope_for,
    memory_switch_on,
    recalls_shared_past,
)
from app.modules.chat.prompt_sections import NEARBY_CONTRACTS, PROMPT_SECTIONS, PromptTurn
from app.modules.chat.prompt_window import (
    PromptWindow,
    followup_subject,
    history_messages,
    load_prompt_window,
)
from app.modules.chat.stream_status import StreamStatusFn, status_phase_for_subject
from app.modules.chat.turn_plan import TurnPlan
from app.modules.math.schemas import MathImageExtract
from app.modules.math.tools.extract import is_graph_followup
from app.services import time_context as time_context_service
from app.services.prompt_inject import inject_before_last_user
from app.services.solving import VerifiedSolveBlock
from app.services.subject_solving import (
    SubjectName,
    build_subject_augmentation,
    detect_subject,
)

if TYPE_CHECKING:
    from app.modules.memory import MemoryScope

logger = logging.getLogger(__name__)


class WebAndSubject(NamedTuple):
    """What one turn's web search and subject solver found, before either is injected."""

    web_block: str | None
    subject_block: str | None
    search_sources: list[WebSearchHit]
    verified: VerifiedSolveBlock | None
    # The solver adapter's own flag: callers must not re-derive it from the
    # wording of the prompt block.
    solver_unverified: bool
    # Set only when ``solver_unverified`` is.
    unverified_subject: str | None
    # A reply both halves of a two-part question already rendered.
    direct_text: str | None


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
    subject_text: str | None = None,
) -> WebAndSubject:
    """Fetch web-search and subject blocks WITHOUT mutating prompt_messages.

    Web search (network) and the subject solver are independent — gather both.
    ``subject_text``: the solve part of a message that asks for more (its plan).
    """
    math_user_content = math_followup_problem or subject_text or user_content
    subject_user_content = subject_text or user_content
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
            subject_user_content,
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
    if needs_subject and on_status is not None and subject is not None:
        await on_status(status_phase_for_subject(subject))

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
    return WebAndSubject(
        web_block=web_block,
        subject_block=subject_result.prompt_block,
        search_sources=search_sources,
        verified=subject_result.verified,
        solver_unverified=subject_result.unverified,
        unverified_subject=subject_result.subject if subject_result.unverified else None,
        direct_text=subject_result.direct_text,
    )


async def inject_web_and_tools(
    prompt_messages: list[dict[str, str]],
    web_block: str | None,
    math_block: str | None,
) -> list[dict[str, str]]:
    """Inject web → math blocks in the historical order.

    Mutation order is what keeps prompt shape stable; fetch order is irrelevant.
    """
    updated = prompt_messages
    if web_block:
        updated = inject_before_last_user(updated, web_block)
    if math_block:
        updated = inject_before_last_user(updated, math_block)
    return updated


@dataclass
class PromptStats:
    """What the prompt drew on, for the turn's ``done``."""

    # Memory sections loaded into the prompt, and the first three of their names.
    recalled: int = 0
    memory_hints: list[str] = field(default_factory=list)
    # Older messages the chat summary stands in for.
    context_summarized: int = 0


@dataclass(frozen=True)
class _ContextPlan:
    """What a turn loads beyond the recent window."""

    # Memory and integration context; a slim turn gets the name-only profile.
    slim: bool
    load_memory: bool
    # "What did we decide last time": memory and past chats answer even a slim turn.
    recalls_shared_past: bool
    history_rag: bool
    # Which saved facts load: by query, with the profile, everything, or the work scope.
    memory_scope: MemoryScope = "query"


async def _context_plan(
    user: User,
    chat_id: UUID,
    settings: Settings,
    *,
    query_text: str | None,
    minimal_personal_context: bool,
    lightweight: bool,
    rich_context: bool,
    advice_memory: bool,
    probe_attachment_rag: bool,
) -> _ContextPlan:
    # If this chat has indexed attachment chunks, force rich context so a
    # casual follow-up ("what's on page 10?") still retrieves RAG chunks.
    # Without this, a lightweight query after uploading a PDF skips RAG
    # entirely and the user gets no document context on follow-ups.
    if not rich_context and settings.attachment_rag_enabled and probe_attachment_rag:
        try:
            rich_context = await attachments_service.chat_has_document_chunks(user.id, chat_id)
        except Exception:
            logger.debug("has_chunks_for_chat probe failed for chat_id=%s", chat_id, exc_info=True)
    # Personal continuity only when this turn is actually about the user.
    # A normal question ("what is the capital of France") used to embed memory
    # and chat history on every non-greeting, which sat on the first token
    # for seconds before the model started.
    personal_context = (rich_context or advice_memory) and not lightweight
    # "How should I structure auth in my app?" needs the stack the user builds with,
    # not their city or job: the work scope, without a query embed.
    work_memory = not personal_context and not lightweight and is_work_turn(query_text)
    recalls_past = recalls_shared_past(query_text)
    # Memory off means no personal recall at all: no saved facts, no earlier chats.
    memory_on = memory_switch_on(user)
    return _ContextPlan(
        slim=minimal_personal_context or lightweight or not rich_context,
        load_memory=memory_on and (personal_context or work_memory or recalls_past),
        recalls_shared_past=recalls_past,
        history_rag=bool(
            memory_on
            and (personal_context or recalls_past)
            and settings.chat_history_rag_enabled
            and query_text
            and query_text.strip()
        ),
        memory_scope="work" if work_memory else memory_scope_for(query_text),
    )


async def _history_rag_block(
    settings: Settings,
    user: User,
    query_text: str | None,
    *,
    vector: list[float] | None,
    window: PromptWindow,
    omit_message_ids: set[UUID] | None,
) -> str:
    # The context gather already attempted the history embed. None means no
    # chunks or a failed/timed-out embed; do not repeat that work serially.
    if vector is None:
        return ""
    return await chat_history_rag_service.retrieve_for_prompt(
        settings,
        user_id=user.id,
        query=query_text or "",
        exclude_message_ids=window.message_ids | (omit_message_ids or set()),
        query_vec=vector,
    )


async def build_prompt_messages(
    user: User,
    chat_id: UUID,
    settings: Settings,
    *,
    summary: str | None = None,
    chat: Chat | None = None,
    stats: PromptStats | None = None,
    query_text: str | None = None,
    minimal_personal_context: bool = False,
    lightweight: bool = False,
    rich_context: bool = True,
    advice_memory: bool = False,
    client_timezone: str | None = None,
    prompt_location: str | None = None,
    omit_message_ids: set[UUID] | None = None,
    probe_attachment_rag: bool = True,
    recent_messages: list[Any] | None = None,
    current_user_message_id: UUID | None = None,
    prior_count: int | None = None,
    turn_plan: TurnPlan | None = None,
) -> list[dict[str, str]]:
    """Assemble system + recent messages for a chat turn.

    Context loading uses short-lived sessions so embeds cannot pin a caller
    connection across the concurrent gather. The system prompt is
    ``PROMPT_SECTIONS``; the history is ``prompt_window``. ``turn_plan``: the message's
    separate requests, when it holds more than one (``turn_prep.intents``). ``stats``,
    when given, is filled with what the prompt drew on.
    """
    plan = await _context_plan(
        user,
        chat_id,
        settings,
        query_text=query_text,
        minimal_personal_context=minimal_personal_context,
        lightweight=lightweight,
        rich_context=rich_context,
        advice_memory=advice_memory,
        probe_attachment_rag=probe_attachment_rag,
    )
    blocks = await _load_context_blocks(
        user,
        chat_id,
        settings,
        chat=chat,
        query_text=query_text,
        recent_limit=settings.recent_message_window,
        slim_context=plan.slim,
        load_memory=plan.load_memory,
        memory_scope=plan.memory_scope,
        client_timezone=client_timezone,
        history_rag=plan.history_rag,
        recent_messages=recent_messages,
    )
    chat = blocks.chat
    window = await load_prompt_window(
        chat_id,
        chat,
        blocks.recent_all,
        settings,
        query_text=query_text,
        omit_message_ids=omit_message_ids,
        current_user_message_id=current_user_message_id,
        prior_count=prior_count if recent_messages is not None else None,
    )
    followup = followup_subject(query_text, window.exchange)
    chat_history_rag_block = await _history_rag_block(
        settings,
        user,
        query_text,
        vector=blocks.history_rag_query_vec if plan.history_rag else None,
        window=window,
        omit_message_ids=omit_message_ids,
    )
    if stats is not None:
        stats.recalled = blocks.recalled
        stats.memory_hints = blocks.memory_hints
        if chat and chat.summary and (chat.summary_message_count or 0) > 0:
            stats.context_summarized = chat.summary_message_count
    turn = PromptTurn(
        user=user,
        settings=settings,
        query_text=query_text,
        local_tz=time_context_service.effective_timezone(user.timezone, client_timezone),
        lightweight=lightweight,
        slim=plan.slim,
        recall_memory=plan.load_memory or plan.recalls_shared_past,
        advice_memory=advice_memory,
        minimal_personal_context=minimal_personal_context,
        prompt_location=prompt_location,
        summary=summary,
        memory_block=blocks.memory_block,
        attachment_rag_block=blocks.attachment_rag_block,
        todos_section=blocks.todos_section,
        chat_history_rag_block=chat_history_rag_block,
        exchange=window.exchange,
        followup=followup,
        plan=turn_plan,
        memory_status=blocks.memory_status,
        memory_paused=bool(
            memory_switch_on(user) and await memory_saving_paused(settings, query_text)
        ),
        recalls_shared_past=plan.recalls_shared_past,
    )
    messages = [
        {"role": "system", "content": "\n\n".join(render_rules(PROMPT_SECTIONS, turn))},
        *history_messages(window, math_followup=followup == "math"),
    ]
    nearby = render_rules(NEARBY_CONTRACTS, turn)
    if nearby:
        messages = inject_before_last_user(messages, "\n\n".join(nearby))
    return messages

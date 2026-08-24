from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.db import SessionLocal
from app.exceptions import ChatNotFoundError
from app.gateways.web_search_gateway import WebSearchHit
from app.models.math_schemas import MathImageExtract
from app.models.orm import Chat, User
from app.repositories import chats as chats_repo
from app.repositories import users as users_repo
from app.services import calendar as calendar_service
from app.services import chemistry_context as chemistry_context_service
from app.services import email as email_service
from app.services import plan as plan_service
from app.services import profile as profile_service
from app.services import settings_proposal as settings_proposal_service
from app.services import time_context as time_context_service
from app.services import web_search as web_search_service
from app.services.chat.prompt_builder import (
    build_prompt_messages,
    fetch_web_and_tools,
    inject_web_and_tools,
)
from app.services.chat.prompt_constants import is_lightweight_chat_turn
from app.services.chat.stream_status import StreamStatusFn
from app.services.chat.turn_prep.integrations import (
    _load_has_calendar_write,
    _load_prior_user_messages,
    fetch_integration_blocks,
    inject_integration_blocks,
)
from app.services.chat.turn_prep.mode import (
    _classify_turn_mode,
    _resolve_instant_reply,
    _should_augment_web_and_tools,
    _should_fetch_integrations,
    _TurnMode,
)
from app.services.chat.turn_timing import TurnTimingTracker
from app.services.math_tools import VerifiedMathBlock, needs_symbolic_math
from app.services.settings_intent import extract_settings_changes
from app.services.vocab_quiz import QuizAnswerGrade

logger = logging.getLogger(__name__)


@dataclass
class RegenerateBackup:
    content: str
    model: str | None
    # When set, the prior assistant row stays in the DB until finalize
    # succeeds (omit from the prompt instead of delete-before-stream).
    message_id: UUID | None = None


@dataclass
class ClientGeoContext:
    user_location: str | None
    client_lat: float | None
    client_lng: float | None
    has_geo_fix: bool
    geo_query: bool
    ambiguous_nearby: bool
    local_places: bool


@dataclass
class StreamContext:
    user_id: UUID
    chat_id: UUID
    model: str
    prompt_messages: list[dict[str, Any]]
    run_title: bool
    user_message_content: str
    reserved_tokens: int
    max_output_tokens: int
    user: User | None = None
    # Pre-assigned id for the assistant row so `done` can be sent to the client
    # before the background DB insert commits.
    assistant_message_id: UUID | None = None
    recalled_count: int = 0
    memory_hints: list[str] = field(default_factory=list)
    context_summarized: int = 0
    instant_reply: str | None = None
    search_sources: list[WebSearchHit] = field(default_factory=list)
    local_places: bool = False
    skip_memory_jobs: bool = False
    prior_count: int = 0
    chat_project_id: UUID | None = None
    regenerate_backup: RegenerateBackup | None = None
    fallback_models: list[str] = field(default_factory=list)
    verified_math: VerifiedMathBlock | None = None
    timing: TurnTimingTracker | None = None
    lightweight_turn: bool = False
    # False = casual chat (skip memory/todos/projects). Status theater
    # (preparing/remembering/thinking/composing) is never shown; activity
    # chips remain for search, files, calendar, inbox, math, image gen.
    rich_context_turn: bool = True
    # Attachment ids to index after the turn finalizes (post-turn jobs path).
    indexable_attachment_ids: list[str] = field(default_factory=list)
    # Set when the tool loop's generate_image persisted the assistant row —
    # stream_and_finalize skips the LLM + second insert.
    terminal_image_message_id: str | None = None
    terminal_image_content: str | None = None
    terminal_image_model: str | None = None


@dataclass
class TurnPromptBundle:
    prompt_messages: list[dict[str, str]]
    meta: dict[str, Any]
    instant_reply: str | None
    search_sources: list[WebSearchHit]
    local_places: bool
    max_out: int
    fallback_models: list[str]
    minimal_quiz: bool
    minimal_vocab_answer: bool
    active_vocab_turn: bool
    lightweight: bool
    rich_context: bool
    quiz_grade: QuizAnswerGrade | None
    geo: ClientGeoContext
    local_tz: str
    verified_math: VerifiedMathBlock | None = None


def stream_context_from_bundle(
    bundle: TurnPromptBundle,
    *,
    user_id: UUID,
    chat_id: UUID,
    model: str,
    user_message_content: str,
    reserved_tokens: int,
    user: User,
    prior_count: int,
    chat_project_id: UUID | None,
    timing: TurnTimingTracker | None = None,
    run_title: bool | None = None,
    skip_memory_jobs: bool | None = None,
    regenerate_backup: RegenerateBackup | None = None,
    indexable_attachment_ids: list[str] | None = None,
    is_letter_answer: bool = False,
) -> StreamContext:
    """Map a TurnPromptBundle into StreamContext; overrides preserve call-site semantics."""
    if run_title is None:
        run_title = prior_count == 0
    if skip_memory_jobs is None:
        # Graded MCQ answers are already persisted — skip background sync.
        # Open-ended vocab answers still need project sync to record mastery.
        # If a letter answer failed to grade (missing fence / no project), keep
        # jobs so project sync can still record progress.
        skip_memory_jobs = bundle.minimal_quiz and not (
            is_letter_answer and bundle.quiz_grade is None
        )
    return StreamContext(
        user_id=user_id,
        chat_id=chat_id,
        model=model,
        prompt_messages=bundle.prompt_messages,
        run_title=run_title,
        user_message_content=user_message_content,
        reserved_tokens=reserved_tokens,
        max_output_tokens=bundle.max_out,
        user=user,
        recalled_count=int(bundle.meta.get("recalled") or 0),
        memory_hints=list(bundle.meta.get("memory_hints") or []),
        context_summarized=int(bundle.meta.get("context_summarized") or 0),
        instant_reply=bundle.instant_reply,
        search_sources=bundle.search_sources,
        local_places=bundle.local_places,
        skip_memory_jobs=skip_memory_jobs,
        prior_count=prior_count,
        chat_project_id=chat_project_id,
        regenerate_backup=regenerate_backup,
        fallback_models=bundle.fallback_models,
        verified_math=bundle.verified_math,
        timing=timing,
        lightweight_turn=bundle.lightweight
        or bundle.active_vocab_turn
        or is_lightweight_chat_turn(
            user_message_content, active_vocab_turn=bundle.active_vocab_turn
        ),
        rich_context_turn=bundle.rich_context,
        indexable_attachment_ids=list(indexable_attachment_ids or []),
    )


def resolve_client_geo(
    user: User,
    content: str,
    *,
    client_location: str | None,
    client_latitude: float | None,
    client_longitude: float | None,
) -> ClientGeoContext:
    # Settings Location toggle is the opt-in. Ignore one-shot client geo when off
    # so a stale/malicious client cannot bypass the user's choice.
    if not getattr(user, "location_enabled", False):
        client_location = None
        client_latitude = None
        client_longitude = None
    normalized_client_location = profile_service.normalize_client_location(client_location)
    client_coordinates = profile_service.normalize_client_coordinates(
        client_latitude, client_longitude
    )
    user_location = profile_service.effective_location_label(user, normalized_client_location)
    geo_query = web_search_service.is_geo_query(content)
    location_question = time_context_service.is_location_question(content)
    # "Where am I?" and nearby asks must use the fresh device fix, not a stale
    # profile city (or prior-chat place names).
    if geo_query or location_question:
        user_location = normalized_client_location
    client_lat = client_coordinates[0] if client_coordinates else None
    client_lng = client_coordinates[1] if client_coordinates else None
    has_geo_fix = bool(user_location) or client_coordinates is not None
    local_places = web_search_service.is_places_list_query(content)
    ambiguous_nearby = web_search_service.is_ambiguous_local_places_query(content)
    if ambiguous_nearby:
        local_places = False
    return ClientGeoContext(
        user_location=user_location,
        client_lat=client_lat,
        client_lng=client_lng,
        has_geo_fix=has_geo_fix,
        geo_query=geo_query or location_question,
        ambiguous_nearby=ambiguous_nearby,
        local_places=local_places,
    )


async def build_stream_prompt_context(
    user_id: UUID,
    chat_id: UUID,
    content: str,
    model: str,
    settings: Settings,
    redis: Redis,
    *,
    client_timezone: str | None,
    client_location: str | None,
    client_latitude: float | None,
    client_longitude: float | None,
    has_image_attachment: bool = False,
    image_math_extract: MathImageExtract | None = None,
    on_status: StreamStatusFn | None = None,
    quiz_mode: str | None = None,
    user: User | None = None,
    chat: Chat | None = None,
    timing: TurnTimingTracker | None = None,
    quiz_grade: QuizAnswerGrade | None = None,
    omit_message_ids: set[UUID] | None = None,
    force_rich_context: bool = False,
    turn_mode: _TurnMode | None = None,
) -> TurnPromptBundle:
    """Shared prompt assembly for new turns and regenerate."""
    if timing is not None:
        timing.mark_phase("prepare_start")
    meta: dict[str, Any] = {}
    prompt_messages: list[dict[str, str]]
    instant_reply: str | None = None
    prior_user_messages: list[str] = []
    has_calendar_write = False
    geo: ClientGeoContext
    local_tz: str
    max_out: int
    fallback_models: list[str]
    mode: _TurnMode

    # Phase 1: ownership + turn mode (short-lived session).
    async with SessionLocal() as session:
        if user is None:
            user = await users_repo.get_by_id(session, user_id)
            if user is None:
                raise ChatNotFoundError("User not found.")
        if chat is None:
            chat = await chats_repo.get_by_id(session, chat_id, user_id)
            if chat is None:
                raise ChatNotFoundError("Chat not found.")

        mode = turn_mode or await _classify_turn_mode(session, chat, content)
        if force_rich_context and not mode.rich_context:
            mode = replace(mode, rich_context=True)

        user_locale = user.locale
        chat_summary = chat.summary
        geo = resolve_client_geo(
            user,
            content,
            client_location=client_location,
            client_latitude=client_latitude,
            client_longitude=client_longitude,
        )
        local_tz = time_context_service.effective_timezone(user.timezone, client_timezone)

    # No outer session during prompt gather (RAG/memory embeds use short-lived
    # sessions inside build_prompt_messages). Do not emit preparing/remembering
    # theater — casual chat should look like TTS: tap, then tokens. Real work
    # (search, files, calendar, inbox, math) still emits its own activity chip.

    async def _resolve_instant_reply_task() -> str | None:
        async with SessionLocal() as session:
            reply = await _resolve_instant_reply(
                session,
                content,
                local_tz=local_tz,
                user_locale=user_locale,
                geo=geo,
                user_id=user.id,
            )
            if reply is None and not mode.minimal_vocab_answer and not mode.minimal_quiz:
                settings_changes = extract_settings_changes(content)
                if settings_changes:
                    reply = await settings_proposal_service.materialize_settings_reply(
                        redis, user, settings, settings_changes
                    )
            await session.commit()
        return reply

    # Phase A: build the prompt (memory/RAG embed) while resolving the
    # instant-reply short-circuit (time/location/calendar/email checks).
    # The two share no data -- overlap them so memory embed does not wait
    # behind a fast DB classification, and the classifier does not wait
    # behind a multi-second embedding round-trip.
    prompt_messages, instant_reply = await asyncio.gather(
        build_prompt_messages(
            user,
            chat.id,
            settings,
            summary=chat_summary,
            chat=chat,
            out=meta,
            query_text=content,
            minimal_personal_context=mode.minimal_personal,
            minimal_quiz_context=mode.minimal_quiz,
            minimal_vocab_answer_context=mode.minimal_vocab_answer,
            lightweight=mode.lightweight,
            rich_context=mode.rich_context,
            quiz_grade=quiz_grade,
            client_timezone=client_timezone,
            prompt_location=geo.user_location if geo.geo_query and geo.has_geo_fix else None,
            on_status=None,
            omit_message_ids=omit_message_ids,
        ),
        _resolve_instant_reply_task(),
    )
    if timing is not None:
        timing.mark_phase("prompt_assembled")

    # Geo "location not set" fallback (independent of the LLM).
    if instant_reply is None and geo.geo_query and not geo.has_geo_fix:
        instant_reply = web_search_service.format_location_not_set_answer()

    is_external_calendar = calendar_service.is_external_calendar_question(content)
    is_external_email = email_service.is_external_email_question(content)
    needs_math = (
        needs_symbolic_math(content, has_image_attachment=has_image_attachment)
        or image_math_extract is not None
    )
    needs_search = web_search_service.needs_web_search(content)
    needs_chem = chemistry_context_service.is_chemistry_question(content)
    augment = _should_augment_web_and_tools(
        instant_reply=instant_reply,
        lightweight=mode.lightweight,
        minimal_personal=mode.minimal_personal,
        minimal_quiz=mode.minimal_quiz,
        active_vocab_turn=mode.active_vocab_turn,
        day_planning=mode.day_planning,
        ambiguous_nearby=geo.ambiguous_nearby,
        is_external_calendar_question=is_external_calendar,
        is_external_email_question=is_external_email,
        rich_context=mode.rich_context,
        needs_math=needs_math,
        needs_search=needs_search,
        needs_chem=needs_chem,
    )
    load_calendar = calendar_service.should_inject_calendar_block(content)
    load_gmail = email_service.should_inject_gmail_block(content)
    integration_gate = _should_fetch_integrations(
        instant_reply=instant_reply,
        lightweight=mode.lightweight,
        minimal_personal=mode.minimal_personal,
        minimal_quiz=mode.minimal_quiz,
        active_vocab_turn=mode.active_vocab_turn,
        rich_context=mode.rich_context,
        load_calendar=load_calendar,
        load_gmail=load_gmail,
    )

    # One high ceiling for every turn — brevity is driven by the STYLE_HINTS
    # prompt guidance, not a hard token cap. Capping by style truncated large
    # deliverables (HTML pages, graph JSON) mid-fence.
    max_out = settings.max_output_tokens
    # M6: filter out unhealthy models from the fallback pool so we don't
    # repeatedly hit a degraded provider. Best-effort — if health read
    # fails (Redis down), treat all as healthy (fail open).
    unhealthy: set[str] = set()
    try:
        from app.services import model_health as model_health_service

        pool = plan_service.model_pool(user, settings)
        snaps = await model_health_service.enrich_models_health(redis, settings, pool)
        unhealthy = {mid for mid, snap in snaps.items() if not snap.healthy}
    except Exception:
        logger.debug("model health read failed during fallback selection", exc_info=True)
    fallback_models = plan_service.chat_fallback_models(user, settings, model, unhealthy=unhealthy)

    local_places = geo.local_places
    search_sources: list[WebSearchHit] = []
    verified_math: VerifiedMathBlock | None = None

    # B2: prior user messages + calendar-write flag. Web search needs the
    # prior messages; the integration fetch needs the calendar-write flag for
    # the create-event hint. Both are cheap DB reads -- resolve them before the
    # concurrent external fetches so all inputs are ready, then overlap the
    # slow I/O (calendar/gmail API | Tavily/SymPy) below.
    # (prior_user_messages / has_calendar_write are initialized above.)
    if augment or integration_gate:
        prior_user_messages, has_calendar_write = await asyncio.gather(
            _load_prior_user_messages(chat.id),
            _load_has_calendar_write(user.id),
        )

    # Phase B: gather the independent external fetches concurrently.
    # Integration fetch (calendar/gmail/nudge) and web+tools fetch
    # (Tavily/SymPy) share no data — run them together so the turn waits
    # on max(calendar, web+math) instead of calendar + web+math serially.
    integration_coro: Awaitable[list[str]] | None = None
    if integration_gate:
        integration_coro = fetch_integration_blocks(
            content,
            user,
            redis,
            settings,
            instant_reply=instant_reply,
            lightweight=mode.lightweight,
            minimal_personal=mode.minimal_personal,
            minimal_quiz=mode.minimal_quiz,
            day_reflection=mode.day_reflection,
            has_calendar_write=has_calendar_write,
            gmail_context=None,
            on_status=on_status,
            client_timezone=client_timezone,
            include_email_nudge=mode.rich_context,
        )
    web_coro: (
        Awaitable[tuple[str | None, str | None, list[WebSearchHit], VerifiedMathBlock | None]]
        | None
    ) = None
    chem_coro: Awaitable[str | None] | None = None
    if augment:
        web_coro = fetch_web_and_tools(
            content,
            settings,
            prompt_messages=prompt_messages,
            user_timezone=local_tz,
            user_location=geo.user_location,
            latitude=geo.client_lat,
            longitude=geo.client_lng,
            prior_user_messages=prior_user_messages,
            has_image_attachment=has_image_attachment,
            image_math_extract=image_math_extract,
            on_status=on_status,
            user=user,
            redis=redis,
        )
        if settings.chemistry_enabled and needs_chem:
            chem_coro = chemistry_context_service.build_chemistry_context(content, settings)

    integration_blocks: list[str] = []
    web_block: str | None = None
    math_block: str | None = None
    chem_block: str | None = None
    fetch_jobs: list[Awaitable[Any]] = []
    fetch_keys: list[str] = []
    if integration_coro is not None:
        fetch_jobs.append(integration_coro)
        fetch_keys.append("integration")
    if web_coro is not None:
        fetch_jobs.append(web_coro)
        fetch_keys.append("web")
    if chem_coro is not None:
        fetch_jobs.append(chem_coro)
        fetch_keys.append("chem")
    if fetch_jobs:
        fetched = await asyncio.gather(*fetch_jobs)
        by_key = dict(zip(fetch_keys, fetched, strict=True))
        if "integration" in by_key:
            integration_blocks = by_key["integration"]
        if "web" in by_key:
            web_block, math_block, search_sources, verified_math = by_key["web"]
        if "chem" in by_key:
            chem_block = by_key["chem"]

    # Phase C: inject in the stable order (integration -> web -> math) so the
    # final prompt is byte-identical to the prior serial pipeline.
    prompt_messages = inject_integration_blocks(prompt_messages, integration_blocks)
    if augment:
        prompt_messages = await inject_web_and_tools(
            prompt_messages,
            web_block,
            math_block,
            settings,
            user_content=content,
            user_timezone=local_tz,
            user_location=geo.user_location,
            prior_user_messages=prior_user_messages,
            on_status=None,
            has_calendar_write=has_calendar_write,
        )

    # Chemistry context (PubChem compound lookup) — injected after math
    # so the model has verified SMILES + properties when it emits a
    # ```smiles fence.
    if chem_block:
        prompt_messages.append({"role": "system", "content": chem_block})

    if timing is not None:
        timing.mark_phase("augment_done")
        timing.mark_prompt_ready()

    return TurnPromptBundle(
        prompt_messages=prompt_messages,
        meta=meta,
        instant_reply=instant_reply,
        search_sources=search_sources,
        local_places=local_places,
        max_out=max_out,
        fallback_models=fallback_models,
        minimal_quiz=mode.minimal_quiz,
        minimal_vocab_answer=mode.minimal_vocab_answer,
        active_vocab_turn=mode.active_vocab_turn,
        lightweight=mode.lightweight,
        rich_context=mode.rich_context,
        quiz_grade=quiz_grade,
        geo=geo,
        local_tz=local_tz,
        verified_math=verified_math,
    )

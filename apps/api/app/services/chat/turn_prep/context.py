from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
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
from app.services import email as email_service
from app.services import plan as plan_service
from app.services import profile as profile_service
from app.services import time_context as time_context_service
from app.services import web_search as web_search_service
from app.services.chat.prompt_builder import _augment_web_and_tools, build_prompt_messages
from app.services.chat.prompt_constants import (
    is_lightweight_chat_turn,
    max_output_tokens_for_style,
)
from app.services.chat.stream_status import StreamStatusFn
from app.services.chat.turn_prep.integrations import (
    _inject_integration_blocks,
    _load_gmail_context_if_needed,
    _load_has_calendar_write,
    _load_prior_user_messages,
)
from app.services.chat.turn_prep.mode import (
    _classify_turn_mode,
    _resolve_instant_reply,
    _should_augment_web_and_tools,
    _TurnMode,
)
from app.services.chat.turn_timing import TurnTimingTracker
from app.services.math_tools import VerifiedMathBlock
from app.services.vocab_quiz import QuizAnswerGrade


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
    # Attachment ids to index after the turn finalizes (post-turn jobs path).
    indexable_attachment_ids: list[str] = field(default_factory=list)


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
        lightweight_turn=bundle.active_vocab_turn
        or is_lightweight_chat_turn(
            user_message_content, active_vocab_turn=bundle.active_vocab_turn
        ),
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
    todo_sync_feedback: str | None = None,
    quiz_mode: str | None = None,
    user: User | None = None,
    chat: Chat | None = None,
    timing: TurnTimingTracker | None = None,
    quiz_grade: QuizAnswerGrade | None = None,
    omit_message_ids: set[UUID] | None = None,
) -> TurnPromptBundle:
    """Shared prompt assembly for new turns and regenerate."""
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

        mode = await _classify_turn_mode(session, chat, content)

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
    # sessions inside build_prompt_messages). Skip status theater on greetings —
    # "Recalling what I know…" on a plain "hi" feels slow and is wasted work.
    if on_status is not None and not mode.lightweight:
        await on_status("preparing")

    prompt_messages = await build_prompt_messages(
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
        quiz_grade=quiz_grade,
        client_timezone=client_timezone,
        prompt_location=geo.user_location if geo.geo_query and geo.has_geo_fix else None,
        todo_sync_feedback=todo_sync_feedback,
        on_status=on_status,
        omit_message_ids=omit_message_ids,
    )

    async with SessionLocal() as session:
        instant_reply = await _resolve_instant_reply(
            session,
            content,
            local_tz=local_tz,
            user_locale=user_locale,
            geo=geo,
            user_id=user.id,
        )

        if _should_augment_web_and_tools(
            instant_reply=instant_reply,
            lightweight=mode.lightweight,
            minimal_personal=mode.minimal_personal,
            minimal_quiz=mode.minimal_quiz,
            day_planning=mode.day_planning,
            ambiguous_nearby=geo.ambiguous_nearby,
            is_external_calendar_question=calendar_service.is_external_calendar_question(content),
            is_external_email_question=email_service.is_external_email_question(content),
        ):
            prior_user_messages, has_calendar_write = await asyncio.gather(
                _load_prior_user_messages(chat.id),
                _load_has_calendar_write(user.id),
            )

        max_out = (
            max_output_tokens_for_style("short", settings)
            if mode.minimal_quiz or mode.lightweight
            else max_output_tokens_for_style(user.response_style, settings)
        )
        fallback_models = plan_service.chat_fallback_models(user, settings, model)

        await session.commit()

    # DB connection released before external integration / web search I/O.
    if instant_reply is None and geo.geo_query and not geo.has_geo_fix:
        instant_reply = web_search_service.format_location_not_set_answer()

    gmail_context = await _load_gmail_context_if_needed(
        content,
        user,
        redis,
        settings,
        instant_reply=instant_reply,
        on_status=on_status,
    )

    local_places = geo.local_places
    prompt_messages = await _inject_integration_blocks(
        prompt_messages,
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
        gmail_context=gmail_context,
        on_status=on_status,
    )

    search_sources: list[WebSearchHit] = []
    verified_math: VerifiedMathBlock | None = None
    if _should_augment_web_and_tools(
        instant_reply=instant_reply,
        lightweight=mode.lightweight,
        minimal_personal=mode.minimal_personal,
        minimal_quiz=mode.minimal_quiz,
        day_planning=mode.day_planning,
        ambiguous_nearby=geo.ambiguous_nearby,
        is_external_calendar_question=calendar_service.is_external_calendar_question(content),
        is_external_email_question=email_service.is_external_email_question(content),
    ):
        prompt_messages, search_sources, verified_math = await _augment_web_and_tools(
            prompt_messages,
            content,
            settings,
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
            has_calendar_write=has_calendar_write,
        )

    if timing is not None:
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
        quiz_grade=quiz_grade,
        geo=geo,
        local_tz=local_tz,
        verified_math=verified_math,
    )

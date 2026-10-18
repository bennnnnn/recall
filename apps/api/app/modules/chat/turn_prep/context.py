from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.db import SessionLocal
from app.exceptions import ChatNotFoundError
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import User
from app.modules.billing import plan as plan_service
from app.modules.chat.prompt_builder import build_prompt_messages
from app.modules.chat.turn_prep.augment import Augmentation, gather_and_inject
from app.modules.chat.turn_prep.followups import resolve_subject_followup
from app.modules.chat.turn_prep.instant import (
    location_not_set_reply,
    recurring_pay_reply,
    resolve_instant_reply,
)
from app.modules.chat.turn_prep.mode import _classify_turn_mode
from app.modules.chat.turn_prep.request import (
    ClientGeoContext,
    TurnIdentity,
    TurnRequest,
    resolve_client_geo,
)
from app.modules.chat.turn_timing import TurnTimingTracker
from app.repositories import chats as chats_repo
from app.repositories import users as users_repo
from app.services import time_context as time_context_service
from app.services.solving import VerifiedSolveBlock

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from app.modules.images.answer_photo import AnswerPhoto


@dataclass
class RegenerateBackup:
    content: str
    model: str | None
    # When set, the prior assistant row stays in the DB until finalize
    # succeeds (omit from the prompt instead of delete-before-stream).
    message_id: UUID | None = None


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
    # Effective timezone for this request (profile preference overridden by
    # the current client timezone). Finalization must use the same zone that
    # prompt construction used for relative dates and reminder clocks.
    user_timezone: str | None = None
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
    regenerate_backup: RegenerateBackup | None = None
    fallback_models: list[str] = field(default_factory=list)
    # One verified solve for the subject that owns this turn.
    verified_subject: VerifiedSolveBlock | None = None
    # A subject solver ran and declined. The reply gets one note, not a card.
    solver_unverified: bool = False
    unverified_subject: str | None = None
    timing: TurnTimingTracker | None = None
    lightweight_turn: bool = False
    # False = casual chat (skip memory/todos). Status theater
    # (preparing/remembering/thinking/composing) is never shown; activity
    # chips remain for search, files, math, image gen.
    rich_context_turn: bool = True
    # Attachment ids to index after the turn finalizes (post-turn jobs path).
    indexable_attachment_ids: list[str] = field(default_factory=list)
    # Background insert of the user row. The LLM stream must not wait on it;
    # finalize and stream teardown await it so the assistant insert cannot
    # commit first and so a failed prompt still keeps what the user sent.
    user_message_persist: asyncio.Task[list[str]] | None = None
    # None means no verdict was prefetched; False is a completed negative.
    web_search_classified: bool | None = None
    # Set when the tool loop's generate_image persisted the assistant row —
    # stream_and_finalize skips the LLM + second insert.
    terminal_image_message_id: str | None = None
    terminal_image_content: str | None = None
    terminal_image_model: str | None = None
    # False sends the model's thinking-off payload. Hard jobs set this True.
    thinking: bool = False
    # A real photo above an answer about something worth seeing: the search
    # starts when the reply's ```photo fence closes; finalize links the ids.
    answer_photo: AnswerPhoto | None = None
    answer_photo_ids: list[UUID] = field(default_factory=list)


@dataclass
class TurnPromptBundle:
    prompt_messages: list[dict[str, str]]
    meta: dict[str, Any]
    instant_reply: str | None
    search_sources: list[WebSearchHit]
    local_places: bool
    max_out: int
    fallback_models: list[str]
    lightweight: bool
    rich_context: bool
    geo: ClientGeoContext
    local_tz: str
    verified_subject: VerifiedSolveBlock | None = None
    solver_unverified: bool = False
    unverified_subject: str | None = None
    web_search_classified: bool | None = None


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
    timing: TurnTimingTracker | None = None,
    run_title: bool | None = None,
    skip_memory_jobs: bool | None = None,
    regenerate_backup: RegenerateBackup | None = None,
    indexable_attachment_ids: list[str] | None = None,
    user_message_persist: asyncio.Task[list[str]] | None = None,
    thinking: bool = False,
) -> StreamContext:
    """Map a TurnPromptBundle into StreamContext; overrides preserve call-site semantics."""
    if run_title is None:
        run_title = prior_count == 0
    if skip_memory_jobs is None:
        skip_memory_jobs = False
    return StreamContext(
        user_id=user_id,
        chat_id=chat_id,
        model=model,
        prompt_messages=bundle.prompt_messages,
        run_title=run_title,
        user_message_content=user_message_content,
        reserved_tokens=reserved_tokens,
        max_output_tokens=bundle.max_out,
        user_timezone=getattr(bundle, "local_tz", None),
        user=user,
        recalled_count=int(bundle.meta.get("recalled") or 0),
        memory_hints=list(bundle.meta.get("memory_hints") or []),
        context_summarized=int(bundle.meta.get("context_summarized") or 0),
        instant_reply=bundle.instant_reply,
        search_sources=bundle.search_sources,
        local_places=bundle.local_places,
        skip_memory_jobs=skip_memory_jobs,
        prior_count=prior_count,
        regenerate_backup=regenerate_backup,
        fallback_models=bundle.fallback_models,
        verified_subject=bundle.verified_subject,
        solver_unverified=getattr(bundle, "solver_unverified", False) is True,
        unverified_subject=getattr(bundle, "unverified_subject", None),
        timing=timing,
        # Trust turn-mode: re-running is_lightweight_chat_turn without the
        # prior assistant would mark "yes"/"go" as greetings again.
        lightweight_turn=bundle.lightweight,
        rich_context_turn=bundle.rich_context,
        web_search_classified=getattr(bundle, "web_search_classified", None),
        indexable_attachment_ids=list(indexable_attachment_ids or []),
        user_message_persist=user_message_persist,
        thinking=thinking,
    )


async def await_user_message_persist(ctx: StreamContext) -> None:
    """Finish the background user-row insert. Safe to call more than once."""
    task = ctx.user_message_persist
    if task is None:
        return
    ctx.user_message_persist = None
    ctx.indexable_attachment_ids = await task


async def _load_turn_identity(request: TurnRequest) -> TurnIdentity:
    """The user, chat and turn mode, with the turn's geo and clock resolved in memory.

    Prepare and regenerate pass all three, so a turn skips a Neon checkout; one
    left out is read in a single short session.
    """
    user, chat, mode = request.user, request.chat, request.turn_mode
    if user is None or chat is None or mode is None:
        async with SessionLocal() as session:
            if user is None:
                user = await users_repo.get_by_id(session, request.user_id)
                if user is None:
                    raise ChatNotFoundError("User not found.")
            if chat is None:
                chat = await chats_repo.get_by_id(session, request.chat_id, request.user_id)
                if chat is None:
                    raise ChatNotFoundError("Chat not found.")
            if mode is None:
                mode = await _classify_turn_mode(session, chat, request.content)
    if request.force_rich_context and not mode.rich_context:
        mode = replace(mode, rich_context=True)
    geo = resolve_client_geo(
        user,
        request.content,
        client_location=request.client_location,
        client_latitude=request.client_latitude,
        client_longitude=request.client_longitude,
    )
    local_tz = time_context_service.effective_timezone(user.timezone, request.client_timezone)
    return TurnIdentity(user=user, chat=chat, mode=mode, geo=geo, local_tz=local_tz)


async def _fallback_models(user: User, settings: Settings, redis: Redis, model: str) -> list[str]:
    unhealthy: set[str] = set()
    try:
        from app.services import model_health as model_health_service

        pool = plan_service.model_pool(user, settings)
        snaps = await model_health_service.enrich_models_health(redis, settings, pool)
        unhealthy = {mid for mid, snap in snaps.items() if not snap.healthy}
    except Exception:
        logger.debug("model health read failed during fallback selection", exc_info=True)
    return plan_service.chat_fallback_models(user, settings, model, unhealthy=unhealthy)


def _bundle(
    identity: TurnIdentity,
    settings: Settings,
    augmented: Augmentation,
    *,
    meta: dict[str, Any],
    instant_reply: str | None,
    fallback_models: list[str],
) -> TurnPromptBundle:
    return TurnPromptBundle(
        prompt_messages=augmented.prompt_messages,
        meta=meta,
        instant_reply=instant_reply,
        search_sources=augmented.search_sources,
        local_places=identity.geo.local_places,
        # One high ceiling for every turn — brevity is driven by the STYLE_HINTS
        # prompt guidance, not a hard token cap. Capping by style truncated large
        # deliverables (HTML pages, graph JSON) mid-fence.
        max_out=settings.max_output_tokens,
        fallback_models=fallback_models,
        lightweight=identity.mode.lightweight,
        rich_context=identity.mode.rich_context,
        geo=identity.geo,
        local_tz=identity.local_tz,
        verified_subject=augmented.verified_subject,
        solver_unverified=augmented.solver_unverified,
        unverified_subject=augmented.unverified_subject,
        web_search_classified=augmented.web_search_classified,
    )


async def build_stream_prompt_context(
    request: TurnRequest, settings: Settings, redis: Redis
) -> TurnPromptBundle:
    """Shared prompt assembly for new turns and regenerate."""
    timing = request.timing
    if timing is not None:
        timing.mark_phase("prepare_start")
    identity = await _load_turn_identity(request)
    pay_reply = recurring_pay_reply(request, identity.local_tz)
    if pay_reply is not None:
        if timing is not None:
            timing.mark_phase("prompt_assembled")
            timing.mark_phase("augment_done")
            timing.mark_prompt_ready()
        prompt = [{"role": "user", "content": request.content}]
        return _bundle(
            identity,
            settings,
            Augmentation(prompt),
            meta={},
            instant_reply=pay_reply,
            fallback_models=[],
        )

    # No outer session during prompt gather (RAG/memory embeds use short-lived
    # sessions inside build_prompt_messages). Do not emit preparing/remembering
    # theater — casual chat should look like TTS: tap, then tokens. Real work
    # (search, files, math) still emits its own activity chip.
    user, chat, mode, geo = identity.user, identity.chat, identity.mode, identity.geo
    meta: dict[str, Any] = {}
    # Phase A: prompt + instant-reply + fallback-health share no data.
    prompt_messages, instant_reply, fallback_models = await asyncio.gather(
        build_prompt_messages(
            user,
            chat.id,
            settings,
            summary=chat.summary,
            chat=chat,
            out=meta,
            query_text=request.content,
            minimal_personal_context=mode.minimal_personal,
            lightweight=mode.lightweight,
            rich_context=mode.rich_context,
            advice_memory=mode.advice_memory,
            client_timezone=request.client_timezone,
            prompt_location=geo.user_location if geo.geo_query and geo.has_geo_fix else None,
            on_status=None,
            omit_message_ids=request.omit_message_ids,
            probe_attachment_rag=request.probe_attachment_rag,
            recent_messages=request.recent_messages,
            current_user_message_id=request.current_user_message_id,
        ),
        resolve_instant_reply(request, identity, settings, redis),
        _fallback_models(user, settings, redis, request.model),
    )
    if timing is not None:
        timing.mark_phase("prompt_assembled")

    followup = resolve_subject_followup(request.content, prompt_messages)
    if instant_reply is None:
        instant_reply = location_not_set_reply(request.content, geo, followup)
    augmented = await gather_and_inject(
        request, identity, settings, redis, prompt_messages, followup, instant_reply=instant_reply
    )
    if timing is not None:
        timing.mark_phase("augment_done")
        timing.mark_prompt_ready()

    if instant_reply is None:
        instant_reply = augmented.direct_reply(request, user, followup)
    return _bundle(
        identity,
        settings,
        augmented,
        meta=meta,
        instant_reply=instant_reply,
        fallback_models=fallback_models,
    )

"""Phase B/C: fetch live web results and a verified subject solve, then inject them.

Phase B runs the web + subject fetch, overlapped with the web-search classifier
when the turn may need it. Phase C injects in the stable order (web, then subject)
so the final prompt is byte-identical to the old serial pipeline.
"""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any

from redis.asyncio import Redis

from app.core.aio import gather_or_cancel
from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit
from app.modules import web_search as web_search_service
from app.modules.chat.prompt_builder import (
    WebAndSubject,
    fetch_web_and_tools,
    inject_web_and_tools,
)
from app.modules.chat.tool_gate import should_classify_tool_web_search
from app.modules.chat.turn_plan import TurnPlan
from app.modules.chat.turn_prep.followups import SubjectFollowup
from app.modules.chat.turn_prep.intents import plan_turn
from app.modules.chat.turn_prep.mode import _should_augment_web_and_tools
from app.modules.chat.turn_prep.request import TurnIdentity, TurnRequest
from app.modules.math.tools.extract import is_graph_followup
from app.modules.web_search import detection as web_search_detection
from app.modules.web_search.subject import (
    collect_prior_user_messages as _prompt_prior_user_messages,
)
from app.modules.web_search.subject import last_assistant_content
from app.services.solving import VerifiedSolveBlock
from app.services.subject_solving import detect_subject, maybe_direct_subject_reply

# Earlier user lines a web search may take its subject from.
_PRIOR_USER_LINES = 8


@dataclass
class Augmentation:
    prompt_messages: list[dict[str, str]]
    search_sources: list[WebSearchHit] = field(default_factory=list)
    verified_subject: VerifiedSolveBlock | None = None
    solver_unverified: bool = False
    unverified_subject: str | None = None
    # A reply both halves of a two-part question already rendered.
    direct_text: str | None = None
    # None means no verdict was prefetched; False is a completed negative.
    web_search_classified: bool | None = None
    # The message asks for more than its solve: the model answers the rest.
    asks_more: bool = False

    def direct_reply(self, request: TurnRequest, followup: SubjectFollowup) -> str | None:
        """The reply the verified solve writes itself, when the turn needs no model."""
        if self.direct_text:
            return self.direct_text
        if self.verified_subject is None or self.asks_more:
            return None
        return maybe_direct_subject_reply(
            self.verified_subject,
            request.content,
            has_image_attachment=request.has_image_attachment,
            # Length follows the message, not a stored setting.
            response_style="balanced",
            verified_request_text=followup.math,
        )


async def gather_and_inject(
    request: TurnRequest,
    identity: TurnIdentity,
    settings: Settings,
    redis: Redis,
    prompt_messages: list[dict[str, str]],
    followup: SubjectFollowup,
    *,
    instant_reply: str | None,
) -> Augmentation:
    """Phase B/C for one turn. A turn the gate turns away keeps its prompt as built."""
    mode = identity.mode
    plan = plan_turn(request.content, chemistry_enabled=settings.chemistry_enabled)
    needs_math, needs_search, needs_chem = _turn_needs(
        request, settings, prompt_messages, followup, plan
    )
    if not _should_augment_web_and_tools(
        instant_reply=instant_reply,
        lightweight=mode.lightweight,
        minimal_personal=mode.minimal_personal,
        day_planning=mode.day_planning,
        ambiguous_nearby=identity.geo.ambiguous_nearby,
        rich_context=mode.rich_context,
        needs_math=needs_math,
        needs_search=needs_search,
        needs_chem=needs_chem,
    ):
        return Augmentation(prompt_messages)

    # Phase B: gather independent fetches.
    jobs: list[Awaitable[Any]] = [
        _fetch_web_with_priors(
            request, identity, settings, redis, prompt_messages, followup, _mixed_solve(plan)
        )
    ]
    # A multi-part message is classified part by part in the tool-loop path.
    classify = (
        None
        if plan.multi
        else _overlapped_classifier(
            request,
            identity,
            settings,
            prompt_messages,
            needs_subject=needs_math or needs_chem,
            instant_reply=instant_reply,
        )
    )
    if classify is not None:
        jobs.append(classify)
    fetched = await gather_or_cancel(jobs)
    (
        web_block,
        math_block,
        search_sources,
        verified_subject,
        solver_unverified,
        unverified_subject,
        direct_text,
    ) = fetched[0]
    # Phase C: inject in the stable order (web -> subject).
    return Augmentation(
        prompt_messages=await inject_web_and_tools(prompt_messages, web_block, math_block),
        search_sources=search_sources,
        verified_subject=verified_subject,
        solver_unverified=solver_unverified,
        unverified_subject=unverified_subject,
        direct_text=direct_text,
        web_search_classified=fetched[1] if len(fetched) > 1 else None,
        asks_more=plan.multi and any(part.kind != "solve" for part in plan.parts),
    )


def _mixed_solve(plan: TurnPlan) -> str | None:
    """The one maths, physics or chemistry request of a message that asks for more.

    "Solve 2x + 5 = 17 and also what's the weather in Paris" is solved from its own
    words: the whole line read as one problem lost the verification.
    """
    solves = plan.of_kind("solve")
    return solves[0].text if plan.multi and len(solves) == 1 else None


def _turn_needs(
    request: TurnRequest,
    settings: Settings,
    prompt_messages: list[dict[str, str]],
    followup: SubjectFollowup,
    plan: TurnPlan,
) -> tuple[bool, bool, bool]:
    """Whether the turn needs maths, a web search and chemistry, in that order."""
    content = request.content
    detected_subject = detect_subject(
        _mixed_solve(plan) or content,
        has_image_attachment=request.has_image_attachment,
        image_math_extract=request.image_math_extract,
        chemistry_enabled=settings.chemistry_enabled,
    )
    needs_math = settings.math_tools_enabled and (
        detected_subject in {"math", "physics"}
        or followup.math is not None
        or followup.physics is not None
        or is_graph_followup(content)
    )
    needs_search = web_search_service.needs_web_search(
        content,
        prior_user_messages=_prompt_prior_user_messages(prompt_messages, content) or None,
        prior_assistant=last_assistant_content(prompt_messages),
    ) or (plan.multi and any(web_search_service.needs_web_search(text) for text in plan.texts()))
    needs_chem = settings.chemistry_enabled and (
        detected_subject == "chemistry" or followup.chemistry is not None
    )
    return needs_math, needs_search, needs_chem


def _overlapped_classifier(
    request: TurnRequest,
    identity: TurnIdentity,
    settings: Settings,
    prompt_messages: list[dict[str, str]],
    *,
    needs_subject: bool,
    instant_reply: str | None,
) -> Awaitable[bool] | None:
    """The web-search classifier, when it may run beside the Phase B fetch.

    Only overlap existing Phase B work. Math may still produce a direct reply, so
    defer its eligibility until the final gate sees that result. This remains on
    the critical path when it outlasts the other fetches.
    """
    content = request.content
    if (
        needs_subject
        or not settings.web_search_classifier_enabled
        or not should_classify_tool_web_search(
            content,
            settings,
            lightweight=identity.mode.lightweight,
            has_instant_reply=instant_reply is not None,
            has_verified_math=False,
            has_search_sources=False,
            user=identity.user,
        )
    ):
        return None
    return web_search_detection.should_web_search(
        content,
        settings,
        prior_user_messages=_prompt_prior_user_messages(prompt_messages, content) or None,
        prior_assistant=last_assistant_content(prompt_messages),
    )


async def _fetch_web_with_priors(
    request: TurnRequest,
    identity: TurnIdentity,
    settings: Settings,
    redis: Redis,
    prompt_messages: list[dict[str, str]],
    followup: SubjectFollowup,
    subject_text: str | None = None,
) -> WebAndSubject:
    # Earlier user lines name the web search subject. They come from the prompt's own
    # history: a second read of the messages raced the current line's insert.
    priors = _prompt_prior_user_messages(prompt_messages, request.content)[-_PRIOR_USER_LINES:]
    geo = identity.geo
    return await fetch_web_and_tools(
        request.content,
        settings,
        prompt_messages=prompt_messages,
        user_timezone=identity.local_tz,
        user_location=geo.user_location,
        latitude=geo.client_lat,
        longitude=geo.client_lng,
        prior_user_messages=priors,
        has_image_attachment=request.has_image_attachment,
        image_math_extract=request.image_math_extract,
        math_followup_problem=followup.math,
        chemistry_followup_problem=followup.chemistry,
        physics_followup_problem=followup.physics,
        on_status=request.on_status,
        user=identity.user,
        redis=redis,
        subject_text=subject_text,
    )

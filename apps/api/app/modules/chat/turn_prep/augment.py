"""Phase B/C: fetch a verified subject solve, then inject it.

Live web results come from the tool loop, after this; the pre-stream search and
its LLM classifier never ran in production and are gone.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.readings import read_off_loop
from app.modules.chat.posed_read import posed_for_turn
from app.modules.chat.prompt_builder import SubjectFetch, fetch_subject, inject_subject_block
from app.modules.chat.referent_read import Referent, continuation_for_turn, referent_for_turn
from app.modules.chat.turn_prep.followups import (
    SubjectFollowup,
    resolve_posed_followup,
    resolve_subject_followup,
    role_content_dicts,
)
from app.modules.chat.turn_prep.instant import location_not_set_reply
from app.modules.chat.turn_prep.mode import _should_augment_web_and_tools
from app.modules.chat.turn_prep.model_read_shadow import start_model_read_shadow
from app.modules.chat.turn_prep.reading import ask_turn_readings, plan_of, subject_of
from app.modules.chat.turn_prep.request import TurnIdentity, TurnRequest
from app.modules.chat.whole_question import whole_question_fetch
from app.modules.chat.worked_render import WorkedLayout
from app.modules.chat.worked_turn import (
    checks_stated_results,
    with_result_check_contract,
    with_worked_contract,
    worked_layout,
)
from app.modules.turn_reading.plan import TurnPlan, solved_parts
from app.modules.web_search.subject import (
    collect_prior_user_messages as _prompt_prior_user_messages,
)
from app.services.solving import VerifiedSolveBlock
from app.services.subjects.dispatch import SubjectName, read_direct_reply, read_subject
from app.services.subjects.registry import subject_adapter

if TYPE_CHECKING:
    from app.services.subjects.registry import MoneyTurn

# Earlier user lines a follow-up may take its problem from.
_PRIOR_USER_LINES = 8


@dataclass
class Augmentation:
    prompt_messages: list[dict[str, str]]
    verified_subject: VerifiedSolveBlock | None = None
    solver_unverified: bool = False
    unverified_subject: str | None = None
    # A reply both halves of a two-part question already rendered.
    direct_text: str | None = None
    # The message asks for more than its solve: the model answers the rest.
    asks_more: bool = False
    # SymPy ran out of time on the turn's problem: the tool loop does not run it again.
    solve_timed_out: bool = False
    # The message's subject, as the subject order read it.
    subject: SubjectName | None = None
    # A calculation nothing verified: the model writes a ```worked block (``worked_turn``).
    worked: WorkedLayout | None = None

    async def direct_reply(
        self, request: TurnRequest, followup: SubjectFollowup, settings: Settings
    ) -> str | None:
        """The reply the verified solve writes itself, when the turn needs no model."""
        if self.direct_text:
            return self.direct_text
        if self.verified_subject is None or self.asks_more:
            return None
        return await read_direct_reply(
            self.verified_subject,
            request.content,
            settings,
            has_image_attachment=request.has_image_attachment,
            # The problem a follow-up solved again ("what if the voltage doubled?"): the
            # verified result answers it, not the line.
            verified_request_text=followup.math if followup.math is not None else followup.physics,
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
    money: bool = False,
    referent: Referent | None = None,
) -> Augmentation:
    """Phase B/C for one turn. A turn the gate turns away keeps its prompt as built.

    A money turn (``turn_prep.money``) has its numbers worked already: no subject solve.
    """
    if money:
        return Augmentation(prompt_messages)
    mode = identity.mode
    plan = plan_of(request.content, settings)
    detected_subject = await read_subject(
        _mixed_solve(plan) or request.content,
        settings,
        has_image_attachment=request.has_image_attachment,
        image_math_extract=request.image_math_extract,
    ) or await _parts_subject(request, settings, plan)
    if instant_reply is None:
        start_model_read_shadow(request.content, settings, redis, subject=detected_subject)
    needs_math, needs_chem = _turn_needs(request, settings, followup, detected_subject)
    if not _should_augment_web_and_tools(
        instant_reply=instant_reply,
        lightweight=mode.lightweight,
        minimal_personal=mode.minimal_personal,
        day_planning=mode.day_planning,
        ambiguous_nearby=identity.geo.ambiguous_nearby,
        rich_context=mode.rich_context,
        needs_math=needs_math,
        needs_chem=needs_chem,
    ):
        return Augmentation(prompt_messages, subject=detected_subject)

    # Phase B: the subject solve. Phase C: inject it before the last user message.
    with subject_adapter("math").solve_timeouts() as timed_out:
        fetched = await _fetch_subject_with_priors(
            request, identity, settings, redis, prompt_messages, followup, plan, referent
        )
    fetched = _readable_fetch(request, identity, prompt_messages, followup, fetched, referent)
    return Augmentation(
        prompt_messages=inject_subject_block(prompt_messages, fetched.subject_block),
        verified_subject=fetched.verified,
        solver_unverified=fetched.solver_unverified,
        unverified_subject=fetched.unverified_subject,
        direct_text=fetched.direct_text,
        asks_more=plan.multi and any(part.kind != "solve" for part in plan.parts),
        solve_timed_out=bool(timed_out),
        subject=detected_subject,
    )


def _readable_fetch(
    request: TurnRequest,
    identity: TurnIdentity,
    prompt_messages: list[dict[str, str]],
    followup: SubjectFollowup,
    fetched: SubjectFetch,
    referent: Referent | None = None,
) -> SubjectFetch:
    """The fetch held to the whole question it answers (``whole_question``): the message,
    the problem a follow-up solves again, and the earlier lines a terse follow-up borrows
    ("graph it" plots the last plottable line; a fragment such as "5" continues the open
    equation). Any of them unread, written in another language or with a number its
    writer's locale reads otherwise, and the result goes."""
    content = request.content
    borrowed: list[str] = []
    if subject_adapter("math").followups.borrows_earlier(content):
        borrowed = _prior_user_lines(request, prompt_messages, referent)
    return whole_question_fetch(
        content,
        fetched,
        locale=identity.user.locale,
        problems=(followup.math, followup.chemistry, followup.physics, *borrowed),
    )


def _mixed_solve(plan: TurnPlan) -> str | None:
    """The one maths, physics or chemistry request of a message that asks for more.

    "Solve 2x + 5 = 17 and also what's the weather in Paris" is solved from its own
    words: the whole line read as one problem lost the verification.
    """
    solves = plan.of_kind("solve")
    return solves[0].text if plan.multi and len(solves) == 1 else None


async def _parts_subject(
    request: TurnRequest, settings: Settings, plan: TurnPlan
) -> SubjectName | None:
    """The subject of a message of separate problems no subject reads whole ("A car goes
    100 m in 5 s; find its speed. A train goes 300 m in 10 s; find its speed."): its first
    part's (``solved_parts``), as the turn's reading takes it. Each part is still solved
    with its own."""
    for part in solved_parts(plan):
        subject = await read_subject(
            part.text, settings, has_image_attachment=request.has_image_attachment
        )
        if subject is not None:
            return subject
    return None


def _solve_parts(plan: TurnPlan) -> tuple[str, ...]:
    """The separate questions of a message that holds several, each solved on its own:
    "A ball is dropped from 20 m. What is its speed after 1 s? How long does it take to
    reach the ground?" is two (``turn_prep.intents``)."""
    solves = plan.of_kind("solve")
    return tuple(part.text for part in solves) if len(solves) >= 2 else ()


def _turn_needs(
    request: TurnRequest,
    settings: Settings,
    followup: SubjectFollowup,
    detected_subject: SubjectName | None,
) -> tuple[bool, bool]:
    """Whether the turn needs maths and chemistry, in that order. A search is the
    reply's own call (``tool_loop.reply_calls``), never read here."""
    content = request.content
    needs_math = (
        settings.math_tools_enabled
        and (
            detected_subject == "math"
            or followup.math is not None
            or subject_adapter("math").followups.continues_alone(content)
        )
    ) or (
        settings.physics_enabled and (detected_subject == "physics" or followup.physics is not None)
    )
    needs_chem = settings.chemistry_enabled and (
        detected_subject == "chemistry" or followup.chemistry is not None
    )
    return needs_math, needs_chem


async def _fetch_subject_with_priors(
    request: TurnRequest,
    identity: TurnIdentity,
    settings: Settings,
    redis: Redis,
    prompt_messages: list[dict[str, str]],
    followup: SubjectFollowup,
    plan: TurnPlan,
    referent: Referent | None,
) -> SubjectFetch:
    priors = _prior_user_lines(request, prompt_messages, referent)
    return await fetch_subject(
        request.content,
        settings,
        prior_user_messages=priors,
        has_image_attachment=request.has_image_attachment,
        image_math_extract=request.image_math_extract,
        math_followup_problem=followup.math,
        chemistry_followup_problem=followup.chemistry,
        physics_followup_problem=followup.physics,
        on_status=request.on_status,
        redis=redis,
        subject_text=_mixed_solve(plan),
        parts=_solve_parts(plan),
        parts_answer_all=all(part.kind == "solve" for part in plan.parts),
    )


def _prior_user_lines(
    request: TurnRequest, prompt_messages: list[dict[str, str]], referent: Referent | None
) -> list[str]:
    """Earlier user lines can hold the problem a follow-up refers to. They come from the
    prompt's own history: a second read of the messages raced the current line. When a model
    read which one "draw it" means (``referent_read``), only that one is read: "graph it"
    after "What's the capital of France?" draws no older curve. A read that named none is
    no read: "graph it" to "Want me to graph it?" still finds the curve, however far back."""
    if referent is not None and referent.problem:
        return [referent.problem]
    return _prompt_prior_user_messages(prompt_messages, request.content)[-_PRIOR_USER_LINES:]


async def augment_after_prompt(
    request: TurnRequest,
    identity: TurnIdentity,
    settings: Settings,
    redis: Redis,
    prompt_messages: list[dict[str, str]],
    instant_reply: str | None,
    money: MoneyTurn | None,
) -> tuple[Augmentation, str | None]:
    """Phases B and C after the prompt: a follow-up's subject, the verified solve (none for a
    money turn, whose numbers are worked already), and a reply the solve writes itself."""
    followup, referent = await _turn_followup(
        request, settings, prompt_messages, small_talk=identity.mode.lightweight
    )
    if followup.asked is not None:
        # "Do it" after a posed problem: the turn is the problem, as if typed, and read so,
        # in the pool.
        request = replace(request, content=followup.asked)
        await read_off_loop(
            ask_turn_readings,
            followup.asked,
            prior_user=None,
            prior_model=None,
            lesson_active=False,
            has_image_attachment=request.has_image_attachment,
            settings=settings,
            timeout=settings.subject_read_timeout_seconds,
        )
    if instant_reply is None:
        instant_reply = location_not_set_reply(
            request.content, identity.geo, followup, role_content_dicts(prompt_messages)
        )
    augmented = await gather_and_inject(
        request,
        identity,
        settings,
        redis,
        prompt_messages,
        followup,
        instant_reply=instant_reply,
        money=money is not None,
        referent=referent,
    )
    timing = request.timing
    if timing is not None:
        timing.mark_phase("augment_done")
        timing.mark_prompt_ready()
    if instant_reply is None:
        instant_reply = await augmented.direct_reply(request, followup, settings)
    subject = augmented.subject or _followup_subject(followup)
    answered = bool(instant_reply is not None or augmented.verified_subject or money)
    lightweight = identity.mode.lightweight
    augmented.worked = worked_layout(
        request.content,
        subject,
        settings,
        answered=answered,
        lightweight=lightweight,
        several_requests=plan_of(request.content, settings).multi,
    )
    if augmented.worked is not None:
        augmented.prompt_messages = with_worked_contract(augmented.prompt_messages)
    elif checks_stated_results(
        request.content, subject, answered=answered, lightweight=lightweight
    ):
        augmented.prompt_messages = with_result_check_contract(augmented.prompt_messages)
    return augmented, instant_reply


async def _turn_followup(
    request: TurnRequest,
    settings: Settings,
    prompt_messages: list[dict[str, str]],
    *,
    small_talk: bool,
) -> tuple[SubjectFollowup, Referent | None]:
    """The earlier problem the line follows up, and what "it" is in "draw it"."""
    # What "it" is: the turn's read, kept since the photo intercept asked it. And the
    # problem "3" or "the area" continues, which a model reads too.
    recent = request.recent_messages or []
    referent = await referent_for_turn(settings, request.content, recent)
    continued = await continuation_for_turn(settings, request.content, recent)
    timeout = settings.subject_read_timeout_seconds
    followup = await read_off_loop(
        resolve_subject_followup,
        request.content,
        role_content_dicts(prompt_messages),
        referent.problem if referent is not None else None,
        continued,
        timeout=timeout,
    )
    if followup is not None and followup.found:
        return followup, referent
    # "Do it" after a problem the assistant posed: a model reads which problem, when the
    # line has no subject of its own and is no "thanks".
    if (
        not small_talk
        and referent is None
        and continued is None
        and subject_of(
            request.content,
            has_image_attachment=request.has_image_attachment,
            chemistry_enabled=settings.chemistry_enabled,
        )
        is None
    ):
        posed = await posed_for_turn(settings, request.content, recent)
        if posed is not None:
            followup = await read_off_loop(
                resolve_posed_followup,
                request.content,
                posed.problem,
                posed.reply,
                posed.changed,
                posed.restated,
                timeout=timeout,
            )
    return followup or SubjectFollowup(), referent


def _followup_subject(followup: SubjectFollowup) -> SubjectName | None:
    """The subject of the earlier problem a follow-up solves again."""
    if followup.physics is not None:
        return "physics"
    if followup.chemistry is not None:
        return "chemistry"
    return "math" if followup.math is not None else None

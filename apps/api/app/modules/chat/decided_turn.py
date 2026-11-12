"""The turn's read, applied before the reply's call: Auto's lane, the thinking, the layout.

The read (``chat.turn_decision``) starts when the turn loads and answers in about a second.
The turn's lane was chosen by word rules then, and the prep ran beside the read; by the
reply's call the read says the subject and how hard the question is. Its answer replaces
the rules' (``model_routing.decided``):

- the thinking level follows the effort, question by question (maths, physics and
  chemistry think only when the read calls them hard);
- Auto's lane follows the subject and the effort through catalog data;
- a maths, physics or chemistry calculation no solver verified gets the ```worked block's
  contract, as one the subject readers recognised does, when the readers missed it;
- an everyday message the read calls an answer to the last reply, or a change to what the
  conversation is about, gets a note beside it saying so (``FOLLOW_NOTES``): "the
  language" after "Python the language, or the snake?" was asked back on every try without it.

Numbers a server path already worked keep their lane and their level (a verified solve, a
money card): the model only presents them. A lesson's step stays quick, a regenerate or a
disputed answer keeps its escalation, a model the user picked keeps its model. A turn that
waited for the read to search (``reply_calls.search_the_live_read``) has it already; one
that did not waits for it as long as a search would, and only when the answer could move
its lane. With no answer in time the word rules stand. Each turn's trace says which
decided (``turn_trace.note_decision``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import Settings
from app.modules.billing import plan as plan_service
from app.modules.billing.entitlements import has_strong_everyday_model
from app.modules.chat.json_output import is_json_request
from app.modules.chat.model_routing.decided import decided_lane, decided_level, math_backups
from app.modules.chat.prompt_constants.conversation import FOLLOW_NOTES
from app.modules.chat.prompt_inject import inject_before_last_user
from app.modules.chat.turn_decision import TurnDecision, turn_decision_result
from app.modules.chat.turn_prep.reading import plan_of
from app.modules.chat.turn_trace import note_decision, note_prompt_rule, note_route
from app.modules.chat.worked_turn import states_a_quantity, with_worked_contract, worked_layout
from app.modules.turn_reading.lesson_flow import active_lesson_step, outline_awaits_pick
from app.modules.turn_reading.school_question import is_school_exercise

if TYPE_CHECKING:
    from app.modules.chat.turn_prep.context import StreamContext

# The read's subjects the worked layout reads, by the subject readers' names.
_WORKED_SUBJECTS = {"maths": "math", "physics": "physics", "chemistry": "chemistry"}
# The subjects whose follow-ups get the read's note. Maths, physics, chemistry and money
# read their own ("what if it was 30 m/s?" changes the posed problem, ``chat.posed_read``).
_NOTED_SUBJECTS = frozenset({"everyday", "code"})


async def decide_from_the_read(ctx: StreamContext, settings: Settings) -> None:
    """The read's answer, applied to the turn; the word rules' choices when it has none."""
    read = await _the_read(ctx, settings)
    if read is None or read.effort is None:
        note_decision("rules")
        return
    note_decision(
        "read",
        subject=read.subject,
        effort=read.effort,
        picture=read.picture,
        follow=read.follow,
    )
    ctx.thinking = _level(ctx, read)
    _follow_the_lane(ctx, settings, read)
    _worked_layout(ctx, settings, read)
    _follow_note(ctx, read)


async def _the_read(ctx: StreamContext, settings: Settings) -> TurnDecision | None:
    """The read when it is in; waited for only when it could still move Auto's lane."""
    task = ctx.live_read
    if task is None:
        return None
    if task.done():
        if task.cancelled() or task.exception() is not None:
            return None
        return task.result()
    if not _lane_may_move(ctx):
        return None
    return await turn_decision_result(task, settings)


def _worked(ctx: StreamContext) -> bool:
    """A server path worked the numbers: a verified solve (maths, physics, chemistry, or a
    tool's), or a money turn, whose calculator card holds them."""
    return ctx.verified_subject is not None or ctx.money is not None


def _lane_may_move(ctx: StreamContext) -> bool:
    """The one test of whether the read may move Auto's lane, and so whether the turn waits
    for it. A lesson keeps its quick lane (``route``'s "lesson"), small talk has nothing to
    move, a photo turn keeps the model that reads it, a JSON ask its model with JSON mode;
    a regenerate or a dispute keeps its escalation, a model the user picked their pick."""
    return (
        ctx.auto_routed
        and ctx.user is not None
        and not _worked(ctx)
        and ctx.instant_reply is None
        and not ctx.terminal_image_content
        and ctx.thinking != "escalate"
        and not ctx.lightweight_turn
        and active_lesson_step(ctx.recent_messages) is None
        and not _shows_a_picture(ctx)
        and not is_json_request(ctx.user_message_content)
    )


def _level(ctx: StreamContext, read: TurnDecision) -> bool | str:
    """The thinking level: the read's effort, except where the turn's own state decides."""
    if ctx.thinking == "escalate" or _worked(ctx):
        return ctx.thinking
    if active_lesson_step(ctx.recent_messages) is not None:
        # A lesson under way keeps its steps quick (``route``'s "lesson").
        return "off"
    return decided_level(read.subject, read.effort or "none")


def _follow_the_lane(ctx: StreamContext, settings: Settings, read: TurnDecision) -> None:
    """Auto's lane for the read's subject and effort, where it may move (``_lane_may_move``)."""
    if not _lane_may_move(ctx) or ctx.user is None or read.subject is None:
        return
    pool = plan_service.model_pool(ctx.user, settings)
    lane = decided_lane(
        read.subject,
        read.effort or "none",
        pool,
        unsteady=ctx.unsteady_models,
        strong_everyday=has_strong_everyday_model(ctx.user, settings),
        math_lane=plan_service.math_lane_for(ctx.user, settings),
    )
    if lane is None:
        return
    note_route(f"read.{read.subject}.{read.effort}")
    # A STEM lane's own backup first (GLM), then the rules' model, then the pool's order.
    first = [*math_backups(read.subject, lane, pool, ctx.unsteady_models), ctx.model]
    backups = [alias for alias in dict.fromkeys([*first, *ctx.fallback_models]) if alias != lane]
    ctx.model, ctx.fallback_models = lane, backups


def _shows_a_picture(ctx: StreamContext) -> bool:
    return any(
        isinstance(message.get("content"), list)
        for message in ctx.prompt_messages
        if isinstance(message, dict)
    )


def _worked_layout(ctx: StreamContext, settings: Settings, read: TurnDecision) -> None:
    """The ```worked contract for a calculation the subject readers missed and the read
    calls maths, physics or chemistry (P16, a resistor problem, 2026-11-10: no reader
    claimed it, so the everyday prompt answered it)."""
    subject = _WORKED_SUBJECTS.get(read.subject or "")
    if subject is None or ctx.worked is not None or _worked(ctx) or ctx.instant_reply:
        return
    content = ctx.user_message_content
    # A value to work with, not only a digit: "Name this compound: CH3CH2CH2OH" got a Given
    # and a Required for its formula (live, 2026-11-10).
    if not (states_a_quantity(content) or is_school_exercise(content)):
        return
    layout = worked_layout(
        content,
        subject,
        settings,
        answered=False,
        lightweight=ctx.lightweight_turn,
        several_requests=plan_of(content, settings).multi,
    )
    if layout is not None:
        ctx.worked = layout
        ctx.prompt_messages = with_worked_contract(ctx.prompt_messages)


def _follow_note(ctx: StreamContext, read: TurnDecision) -> None:
    """The read's word on how the message leans on the conversation, beside it. A lesson, an
    outline awaiting a pick and the turn after a clarify card read the reply their own way
    (``message_notes``); numbers a server path worked are the reply's to present, and a
    calculation the subject readers gave the ```worked contract is laid out by it, whatever
    the read calls the subject."""
    note = FOLLOW_NOTES.get(read.follow or "")
    if note is None or read.subject not in _NOTED_SUBJECTS or ctx.after_card:
        return
    if _worked(ctx) or ctx.worked is not None:
        return
    if active_lesson_step(ctx.recent_messages) or outline_awaits_pick(ctx.recent_messages):
        return
    note_prompt_rule(f"read.follow_{read.follow}")
    ctx.prompt_messages = inject_before_last_user(ctx.prompt_messages, note)

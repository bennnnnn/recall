"""Read the turn's message once, in the SymPy pool, before code on the event loop asks.

Routing, the prompt builder, the subject fetch, the tool loop and the finalize passes
all ask the same readings of the message: its plan, its subject, whether physics or
maths claims it, its maths and physics intents. ``ask_turn_readings`` asks each of them
in a pool worker, where a hostile message stops at the timeout, and the turn keeps the
answers (``app/core/readings.py``). Workers import this module, so it stays light:
nothing here may import the prompt, attachment or database stack.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.core.config import Settings
from app.core.readings import first_read, read_off_loop, readings_declined
from app.modules.turn_reading.plan import TurnPlan, single_plan
from app.modules.turn_reading.turn import (
    PlanReason,
    TurnReading,
    current_turn_reading,
    keep_turn_reading,
)

# Exchanges a terse follow-up reaches back over (``math.followup``).
_FOLLOWUP_EXCHANGES = 4


def read_turn(content: str, settings: Settings) -> TurnReading:
    """The turn's reading of its message, built once from the pooled readings and kept.

    Its fields come from the readings ``ask_turn_readings`` made in the pool, so building
    it reads nothing on the loop.
    """
    from app.modules.chat.turn_prep.intents import plan_turn

    chemistry = settings.chemistry_enabled
    kept = current_turn_reading()
    if kept is not None and kept.reads(content, chemistry_enabled=chemistry):
        return kept
    reason: PlanReason
    if readings_declined():
        # The pool gave up: the whole message is one request, as ``plan_turn`` declines.
        plan, reason = single_plan(content), "read_declined"
    else:
        plan = plan_turn(content, chemistry_enabled=chemistry)
        reason = "several_requests" if plan.multi else "one_request"
    reading = TurnReading(content, chemistry, plan, reason)
    keep_turn_reading(reading)
    return reading


def plan_of(text: str, settings: Settings | None = None) -> TurnPlan:
    """The plan of ``text``: the turn's own plan when ``text`` is the turn's message.

    A caller holding another text (a line from the prompt the turn rewrote, an earlier
    line) reads that text's plan as before.
    """
    from app.modules.chat.turn_prep.intents import plan_turn

    chemistry = settings is None or settings.chemistry_enabled
    kept = current_turn_reading()
    if kept is not None and kept.reads(text, chemistry_enabled=chemistry):
        return kept.plan
    return plan_turn(text, chemistry_enabled=chemistry)


def ask_turn_readings(
    content: str,
    *,
    prior_user: str | None,
    prior_model: str | None,
    lesson_active: bool,
    has_image_attachment: bool,
    settings: Settings,
    earlier_lines: tuple[str, ...] = (),
) -> None:
    """Every reading the turn's sync code asks of its message. Runs in a pool worker."""
    from app.modules.chat.model_routing.route import route_chat_model
    from app.modules.chat.turn_prep.intents import plan_turn
    from app.modules.math.tools.extract import extract_math_intent
    from app.modules.math.tools.prompt import needs_symbolic_math
    from app.modules.physics.extract import extract_physics_intent
    from app.services.subject_solving import detect_subject

    chemistry = settings.chemistry_enabled
    plan = plan_turn(content, chemistry_enabled=chemistry)
    # The plan's parts too: the tool loop asks each whether it is maths.
    for text in dict.fromkeys((content, *plan.texts())):
        detect_subject(text)
        detect_subject(text, has_image_attachment=has_image_attachment, chemistry_enabled=chemistry)
        if needs_symbolic_math(text):
            extract_math_intent(text)
    extract_math_intent(content)
    extract_physics_intent(content)
    # The follow-up readers ask the subject of the user's earlier lines: a physics or
    # chemistry problem is not replayed through maths. Routing asks the line before this
    # one whenever the turn may inherit its lane. A money follow-up asks each line's plan,
    # to read it in the parts its own turn did.
    for text in earlier_lines:
        detect_subject(text)
        plan_turn(text, chemistry_enabled=chemistry)
    if prior_user:
        detect_subject(prior_user, chemistry_enabled=chemistry)
    route_chat_model(
        content,
        prior_user=prior_user,
        prior_model=prior_model,
        lesson_active=lesson_active,
        settings=settings,
    )


async def read_turn_message(
    content: str,
    recent: Sequence[Any],
    settings: Settings,
    *,
    has_image_attachment: bool = False,
) -> None:
    """Read the message (and the line before it, for routing) off the loop, for this turn,
    and keep the turn's reading of it (``read_turn``).

    Turn load reads it; turn prep asks again (a regenerate, the behavior harness) and
    pays only for what changed.
    """
    from app.modules.chat.model_routing.route import last_user_turn
    from app.modules.turn_reading.lesson_flow import active_lesson_step
    from app.services.problem_followup import message_role_content

    earlier = list(recent)
    # The message's own row may already be in the window: it is not the line before it.
    if earlier and message_role_content(earlier[-1]) == ("user", content):
        earlier.pop()
    prior_user, prior_model = last_user_turn(earlier)
    if first_read(("turn_message", content, prior_user, has_image_attachment)):
        await read_off_loop(
            ask_turn_readings,
            content,
            prior_user=prior_user,
            prior_model=prior_model,
            lesson_active=active_lesson_step(list(recent)) is not None,
            has_image_attachment=has_image_attachment,
            settings=settings,
            earlier_lines=_earlier_user_lines(earlier),
            timeout=settings.subject_read_timeout_seconds,
        )
    read_turn(content, settings)


def _earlier_user_lines(earlier: Sequence[Any]) -> tuple[str, ...]:
    """The user's lines in the last four exchanges, as far back as a follow-up looks."""
    from app.services.problem_followup import message_role_content

    lines: list[str] = []
    for message in reversed(earlier):
        role, text = message_role_content(message)
        if role == "user" and text and text.strip():
            lines.append(text)
            if len(lines) == _FOLLOWUP_EXCHANGES:
                break
    return tuple(lines)


def warm_pool_worker() -> None:
    """The pool warm-up: a solve and a message read, so a turn pays neither's imports.

    A worker starts cold at boot and again after a timeout kills it; the executor runs
    this first, outside any timeout.
    """
    from app.modules.math.sympy_warmup import warm_math_worker

    warm_math_worker()
    ask_turn_readings(
        "A car goes from 0 to 100 km/h in 8 s. Find a, and also solve 2x + 3 = 7",
        prior_user=None,
        prior_model=None,
        lesson_active=False,
        has_image_attachment=False,
        settings=Settings.model_validate({}),
    )

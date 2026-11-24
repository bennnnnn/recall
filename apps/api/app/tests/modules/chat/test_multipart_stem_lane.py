"""A message that holds maths, physics or chemistry work among other requests routes to the
maths lane (``decided_turn._routed_by``, ``TurnReading.solve_subject``).

"A ball is thrown from the top of a 45 m cliff … Also solve x³ - 6x² + 11x - 6 = 0 and graph
it, draw the structure of aspirin and give its molar mass, and remind me tomorrow at 7 pm to
review projectile motion." was read as everyday as a whole (0.63 against 0.37 for the three
sciences together) and went to the everyday model, which slipped on the arithmetic
(2026-11-23). The plan read its parts as solves, and the pool read their subjects.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from app.core.readings import begin_turn
from app.models.orm import User
from app.models.routing_lanes import ROUTING
from app.modules.chat.decided_turn import decide_from_the_read
from app.modules.chat.decider_read import decision_fields
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.chat.turn_prep.intents import plan_turn
from app.modules.chat.turn_prep.reading import read_turn_message
from app.modules.chat.turn_trace import begin_turn_trace
from app.modules.turn_reading.turn import current_turn_reading
from app.tests.fakes import isolated_settings

_SETTINGS = isolated_settings()
OWNERS = (
    "A ball is thrown from the top of a 45 m cliff at 25 m/s, 35° above the horizontal. How "
    "long is it in the air, and how far from the base of the cliff does it land? Also solve "
    "x³ - 6x² + 11x - 6 = 0 and graph it, draw the structure of aspirin and give its molar "
    "mass, and remind me tomorrow at 7 pm to review projectile motion."
)
MATHS_AND_REMINDER = "Solve 2x + 5 = 17 and remind me tomorrow at 6 pm to do my homework."
EVERYDAY_PARTS = "What's a good pasta recipe for dinner, and remind me at 5 pm to buy groceries."


def _read(subject: str, *, think: bool = True, hard_odds: float | None = None) -> TurnDecision:
    return TurnDecision.model_validate(
        {"live": False, "subject": subject, "think": think, "hard_odds": hard_odds}
    )


async def _decided(content: str, read: TurnDecision, plan: str = "pro") -> StreamContext:
    begin_turn()
    await read_turn_message(content, [], _SETTINGS)
    future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    future.set_result(read)
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": content}],
        run_title=False,
        user_message_content=content,
        reserved_tokens=100,
        max_output_tokens=100,
    )
    ctx.user = User(id=uuid4(), email="a@b.c", plan=plan)
    ctx.auto_routed, ctx.thinking = True, "off"
    ctx.fallback_models = ["smart-chat", "qwen-3.7-flash"]
    ctx.live_read = future  # type: ignore[assignment]
    await decide_from_the_read(ctx, _SETTINGS)
    return ctx


@pytest.mark.parametrize(
    ("content", "subject"),
    [
        (OWNERS, "physics"),
        (MATHS_AND_REMINDER, "math"),
        ("Calculate the molar mass of water, and remind me at 8 pm to study.", "chemistry"),
        (EVERYDAY_PARTS, None),
        # One request: the read's subject stands, whatever the readers claim.
        ("Solve 2x + 5 = 17", None),
    ],
)
async def test_a_message_of_several_requests_names_the_subject_of_its_solve(
    content: str, subject: str | None
) -> None:
    begin_turn()
    await read_turn_message(content, [], _SETTINGS)
    reading = current_turn_reading()
    assert reading is not None and reading.solve_subject == subject


@pytest.mark.parametrize("plan", ["pro", "plus", "free"])
async def test_stem_work_among_other_requests_routes_to_the_maths_lane(plan: str) -> None:
    trace = begin_turn_trace("new")
    ctx = await _decided(OWNERS, _read("everyday", hard_odds=0.81), plan)
    assert ctx.model == (ROUTING.math_free if plan == "free" else ROUTING.math)
    # Weighed as a physics problem is: hard at the sciences' line, so it thinks.
    assert ctx.thinking == "hard"
    assert trace.route == "read.parts.physics.high"
    # The read's own answer is what the trace says the read decided.
    assert trace.decision is not None and trace.decision["subject"] == "everyday"


async def test_an_easy_solve_beside_a_reminder_answers_without_thinking() -> None:
    ctx = await _decided(MATHS_AND_REMINDER, _read("everyday", hard_odds=0.21))
    assert (ctx.model, ctx.thinking) == (ROUTING.math, "off")


async def test_the_text_reads_effort_stands_when_it_gives_no_odds() -> None:
    ctx = await _decided(MATHS_AND_REMINDER, _read("code", think=False))
    assert (ctx.model, ctx.thinking) == (ROUTING.math, "off")


@pytest.mark.parametrize(
    ("content", "read"),
    [
        # Everyday requests only: the everyday lane.
        (EVERYDAY_PARTS, _read("everyday", think=False, hard_odds=0.0)),
        # One request the read calls everyday keeps it: its words may only sound like a subject.
        ("Solve 2x + 5 = 17", _read("everyday", think=False, hard_odds=0.0)),
    ],
)
async def test_everyday_stays_everyday_without_a_solve_among_several(
    content: str, read: TurnDecision
) -> None:
    ctx = await _decided(content, read)
    assert (ctx.model, ctx.thinking) == ("free-chat", "off")


async def test_money_keeps_the_rules_lane() -> None:
    ctx = await _decided(MATHS_AND_REMINDER, _read("money", hard_odds=0.0))
    assert ctx.model == "free-chat"


def test_the_decider_keeps_the_hard_odds() -> None:
    answers = {
        "subject": {"choice": "everyday"},
        "think": {"noul": 0.7},
        "hard": {"noul": 0.81},
        "live": {"noul": 0.0},
        "asked": {"noul": 0.0},
    }
    fields = decision_fields(answers, has_earlier=False)
    assert fields is not None
    assert (fields["hard_odds"], fields["think"], fields["hard"]) == (0.81, True, False)


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        # A comma between two tasks cuts as ", and" does; two subjects' solves stay two.
        (
            "Find the area of a circle of radius 3, draw the structure of benzene",
            [
                ("solve", "Find the area of a circle of radius 3"),
                ("solve", "draw the structure of benzene"),
            ],
        ),
        (
            "Tell me a joke, remind me at 5 pm to call mom",
            [("ask", "Tell me a joke"), ("reminder", "remind me at 5 pm to call mom")],
        ),
    ],
)
def test_a_comma_before_a_fresh_task_starts_a_request(
    text: str, parts: list[tuple[str, str]]
) -> None:
    assert [(part.kind, part.text) for part in plan_turn(text).parts] == parts


def test_the_owners_message_plans_its_chemistry_as_a_part_of_its_own() -> None:
    kinds = [part.kind for part in plan_turn(OWNERS).parts]
    assert kinds == ["solve", "solve", "solve", "reminder"]
    assert "aspirin" in plan_turn(OWNERS).parts[2].text


@pytest.mark.parametrize(
    "text",
    [
        "Write a poem about the sea, make it rhyme",
        "In Python, write a function that reverses a string",
        # A comma before a task cuts only after a task.
        "When teaching me, explain one concept at a time, use practical examples, and ask me "
        "to solve a short exercise before moving on.",
        # One subject's solves stay one request.
        "Calculate the molar mass of water, draw the structure of ethanol",
        "If x = 2, find y when y = 3x + 1",
    ],
)
def test_a_comma_that_shapes_one_request_keeps_it_whole(text: str) -> None:
    assert not plan_turn(text).multi

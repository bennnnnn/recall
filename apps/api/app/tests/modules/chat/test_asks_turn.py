"""A verified instant reply the read says answers part of the message gives way to the model's
(``chat.asks_turn``).

P30 and P37 of the 2026-11-21 live round: "What frequency does a stationary listener hear as it
approaches, and as it moves away?" was answered for the approach alone, instantly, and "the
angle of the first-order maximum and the highest order" with the angle: the word rules counted
one ask each. The read counts two; the instant reply goes, the block is marked partial, and the
reply is told to answer the rest around the same card.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.modules.chat.asks_turn import _may_ask_more, write_the_rest
from app.modules.chat.decider_read import ASKS_COUNTS, decision_fields
from app.modules.chat.turn_decision import TurnDecision
from app.modules.physics.reply_policy import PHYSICS_PARTIAL_POLICY
from app.services.solving import VerifiedPhysicsBlock
from app.tests.modules.chat.test_drawing_turn import _ctx, _settings

P30 = (
    "An ambulance siren emits 700 Hz. The ambulance moves at 30 m/s and the speed of sound "
    "is 343 m/s. What frequency does a stationary listener hear as it approaches, and as it "
    "moves away?"
)
P37 = (
    "Light of wavelength 550 nm falls on a diffraction grating with 600 lines per mm. Find "
    "the angle of the first-order maximum and the highest order that can be seen."
)
P8 = (
    "A road curve of radius 120 m is banked at 15°. At what speed can a car take the curve "
    "with no friction needed?"
)


def _verified(question: str) -> VerifiedPhysicsBlock:
    from app.core.config import Settings
    from app.modules.physics.prompt import solve_physics_request

    outcome, block = solve_physics_request(
        question,
        Settings(_env_file=None, math_tools_enabled=True),  # type: ignore[call-arg]
        None,
    )
    assert outcome == "verified" and block is not None
    return block


def _read(asks: int | None, *, delay: float = 0.0) -> asyncio.Task[TurnDecision | None]:
    async def answer() -> TurnDecision | None:
        await asyncio.sleep(delay)
        return TurnDecision(live=False, think=False, asks=asks)

    return asyncio.ensure_future(answer())


def _turn(question: str, read: asyncio.Task[TurnDecision | None] | None) -> Any:
    return _ctx(
        question,
        instant_reply="**Given** ... ```answer\n767 Hz\n```",
        verified_subject=_verified(question),
        live_read=read,
    )


@pytest.mark.parametrize("question", [P30, P37])
async def test_a_partial_result_gives_way_to_the_models_reply(question: str) -> None:
    ctx = _turn(question, _read(2))
    await write_the_rest(ctx, _settings())
    assert ctx.instant_reply is None
    assert isinstance(ctx.verified_subject, VerifiedPhysicsBlock) and ctx.verified_subject.partial
    assert ctx.prompt_messages[-2]["content"] == PHYSICS_PARTIAL_POLICY


@pytest.mark.parametrize(
    ("asks", "delay", "kept"),
    [
        # The read counts the one ask the result answers.
        (1, 0.0, True),
        # No count from the read: the word rules decided, and the reply stands.
        (None, 0.0, True),
        # A read later than the reply waits keeps the card, losing a part at worst.
        (2, 5.0, True),
    ],
)
async def test_the_instant_reply_stands_unless_the_read_counts_more(
    asks: int | None, delay: float, kept: bool
) -> None:
    ctx = _turn(P30, _read(asks, delay=delay))
    await write_the_rest(ctx, _settings(live_read_wait_seconds=0.05))
    assert (ctx.instant_reply is not None) is kept
    assert isinstance(ctx.verified_subject, VerifiedPhysicsBlock)
    assert not ctx.verified_subject.partial


async def test_a_single_ask_never_waits_for_the_read() -> None:
    """P8 asks one thing in one sentence: the reply goes out without asking the read."""
    read = _read(2, delay=5.0)
    ctx = _turn(P8, read)
    await asyncio.wait_for(write_the_rest(ctx, _settings()), timeout=0.5)
    assert ctx.instant_reply is not None
    read.cancel()


@pytest.mark.parametrize(
    ("text", "may"),
    [
        (P30, True),
        (P37, True),
        (P8, False),
        (
            "A 2 kg ball and a 3 kg ball are dropped from 45 m. How long do they take to land?",
            False,
        ),
        ("Find the speed. Then find the time.", True),
    ],
)
def test_only_an_ask_that_joins_more_waits(text: str, may: bool) -> None:
    assert _may_ask_more(text) is may


@pytest.mark.parametrize(("choice", "count"), [*ASKS_COUNTS.items(), ("several", None)])
def test_the_reads_count_is_its_choice(choice: str, count: int | None) -> None:
    answers = {
        "subject": {"choice": "physics"},
        "think": {"noul": 0.1},
        "hard": {"noul": 0.1},
        "picture": {"choice": "none"},
        "follow": {"choice": "none"},
        "live": {"noul": 0.0},
        "asked": {"noul": 0.0},
        "asks": {"choice": choice},
    }
    fields = decision_fields(answers, has_earlier=False)
    assert fields is not None and fields["asks"] == count
    assert TurnDecision(**fields).asks == count

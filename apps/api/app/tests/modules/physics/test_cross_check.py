"""A verified physics answer held to the formal reader's reading (``physics.cross_check``).

The live QA round of 2026-11-22 found three checked wrong answers in 100 casual rewordings:
the extractors bound "slowing down at 3 m/s^2" as +3 and read "kicked sideways off a 30 m
cliff" as a fall in one line. Each is held here to the reading a model writes of it, as the
turn holds it, and two readings that differ leave the question to the model, unchecked.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.modules.physics import cross_check as cc
from app.modules.physics.formal_read import FormalReading
from app.modules.physics.prompt import solve_or_say_why, unverified_physics_note
from app.services.formal.problem import FormalProblem
from app.services.solving import VerifiedPhysicsBlock

_SETTINGS = Settings(_env_file=None)  # type: ignore[call-arg]

BRAKING = (
    "a car is slowing down at 3 m/s^2 for 4 s and at the end it is going 8 m/s. How fast was "
    "it going before it started braking?"
)
KICKED = (
    "a ball gets kicked sideways at 15 m/s off a 30 m cliff, whats its vertical velocity after 2 s?"
)
THROWN = "a ball gets thrown sideways at 10 m/s off a 20 m high cliff. whats its speed after 1 s?"
SPEED_UP = "A car speeds up from 10 m/s to 30 m/s in 4 s. How far does it go?"


def _ask(value: float | None, unit: str, *, symbol: str = "x", part: str = "") -> dict[str, Any]:
    return {"part": part, "symbol": symbol, "unit": unit, "answer": value}


def _setup(*asked: dict[str, Any]) -> FormalProblem:
    return FormalProblem.model_validate({"equations": ["x = 1"], "asked": list(asked)})


def _server(value: float, unit: str, *, symbol: str = "x", band: float = 0.0) -> dict[str, Any]:
    return {
        "part": "",
        "symbol": symbol,
        "value": value,
        "unit": unit,
        "low": value * (1 - band),
        "high": value * (1 + band),
        "agrees": True,
    }


def _asks(setup: FormalProblem, *server: dict[str, Any]) -> list[cc.ReadAsk]:
    return cc.reading_asks(setup, {"solved": bool(server), "answers": list(server)})


@pytest.mark.parametrize(
    ("answers", "asks", "found"),
    [
        # The QA round's three: the solver's reading against the model's.
        ([(-4.0, "m/s")], _asks(_setup(_ask(20, "m/s")), _server(20, "m/s")), "disagree"),
        ([(15.0, "m/s")], _asks(_setup(_ask(-19.6, "m/s")), _server(-19.62, "m/s")), "disagree"),
        ([(30.0, "m/s")], _asks(_setup(_ask(14.0, "m/s")), _server(14.01, "m/s")), "disagree"),
        # The same value in another unit of its kind, and a sign that is only a direction.
        ([(20.0, "m/s")], _asks(_setup(_ask(72, "km/h"))), "agree"),
        ([(-19.62, "m/s")], _asks(_setup(_ask(19.62, "m/s"))), "agree"),
        # Within the band the standard constants allow (g as 9.8 or 10), or 2%.
        ([(2.02, "s")], _asks(_setup(_ask(None, "s")), _server(2.0, "s", band=0.02)), "agree"),
        ([(0.759, "eV")], _asks(_setup(_ask(0.77, "eV"))), "agree"),
        ([(0.759, "eV")], _asks(_setup(_ask(0.80, "eV"))), "disagree"),
        # Either the server's value or the setup's own answer may be the one it agrees with.
        ([(80.0, "m")], _asks(_setup(_ask(85, "m")), _server(80, "m")), "agree"),
        ([(80.0, "m")], _asks(_setup(_ask(80, "m")), _server(85, "m")), "agree"),
        # A card may show more than was asked (both balls' speeds after the collision)...
        ([(2.0, "m/s"), (4.0, "m/s")], _asks(_setup(_ask(4, "m/s"))), "agree"),
        ([(1.96, "m/s^2"), (7.85, "N")], _asks(_setup(_ask(7.84, "N"))), "agree"),
        # ...and a partial solve less than the reading asks.
        (
            [(3.0, "s")],
            _asks(_setup(_ask(3, "s", symbol="t"), _ask(44.1, "m", symbol="d"))),
            "agree",
        ),
        ([(3.0, "s")], _asks(_setup(_ask(3, "s", part="a"), _ask(5, "s", part="b"))), "agree"),
        # The reading asks another quantity: it read another question.
        ([(20.0, "J")], _asks(_setup(_ask(4, "s"))), "disagree"),
        # Nothing to hold it to: no value asked, or units neither side reads.
        ([(20.0, "J")], [], "unread"),
        ([(20.0, "J")], _asks(_setup(_ask(None, "J"))), "unread"),
        ([(20.0, "zorks")], _asks(_setup(_ask(20, "J"))), "unread"),
        ([], _asks(_setup(_ask(20, "J"))), "unread"),
    ],
)
def test_verdict_holds_the_solver_to_the_reading(
    answers: list[tuple[float, str]], asks: list[cc.ReadAsk], found: str
) -> None:
    assert cc.verdict(answers, asks) == found


def _block(question: str) -> VerifiedPhysicsBlock:
    outcome, block, _why = solve_or_say_why(question, _SETTINGS, None)
    assert outcome == "verified" and isinstance(block, VerifiedPhysicsBlock), outcome
    return block


def test_the_solver_answers_carry_their_units() -> None:
    assert cc.solver_answers(_block(SPEED_UP)) == [(80.0, "m")]


def _reading(*asked: dict[str, Any], server: tuple[dict[str, Any], ...] = ()) -> FormalReading:
    return FormalReading(_setup(*asked), {"solved": bool(server), "answers": list(server)})


async def test_a_reading_that_differs_is_a_disagreement() -> None:
    block = _block(SPEED_UP)
    reading = _reading(_ask(60, "m"), server=(_server(60, "m"),))
    with patch("app.modules.physics.formal_read.formal_reading", AsyncMock(return_value=reading)):
        assert await cc.cross_check(block, SPEED_UP, _SETTINGS) == "disagree"


async def test_a_reading_that_agrees_keeps_the_check() -> None:
    block = _block(SPEED_UP)
    reading = _reading(_ask(80, "m"), server=(_server(80, "m"),))
    with patch("app.modules.physics.formal_read.formal_reading", AsyncMock(return_value=reading)):
        assert await cc.cross_check(block, SPEED_UP, _SETTINGS) == "agree"


@pytest.mark.parametrize("failure", ["none", "raises", "late"])
async def test_no_reading_in_time_leaves_the_check_standing(failure: str) -> None:
    block = _block(SPEED_UP)

    async def read(*_args: Any, **_kwargs: Any) -> FormalReading | None:
        if failure == "raises":
            raise RuntimeError("provider down")
        if failure == "late":
            await asyncio.sleep(5)
        return None

    settings = _SETTINGS.model_copy(update={"formal_wait_seconds": 0.05})
    with patch("app.modules.physics.formal_read.formal_reading", read):
        assert await cc.cross_check(block, SPEED_UP, settings) == "unread"


async def test_a_block_with_no_number_is_never_read() -> None:
    block = replace(_block(SPEED_UP), answer_values=(), answer_units=(), physics_parts=())
    reading = AsyncMock()
    with patch("app.modules.physics.formal_read.formal_reading", reading):
        assert await cc.cross_check(block, SPEED_UP, _SETTINGS) == "unread"
    reading.assert_not_called()


async def _solve(question: str, reading: FormalReading | None, settings: Settings) -> Any:
    from app.modules.physics.subject import PHYSICS_SUBJECT
    from app.services.subjects.registry import SubjectRequest

    request = SubjectRequest(text=question, math_text=question)
    with (
        patch("app.modules.physics.formal_read.formal_reading", AsyncMock(return_value=reading)),
        patch("app.core.sympy_executor.run_sympy", _in_process),
    ):
        return await PHYSICS_SUBJECT.solve(request, settings)


async def _in_process(fn: Any, *args: Any, **_kwargs: Any) -> Any:
    return fn(*args)


async def test_the_turn_leaves_a_contradicted_answer_to_the_model() -> None:
    """A second reading that differs: no check, no solver value in the prompt, the model's
    own unverified answer (and no "could not be verified" claim)."""
    reading = _reading(_ask(60, "m"), server=(_server(60, "m"),))
    augmentation = await _solve(SPEED_UP, reading, _SETTINGS)
    assert augmentation.verified is None
    assert augmentation.prompt_block == unverified_physics_note()
    assert augmentation.unverified is False


async def test_the_turn_keeps_an_answer_the_reading_agrees_with() -> None:
    reading = _reading(_ask(80, "m"), server=(_server(80, "m"),))
    augmentation = await _solve(SPEED_UP, reading, _SETTINGS)
    assert isinstance(augmentation.verified, VerifiedPhysicsBlock)
    assert augmentation.verified.answer_values == (80.0,)


@pytest.mark.parametrize(
    "switch", ["physics_cross_check_enabled", "formal_reader_enabled"], ids=str
)
async def test_off_every_solver_answer_is_checked_as_before(switch: str) -> None:
    reading = _reading(_ask(60, "m"), server=(_server(60, "m"),))
    settings = _SETTINGS.model_copy(update={switch: False})
    augmentation = await _solve(SPEED_UP, reading, settings)
    assert isinstance(augmentation.verified, VerifiedPhysicsBlock)


# --- the QA round's three, read right or left to the model by the solver itself --------------


def test_slowing_down_at_a_rate_is_a_negative_acceleration() -> None:
    """Any tense of slowing or braking "at" a rate signs it: v_i = v_f - at = 8 + 12."""
    assert cc.solver_answers(_block(BRAKING)) == [(20.0, "m/s")]
    slowed = "a car slowed down at 2 m/s^2 for 3 s from 15 m/s. what is its final speed?"
    assert cc.solver_answers(_block(slowed)) == [(9.0, "m/s")]


@pytest.mark.parametrize("question", [KICKED, THROWN])
def test_a_sideways_launch_off_a_cliff_is_no_motion_along_one_line(question: str) -> None:
    """Its height is no displacement along its speed: the one-line laws decline it, and the
    formal reader and the model answer it (v_y = gt, |v| = sqrt(u² + (gt)²))."""
    outcome, block, _why = solve_or_say_why(question, _SETTINGS, None)
    assert block is None and outcome in ("note", "failed")


def test_a_sideways_launch_is_level_for_the_projectile_laws() -> None:
    """One word set for both: "sideways", like "horizontally", states the 0° launch."""
    question = "a ball gets kicked sideways at 15 m/s off a 30 m cliff. how far does it land?"
    ((value, unit),) = cc.solver_answers(_block(question))
    assert unit == "m" and value == pytest.approx(15 * (2 * 30 / 9.81) ** 0.5, rel=1e-3)

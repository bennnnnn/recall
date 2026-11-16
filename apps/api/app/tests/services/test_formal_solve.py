"""A model's written-down setup is checked and solved by the server (``services.formal``).

The model reads the question in any wording and language; the server does the arithmetic,
and refuses a setup that uses a number the student never gave, mixes kinds of quantity, or
tries anything that is not plain arithmetic.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.formal.solve import grounded, parse_number, solve_formal

CAR = "my car goes from 0 to 100 km/h in 8 seconds, what's the acceleration in m/s^2"
DROP = "A ball is dropped from a 45 m tall building. How long does it take to hit the ground?"
PARALLEL_ES = "Dos resistencias de 10 ohmios están en paralelo a 5 V, ¿cuál es la corriente total?"
THROW = "A ball is thrown at 20 m/s at 30° above horizontal. Find its range."


def _g(value: str = "9.81") -> dict[str, Any]:
    return {"symbol": "g", "value": value, "unit": "m/s^2", "constant": True}


def _car(**changes: Any) -> dict[str, Any]:
    setup: dict[str, Any] = {
        "givens": [
            {"symbol": "v0", "value": "0", "unit": "km/h", "quote": "0"},
            {"symbol": "v", "value": "100", "unit": "km/h", "quote": "100 km/h"},
            {"symbol": "t", "value": "8", "unit": "s", "quote": "8 seconds"},
        ],
        "unknowns": [{"symbol": "a", "unit": "m/s^2"}],
        "equations": ["v = v0 + a*t"],
        "target": "a",
        "target_unit": "m/s^2",
        "answer": 3.47,
    }
    return setup | changes


def _drop(**changes: Any) -> dict[str, Any]:
    setup: dict[str, Any] = {
        "givens": [{"symbol": "h", "value": "45", "unit": "m", "quote": "45 m"}, _g()],
        "unknowns": [{"symbol": "t", "unit": "s"}],
        "equations": ["h = g*t**2/2"],
        "target": "t",
        "target_unit": "s",
        "answer": 3.03,
    }
    return setup | changes


def _solve(setup: dict[str, Any], question: str) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(solve_formal(json.dumps(setup), question))
    return result


def test_the_server_works_out_the_answer_in_the_unit_asked() -> None:
    result = _solve(_car(), CAR)
    assert result["solved"] and result["value"] == pytest.approx(3.4722, rel=1e-4)
    assert result["agrees"] is True


def test_a_negative_root_the_physics_rules_out_is_set_aside() -> None:
    result = _solve(_drop(), DROP)
    assert result["value"] == pytest.approx(3.0289, rel=1e-4)
    assert sorted(result["candidates"]) == pytest.approx([-3.0289, 3.0289], rel=1e-4)


def test_a_count_in_words_and_a_current_named_i_in_spanish() -> None:
    setup = {
        "givens": [
            {"symbol": "n", "value": "2", "unit": "", "quote": "Dos resistencias"},
            {"symbol": "R", "value": "10", "unit": "ohm", "quote": "10 ohmios"},
            {"symbol": "V", "value": "5", "unit": "V", "quote": "5 V"},
        ],
        "unknowns": [{"symbol": "Req", "unit": "ohm"}, {"symbol": "I", "unit": "A"}],
        "equations": ["Req = R/n", "V = I*Req"],
        "target": "I",
        "target_unit": "A",
        "answer": 1.0,
    }
    assert _solve(setup, PARALLEL_ES)["value"] == pytest.approx(1.0)


def test_degrees_latex_names_and_an_undeclared_step() -> None:
    setup = {
        "givens": [
            {"symbol": "v", "value": "20", "unit": "m/s", "quote": "20 m/s"},
            {"symbol": "\\theta", "value": "30", "unit": "degree", "quote": "30°"},
            _g(),
        ],
        "unknowns": [{"symbol": "R", "unit": "m"}],
        "equations": ["v_y = v*sin(\\theta)", "R = 2*v*cos(\\theta)*v_y/g"],
        "target": "R",
        "target_unit": "m",
        "answer": 35.3,
    }
    assert _solve(setup, THROW)["value"] == pytest.approx(35.31, rel=1e-3)


def test_a_side_written_as_zero_is_any_kind() -> None:
    setup = _drop(equations=["0 = h - g*t**2/2"])
    assert _solve(setup, DROP)["solved"]


@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        # A number the question never gave, even under words that are in it.
        (
            _drop(givens=[{"symbol": "h", "value": "50", "unit": "m", "quote": "45 m"}, _g()]),
            "h is not in the question",
        ),
        # Words that are not in the question.
        (
            _drop(givens=[{"symbol": "h", "value": "45", "unit": "m", "quote": "45 metres"}, _g()]),
            "h is not in the question",
        ),
        # A "constant" that is no standard value.
        (
            _drop(givens=[{"symbol": "h", "value": "45", "unit": "m", "quote": "45 m"}, _g("7")]),
            "constant g is no standard value",
        ),
        # A value written into an equation instead of given.
        (_drop(equations=["50 = g*t**2/2"]), "equation: a value written into an equation"),
        # Kinds that do not match: metres against metres per second.
        (_drop(equations=["h = g*t/2"]), "units of an equation"),
        # Not arithmetic: nothing is executed.
        (_drop(equations=["__import__('os').system('id') = t"]), "equation:"),
        (_drop(equations=["h = g.__class__ * t"]), "equation:"),
        # A setup that asks nothing.
        (_drop(target=""), "no setup"),
        (_drop(solvable=False), "no setup"),
    ],
)
def test_a_setup_that_does_not_hold_is_refused(setup: dict[str, Any], reason: str) -> None:
    result = _solve(setup, DROP)
    assert not result["solved"]
    assert result["reason"].startswith(reason)


def test_two_answers_the_setup_cannot_tell_apart_are_settled_by_the_model_s_own() -> None:
    question = "A number squared is 49 metres squared. What lengths could it be? Take x = 7 m."
    setup = {
        "givens": [{"symbol": "A", "value": "49", "unit": "m^2", "quote": "49 metres"}],
        "unknowns": [{"symbol": "x", "unit": "m"}],
        "equations": ["x**2 = A"],
        "target": "x",
        "target_unit": "m",
        "answer": 7,
    }
    assert _solve(setup, question)["value"] == pytest.approx(7)


@pytest.mark.parametrize(
    ("text", "number"),
    [("1,200", 1200), ("2,5", 2.5), ("3e8", 3e8), ("3×10^8", 3e8), ("−4", -4), ("0.5", 0.5)],
)
def test_numbers_as_people_write_them(text: str, number: float) -> None:
    assert parse_number(text) == pytest.approx(number)


@pytest.mark.parametrize(
    ("value", "quote", "question", "held"),
    [
        (100, "100 km/h", CAR, True),
        (100, "100  KM/H", CAR, True),  # spacing and case
        (2, "Dos resistencias", PARALLEL_ES, True),  # a count in words
        (20, "Dos resistencias", PARALLEL_ES, False),  # not a small count
        (100, "100 km/h", "my car goes from 0 to 90 km/h", False),
    ],
)
def test_a_given_is_held_to_the_question_s_words(
    value: float, quote: str, question: str, held: bool
) -> None:
    assert grounded(value, quote, question) is held


@pytest.mark.asyncio
@pytest.mark.parametrize("gate", [AsyncMock(return_value=True), AsyncMock(side_effect=OSError)])
async def test_no_setup_read_past_the_spend_cap_or_in_an_outage(gate: AsyncMock) -> None:
    from app.core.config import Settings
    from app.modules.physics.formal_read import read_physics_setup

    with (
        patch("app.core.redis.get_redis_client", MagicMock()),
        patch("app.services.quota.global_spend_exceeded", gate),
        patch("app.gateways.structured_completion.complete_structured", AsyncMock()) as call,
    ):
        assert await read_physics_setup(Settings(_env_file=None), CAR) is None  # type: ignore[call-arg]
    call.assert_not_awaited()


def test_a_temperature_asked_in_celsius_is_converted_not_scaled() -> None:
    """Review: degrees Celsius are an offset from kelvin, not a factor of it."""
    question = (
        "Water at 20 °C gains 4186 J per kg per degree and is heated by 25 °C. Final temperature?"
    )
    setup = {
        "givens": [
            {"symbol": "T1", "value": "20", "unit": "degC", "quote": "20 °C"},
            {"symbol": "dT", "value": "25", "unit": "delta_degC", "quote": "25 °C"},
        ],
        "unknowns": [{"symbol": "T2", "unit": "K"}],
        "equations": ["T2 = T1 + dT"],
        "target": "T2",
        "target_unit": "degC",
        "answer": 45,
    }
    result = _solve(setup, question)
    assert result["solved"] and result["value"] == pytest.approx(45.0)

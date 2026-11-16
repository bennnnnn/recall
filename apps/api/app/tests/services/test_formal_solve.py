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


UNIFORM = "A car accelerates uniformly from rest. How far does it go?"


@pytest.mark.parametrize(
    ("value", "quote", "question", "count", "held"),
    [
        (100, "100 km/h", CAR, False, True),
        (100, "100  KM/H", CAR, False, True),  # spacing and case
        (2, "Dos resistencias", PARALLEL_ES, True, True),  # a count in words
        (20, "Dos resistencias", PARALLEL_ES, True, False),  # not a small count
        (100, "100 km/h", "my car goes from 0 to 90 km/h", False, False),
        (0, "from rest", UNIFORM, False, True),  # a state's zero, any unit
        (5, "car", UNIFORM, False, False),  # a time from words that say no number
        (5, "uniformly", UNIFORM, False, False),
        (2, "Dos resistencias", PARALLEL_ES, False, False),  # words count, never measure
    ],
)
def test_a_given_is_held_to_the_question_s_words(
    value: float, quote: str, question: str, count: bool, held: bool
) -> None:
    assert grounded(value, quote, question, count=count) is held


def test_an_invented_time_from_words_with_no_number_is_refused() -> None:
    setup = {
        "givens": [
            {"symbol": "u", "value": "0", "unit": "m/s", "quote": "from rest"},
            {"symbol": "a", "value": "2", "unit": "m/s^2", "quote": "car"},
            {"symbol": "t", "value": "5", "unit": "s", "quote": "uniformly"},
        ],
        "unknowns": [{"symbol": "d", "unit": "m"}],
        "equations": ["d = u*t + a*t**2/2"],
        "target": "d",
        "target_unit": "m",
        "answer": 25,
    }
    assert _solve(setup, UNIFORM)["reason"] == "a is not in the question"


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


async def _in_process(fn: Any, *args: Any, **_kwargs: Any) -> Any:
    return fn(*args)


@pytest.mark.asyncio
@pytest.mark.parametrize(("own", "kept"), [(3.47, True), (4.5, False), (None, False)])
async def test_the_server_s_answer_is_used_only_when_the_setup_s_own_agrees(
    own: float | None, kept: bool
) -> None:
    """A setup whose own answer is another than the server's is no answer: the reply stands."""
    from app.core.config import Settings
    from app.modules.physics import formal_read
    from app.services.formal.problem import FormalProblem

    setup = FormalProblem.model_validate(_car(answer=own))
    with (
        patch.object(formal_read, "read_physics_setup", AsyncMock(return_value=setup)),
        patch("app.core.sympy_executor.run_sympy", _in_process),
    ):
        answer = await formal_read.formal_answer(CAR, Settings(_env_file=None))  # type: ignore[call-arg]
    assert (answer is not None) is kept
    if answer is not None:
        assert answer.value == pytest.approx(3.4722, rel=1e-4) and answer.unit == "m/s^2"


MIXING = "2 kg of water at 80 C is mixed with 3 kg of water at 20 C. What is the final temperature?"
PULLEY = "A pulley lifts a 900 N load 2 m when an effort of 250 N pulls the rope 8 m. Efficiency?"


def _mixing(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "givens": [
            {"symbol": "m1", "value": "2", "unit": "kg", "quote": "2 kg"},
            {"symbol": "T1", "value": "80", "unit": "degC", "quote": "80 C"},
            {"symbol": "m2", "value": "3", "unit": "kg", "quote": "3 kg"},
            {"symbol": "T2", "value": "20", "unit": "degC", "quote": "20 C"},
            c,
        ],
        "unknowns": [{"symbol": "Tf", "unit": "degC"}],
        "equations": ["m1*c*(T1 - Tf) = m2*c*(Tf - T2)"],
        "target": "Tf",
        "target_unit": "degC",
        "answer": 44,
    }


def test_a_standard_constant_named_with_no_value_takes_the_table_s() -> None:
    """Water's specific heat, the only constant of its kind, named but not valued."""
    c = {"symbol": "c", "value": "", "unit": "J/(kg*K)", "constant": True}
    result = _solve(_mixing(c), MIXING)
    assert result["solved"] and result["agrees"] and result["value"] == pytest.approx(44)


@pytest.mark.parametrize(
    "c",
    [
        {"symbol": "c", "value": "", "unit": "m/s", "constant": True},
        {"symbol": "c", "value": "", "unit": "kg", "constant": True},
        {"symbol": "c", "value": "", "unit": "J/(kg*K)", "constant": False, "quote": "x"},
    ],
    ids=["a-speed-light-s-or-sound-s", "a-mass-of-five", "not-a-constant"],
)
def test_a_constant_with_no_value_and_more_than_one_of_its_kind_is_refused(
    c: dict[str, Any],
) -> None:
    assert _solve(_mixing(c), MIXING)["reason"] == "value of c"


def test_a_percentage_is_the_ratio_in_the_unit_asked() -> None:
    setup = {
        "givens": [
            {"symbol": "L", "value": "900", "unit": "N", "quote": "900 N"},
            {"symbol": "dl", "value": "2", "unit": "m", "quote": "2 m"},
            {"symbol": "E", "value": "250", "unit": "N", "quote": "250 N"},
            {"symbol": "de", "value": "8", "unit": "m", "quote": "8 m"},
        ],
        "unknowns": [{"symbol": "eta", "unit": "%"}],
        "equations": ["eta = L*dl/(E*de)"],
        "target": "eta",
        "target_unit": "%",
        "answer": 90,
    }
    result = _solve(setup, PULLEY)
    assert result["solved"] and result["agrees"]
    assert (result["value"], result["unit"]) == (pytest.approx(90), "%")
    times_100 = setup | {"equations": ["eta = L*dl/(E*de)*100"]}
    assert not _solve(times_100, PULLEY)["solved"]


HEATER = "A 1000 W heater warms 2 kg of water by 30 C. How long? The specific heat is 4200 J/kg C."


@pytest.mark.parametrize("unit", ["J/kg*degC", "J/kg*K", "J/(kg*K)", "J/(kg*delta_degC)"])
def test_a_unit_after_a_slash_is_all_denominator(unit: str) -> None:
    """A science book's J/kg*K is per kilogram per kelvin, never (J/kg)*K (the heater's time
    was refused for its units)."""
    setup = {
        "givens": [
            {"symbol": "P", "value": "1000", "unit": "W", "quote": "1000 W"},
            {"symbol": "m", "value": "2", "unit": "kg", "quote": "2 kg"},
            {"symbol": "dT", "value": "30", "unit": "delta_degC", "quote": "30 C"},
            {"symbol": "c", "value": "4200", "unit": unit, "quote": "4200 J/kg C"},
        ],
        "unknowns": [{"symbol": "t", "unit": "s"}],
        "equations": ["P*t = m*c*dT"],
        "target": "t",
        "target_unit": "s",
        "answer": 252,
    }
    result = _solve(setup, HEATER)
    assert result["solved"] and result["value"] == pytest.approx(252)

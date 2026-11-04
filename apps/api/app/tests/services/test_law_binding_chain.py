"""The shared chain answers every ask by a law, one law after another, or none.

A toy motion subject drives the engine directly, so nothing here depends on physics: its
own units, its own laws, its own solver. Laws that declare the same variable share it, as
SUVAT's do; one that only reuses the name does not.
"""

from __future__ import annotations

import pytest

from app.services.law_binding.chain import Asked, Step, chain
from app.services.law_binding.fit import Fit, Subject, read_question
from app.services.law_binding.spec import Binding, FormulaSpec, VariableSpec, var
from app.services.law_binding.units import UnitTable, dimension_of

_UNITS = UnitTable({"m": "meter", "s": "second", "m/s": "meter / second"}, {})
_MOTION = Subject(units=_UNITS, fallback=lambda *_: None, unit_of=lambda _variable: "")
_SPEED = "meter / second"
_ACCELERATION = "meter / second ** 2"
_U = var("u", "u", _SPEED, words=("from",))
_V = var("v", "v", _SPEED, words=("to", "reaches"))
_A = var("a", "a", _ACCELERATION)
_T = var("t", "t", "second")
_D = var("d", "d", "meter")


def _law(
    op: str,
    result: str,
    unit: str,
    asks: tuple[str, ...],
    inputs: set[str],
    *variables: VariableSpec,
) -> FormulaSpec:
    return FormulaSpec(
        id=op,
        kind="motion",
        law_name=op,
        result_symbol=result,
        variables=variables,
        binding=Binding(asks=asks, result=(unit,), inputs=(frozenset(inputs),)),
    )


_ACCEL = _law("accel", "a", _ACCELERATION, ("acceleration",), {"u", "v", "t"}, _U, _V, _T, _A)
_DIST = _law("dist", "d", "meter", ("distance",), {"u", "a", "t"}, _U, _A, _T, _D)
# The same distance from the mean speed: a second law named alike that agrees.
_MEAN = _law("mean", "d", "meter", ("distance",), {"u", "v", "t"}, _U, _V, _T, _D)
# A law that only reuses the name ``a`` for another quantity.
_OTHER_A = var("a", "a", _ACCELERATION)
_OTHER = _law("other", "d", "meter", ("distance",), {"u", "a", "t"}, _U, _OTHER_A, _T, _D)


def _solve(filled: Fit, _ask: Asked) -> tuple[float, str] | None:
    p = filled.params
    if filled.spec.id == "accel":
        return (p["v"] - p["u"]) / p["t"], "m/s^2"
    if filled.spec.id in {"dist", "other"}:
        return p["u"] * p["t"] + 0.5 * p["a"] * p["t"] ** 2, "m"
    if filled.spec.id == "mean":
        return (p["u"] + p["v"]) / 2 * p["t"], "m"
    if filled.spec.id == "wrong":
        return 1.0, "m"
    return None


def _run(
    text: str, asks: list[tuple[str, str]], laws: list[FormulaSpec]
) -> tuple[Step, ...] | None:
    question = read_question(text, asks[0][0], _UNITS, max_givens=8)
    assert question is not None

    def named(words: str) -> list[tuple[FormulaSpec, int]]:
        lower = words.lower()
        return [
            (law, 1) for law in laws if law.binding and any(a in lower for a in law.binding.asks)
        ]

    return chain(
        question,
        [Asked(words, dimension_of(unit) or "") for words, unit in asks],
        _MOTION,
        named=named,
        of_kind=lambda kind: [law for law in laws if law.kind == kind],
        solve=_solve,
    )


_TEXT = "A cart goes from 10 m/s to 20 m/s in 5 s."


def _answered(steps: tuple[Step, ...] | None) -> list[tuple[str, float, int | None]]:
    assert steps is not None
    return [(step.fit.spec.id, round(step.value, 6), step.answers) for step in steps]


def test_one_ask_is_one_law() -> None:
    steps = _run(f"{_TEXT} Find the acceleration.", [("acceleration", _ACCELERATION)], [_ACCEL])
    assert _answered(steps) == [("accel", 2.0, 0)]


def test_a_law_lacking_one_input_has_it_worked_out_first() -> None:
    steps = _run(f"{_TEXT} Find the distance.", [("distance", "meter")], [_ACCEL, _DIST])
    # The acceleration is worked out for the distance, and answers no ask itself.
    assert _answered(steps) == [("accel", 2.0, None), ("dist", 75.0, 0)]


def test_every_ask_is_answered_in_turn_and_reuses_what_came_before() -> None:
    steps = _run(
        f"{_TEXT} Find the acceleration and the distance.",
        [("acceleration and the ", _ACCELERATION), ("distance", "meter")],
        [_ACCEL, _DIST],
    )
    assert _answered(steps) == [("accel", 2.0, 0), ("dist", 75.0, 1)]


def test_two_laws_named_alike_answer_when_they_agree() -> None:
    steps = _run(f"{_TEXT} Find the distance.", [("distance", "meter")], [_MEAN, _ACCEL, _DIST])
    assert _answered(steps)[-1][1:] == (75.0, 0)


def test_two_laws_named_alike_that_disagree_decline() -> None:
    wrong = _law("wrong", "d", "meter", ("distance",), {"u", "v", "t"}, _U, _V, _T, _D)
    assert _run(f"{_TEXT} Find the distance.", [("distance", "meter")], [_MEAN, wrong]) is None


def test_a_value_carries_only_to_a_law_that_declares_that_variable() -> None:
    # ``other`` calls an input "a" too, but it is not the acceleration ``accel`` gives.
    assert (
        _run(
            f"{_TEXT} Find the acceleration and the distance.",
            [("acceleration and the ", _ACCELERATION), ("distance", "meter")],
            [_ACCEL, _OTHER],
        )
        is None
    )


@pytest.mark.parametrize(
    "asks",
    [
        [],
        [("distance", "meter")] * 5,
    ],
)
def test_no_ask_or_too_many_decline(asks: list[tuple[str, str]]) -> None:
    question = read_question(f"{_TEXT} distance", "distance", _UNITS, max_givens=8)
    assert question is not None
    steps = chain(
        question,
        [Asked(words, dimension_of(unit) or "") for words, unit in asks],
        _MOTION,
        named=lambda _words: [(_MEAN, 1)],
        of_kind=lambda _kind: [],
        solve=_solve,
    )
    assert steps is None


def test_an_ask_no_law_answers_declines_the_whole_chain() -> None:
    steps = _run(
        f"{_TEXT} Find the acceleration and the distance.",
        [("acceleration and the ", _ACCELERATION), ("distance", "meter")],
        [_ACCEL],
    )
    assert steps is None

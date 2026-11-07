"""A trig equation in an interval is worked: one side zero, an identity, factor, each factor.

2026-11-06: "solve sin(2x) = cos(x) for 0 <= x < 2pi" showed only its solutions, and
``2 sin^2 x - sin x - 1 = 0`` on ``[0, 2pi)`` was certified as ``pi/2`` alone: SymPy's
interval solve drops roots its real solve finds.
"""

from __future__ import annotations

import pytest
from sympy import FiniteSet, Interval, Max, Rational, Symbol, cos, pi, sign, sin

from app.core.config import Settings
from app.modules.math.tools.school.trig_equation_steps import (
    SolveRange,
    identity_factor_steps,
    solutions_in,
)
from app.services.subjects.dispatch import build_subject_augmentation, maybe_direct_subject_reply

x = Symbol("x", real=True)
TURN = Interval.Ropen(0, 2 * pi)


async def _reply(text: str) -> tuple[str | None, str | None]:
    settings = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
    augmentation = await build_subject_augmentation(text, settings)
    verified = augmentation.verified
    answer = getattr(verified, "canonical_answer", None) if verified is not None else None
    return answer, maybe_direct_subject_reply(verified, text)


def _radians(values: list[object]) -> str:
    from sympy import latex

    return "= " + r",\;".join(latex(value) for value in values)


@pytest.mark.parametrize(
    ("expr", "roots"),
    [
        (2 * sin(x) ** 2 - sin(x) - 1, {pi / 2, 7 * pi / 6, 11 * pi / 6}),
        (2 * sin(x) ** 2 + sin(x) - 1, {pi / 6, 5 * pi / 6, 3 * pi / 2}),
        (2 * cos(x) ** 2 - cos(x) - 1, {0, 2 * pi / 3, 4 * pi / 3}),
        (sin(2 * x) - cos(x), {pi / 6, pi / 2, 5 * pi / 6, 3 * pi / 2}),
    ],
)
def test_solutions_in_finds_every_root_in_the_interval(expr: object, roots: set[object]) -> None:
    assert solutions_in(expr, x, TURN) == FiniteSet(*roots)


def test_solutions_in_declines_an_interval_of_solutions() -> None:
    assert solutions_in(sin(x) ** 2 + cos(x) ** 2 - 1, x, TURN) is None


@pytest.mark.parametrize(
    "expr",
    [
        # SymPy raises on both: never "no solution" built from the failures.
        Max(sin(x), cos(x)) - Rational(1, 2),
        sign(sin(x)) - 1,
    ],
)
def test_solutions_in_declines_when_no_solve_finished(expr: object) -> None:
    assert solutions_in(expr, x, TURN) is None


def test_no_root_anywhere_is_no_solution() -> None:
    """Both solves finish empty: "no solution", as main answered (review of #2319)."""
    assert solutions_in(sin(x) - 2, x, TURN) == FiniteSet()


def test_one_factor_with_no_root_in_the_interval_says_so() -> None:
    assert solutions_in(sin(x) - 2, x, TURN, empty_allowed=True) == FiniteSet()


def _steps(lhs: object, rhs: object) -> tuple[str, ...] | None:
    solved = solutions_in(lhs - rhs, x, TURN)  # type: ignore[operator]
    return identity_factor_steps(lhs, rhs, SolveRange(x, TURN, _radians, False), solved)


def test_double_angle_then_factor_then_each_factor() -> None:
    steps = _steps(sin(2 * x), cos(x))
    assert steps is not None
    shown = "\n".join(steps)
    assert "move every term to one side" in steps[0]
    assert (
        r"use $\sin{\left(2 x \right)} = 2 \sin{\left(x \right)} \cos{\left(x \right)}$" in steps[1]
    )
    assert "factor" in steps[2]
    assert r"\cos{\left(x \right)} = 0 \Rightarrow x = \frac{\pi}{2},\;\frac{3 \pi}{2}" in shown
    assert (
        r"\sin{\left(x \right)} = \frac{1}{2} \Rightarrow x = \frac{\pi}{6},\;\frac{5 \pi}{6}"
        in (shown)
    )


def test_cos_double_angle_is_written_in_the_other_function() -> None:
    steps = _steps(cos(2 * x), sin(x))
    assert steps is not None
    assert r"\cos{\left(2 x \right)} = 1 - 2 \sin^{2}{\left(x \right)}" in steps[1]


def test_a_pythagorean_square_is_replaced() -> None:
    steps = _steps(2 * cos(x) ** 2 + 3 * sin(x) - 3, 0)
    assert steps is not None
    assert r"\cos^{2}{\left(x \right)} = 1 - \sin^{2}{\left(x \right)}" in steps[0]


def test_a_multiple_angle_runs_over_its_own_interval() -> None:
    steps = _steps(cos(2 * x), Rational(1, 2))
    assert steps is not None
    assert r"0 \le 2 x < 4 \pi" in steps[-1]


def test_the_function_alone_equal_to_a_value_has_nothing_to_work() -> None:
    assert _steps(sin(x), Rational(1, 2)) is None


def test_a_wrong_solution_set_leaves_the_working_out() -> None:
    steps = identity_factor_steps(
        sin(2 * x), cos(x), SolveRange(x, TURN, _radians, False), FiniteSet(pi / 6)
    )
    assert steps is None


@pytest.mark.asyncio
async def test_the_reported_question_shows_its_working() -> None:
    answer, reply = await _reply("solve sin(2x) = cos(x) for 0 <= x < 2pi")
    assert answer == r"x = \frac{\pi}{6},\;\frac{\pi}{2},\;\frac{5 \pi}{6},\;\frac{3 \pi}{2}"
    assert reply is not None
    assert "— factor" in reply
    assert r"2 \sin{\left(x \right)} - 1 = 0 \Rightarrow" in reply


@pytest.mark.asyncio
async def test_a_quadratic_in_sine_keeps_every_root() -> None:
    answer, _ = await _reply("solve 2sin^2(x) - sin(x) - 1 = 0 for 0 <= x < 2pi")
    assert answer == r"x = \frac{\pi}{2},\;\frac{7 \pi}{6},\;\frac{11 \pi}{6}"


@pytest.mark.asyncio
async def test_degrees_show_each_factor_in_degrees() -> None:
    _, reply = await _reply("solve sin(2x) = sin(x) for 0 <= x <= 360 degrees")
    assert reply is not None
    assert r"\sin{\left(x \right)} = 0 \Rightarrow x = 0^\circ,\;180^\circ,\;360^\circ" in reply

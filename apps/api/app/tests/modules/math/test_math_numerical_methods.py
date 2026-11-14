"""A numerical method the question names is worked as asked, or the turn gets no card.

2026-11-13 audit (MATH-01): "use the trapezoidal rule with n = 4 to approximate the integral
of x^2 from 0 to 2" came back a checked 8/3, the exact integral, and finalize wrote "The
verified answer is 8/3" under a model's correct 2.75. "Apply 1 Newton iteration to
x^2 - 10 = 0 from x = 3" came back the root √10 ≈ 3.16228, not x_1 = 19/6.
"""

from __future__ import annotations

import time

import pytest
from sympy import Rational, sympify

from app.core.config import Settings
from app.modules.math.match.numerical_methods import named_numerical_method
from app.modules.math.request_consumption import audit_math_request
from app.modules.math.schemas import MathIntent, is_declined
from app.modules.math.solve.approximation import euler_points, newton_iterates, rule_sum
from app.modules.math.subject import MathTool
from app.modules.math.tools.extract import extract_math_intent
from app.services.subjects.dispatch import build_subject_augmentation, maybe_direct_subject_reply


async def _reply(text: str) -> tuple[str | None, str | None]:
    """(canonical answer, direct reply) for one turn, with no model call."""
    settings = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
    augmentation = await build_subject_augmentation(text, settings)
    verified = augmentation.verified
    answer = getattr(verified, "canonical_answer", None) if verified is not None else None
    return answer, maybe_direct_subject_reply(verified, text)


@pytest.mark.parametrize(
    ("text", "rule", "count"),
    [
        ("use the trapezoidal rule with n = 4 to approximate the integral", "trapezoid", 4),
        ("the trapezium rule with 5 ordinates", "trapezoid", 4),
        ("Simpson's rule with 6 subintervals", "simpson", 6),
        ("the midpoint rule with n = 2", "midpoint", 2),
        ("a left Riemann sum with four rectangles", "left", 4),
        ("a right-endpoint approximation with 3 strips", "right", 3),
        ("apply 1 Newton iteration to x^2 - 10 = 0 from x = 3", "newton", 1),
        ("two iterations of Newton's method", "newton", 2),
        ("Newton's method with x1 = 2 to find x3", "newton", 2),
        ("Newton's method from x_0 = 1: find the second approximation", "newton", 2),
        ("use Newton's method to solve x^2 - 5 = 0 starting at 3", "newton", None),
        ("Euler's method with h = 0.1", "euler", None),
        # Named, and worked by no solver here: the reading declines.
        ("a Riemann sum with 4 rectangles", "unworked", None),
        ("the improved Euler method with h = 0.1", "unworked", None),
        ("a lower sum with 4 rectangles", "unworked", None),
    ],
)
def test_a_named_method_and_its_count_are_read(text: str, rule: str, count: int | None) -> None:
    named = named_numerical_method(text)
    assert named is not None
    assert (named.rule, named.count) == (rule, count)


@pytest.mark.parametrize(
    "text",
    [
        "find the area of a trapezoid with bases 3 and 5 and height 4",
        "find the midpoint of (1, 2) and (3, 4)",
        "a force of 10 newtons acts on a 2 kg mass",
        "state Newton's second law",
        "integrate x^2 from 0 to 2",
        "the left side of the equation 2x + 3 = 7",
    ],
)
def test_no_method_is_read_into_a_look_alike(text: str) -> None:
    assert named_numerical_method(text) is None


@pytest.mark.parametrize(
    ("rule", "n", "expr", "low", "high", "total"),
    [
        ("trapezoid", 4, "x^2", "0", "2", Rational(11, 4)),
        ("midpoint", 2, "x^2", "0", "2", Rational(5, 2)),
        ("simpson", 4, "x^3", "0", "2", 4),
        ("left", 4, "x^2", "0", "2", Rational(7, 4)),
        ("right", 4, "x^2", "0", "2", Rational(15, 4)),
        ("trapezoid", 2, "1/x", "1", "2", Rational(17, 24)),
    ],
)
def test_a_rule_of_integration_is_its_own_sum(
    rule: str, n: int, expr: str, low: str, high: str, total: object
) -> None:
    assert rule_sum(expr, "x", low, high, n, rule).total == total


def test_newton_and_euler_are_worked_step_by_step() -> None:
    assert newton_iterates("x^2 - 5", "x", "3", 1) == (3, Rational(7, 3))
    assert newton_iterates("x^2 - 10", "x", "3", 1) == (3, Rational(19, 6))
    assert [y for _x, y in euler_points("y", "0", "1", "0.1", 2)] == [
        1,
        Rational(11, 10),
        Rational(121, 100),
    ]


@pytest.mark.parametrize(
    ("text", "value"),
    [
        (
            "use the trapezoidal rule with n = 4 to approximate the integral of x^2 from 0 to 2",
            2.75,
        ),
        ("use the midpoint rule with n = 2 to approximate the integral of x^2 from 0 to 2", 2.5),
        ("use Simpson's rule with n = 4 to approximate the integral of x^3 from 0 to 2", 4),
        (
            "approximate the integral of x^2 from 0 to 2 using a left Riemann sum with 4 "
            "subintervals",
            1.75,
        ),
        ("estimate the integral from 1 to 2 of 1/x dx using the midpoint rule with n = 4", 0.69122),
        ("use one iteration of Newton's method on x^2 - 5 = 0 starting at x0 = 3", 2.33333),
        ("apply 1 Newton iteration to x^2 - 10 = 0 from x = 3", 3.16667),
        ("Use Newton's method with x1 = 2 to find x3 for x^3 - 2x - 5 = 0", 2.09457),
        ("use Euler's method with h = 0.1 to approximate y(0.2) for y' = x + y, y(0) = 1", 1.22),
    ],
)
async def test_the_turn_answers_the_method_asked(text: str, value: float) -> None:
    answer, direct = await _reply(text)
    assert answer is not None
    shown = answer.replace(r"\approx", "=").split("=")[-1]
    assert float(sympify(shown.strip())) == pytest.approx(value, abs=1e-5)
    assert direct is not None and "**Substitution**" in direct


@pytest.mark.parametrize(
    "text",
    [
        # No count: the rule cannot be worked, and the integral is not what was asked.
        "use the trapezoidal rule to approximate the integral of x^2 from 0 to 2",
        "approximate the integral of x^2 from 0 to 2 with a Riemann sum with 4 rectangles",
        "use the improved Euler method with h = 0.1 for y' = y, y(0) = 1 to find y(0.2)",
        # A count with no start.
        "do two Newton steps on x^3 - 2 = 0",
    ],
)
async def test_a_method_that_cannot_be_worked_gets_no_card(text: str) -> None:
    answer, _direct = await _reply(text)
    assert answer is None
    assert is_declined(extract_math_intent(text))


async def test_newton_without_a_count_still_runs_to_its_root() -> None:
    answer, _direct = await _reply("use Newton's method to solve x^2 - 5 = 0 starting at 3")
    assert answer == "2.23607"


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        (
            "use the trapezoidal rule with n = 4 to approximate the integral of x^2 from 0 to 2",
            MathIntent(
                kind="calculus",
                operation="integrate",
                expr="x^2",
                integral_lower="0",
                integral_upper="2",
            ),
        ),
        (
            "apply 1 Newton iteration to x^2 - 10 = 0 from x = 3",
            MathIntent(kind="numerical_method", operation="newton", expr="x^2-10", newton_guess=3),
        ),
        (
            "apply 1 Newton iteration to x^2 - 10 = 0 from x = 3",
            MathIntent(kind="equation", lhs="x^2 - 10", rhs="0"),
        ),
    ],
)
def test_a_reading_without_the_named_method_is_incomplete(text: str, intent: MathIntent) -> None:
    """Any reader that answers the method's question in its place leaves it unconsumed."""
    audit = audit_math_request(text, intent)
    assert not audit.complete
    assert "a numerical method or count the reading does not carry" in audit.leftovers


def test_a_model_tool_call_on_an_unworked_method_is_not_certified() -> None:
    """The model's own integrate call answers the integral, not the rule asked."""
    text = "use the trapezoidal rule to approximate the integral of x^2 from 0 to 2"
    args = {"action": "integrate", "expr": "x^2", "lower": "0", "upper": "2"}
    assert MathTool().call_matches(args, [text]) is None
    assert MathTool().call_matches(args, ["integrate x^2 from 0 to 2"]) is not None


@pytest.mark.wall_clock
@pytest.mark.parametrize(
    "text",
    [
        "left" + " " * 1990 + "x",
        "newton's method starting at" + " " * 1970,
        "newton's method " + "x_1 " * 490,
        "simpson" + " -" * 990,
        "trapezoidal rule " + "with n = 4 " * 170,
    ],
)
def test_the_method_reader_stays_linear_on_a_long_run(text: str) -> None:
    from app.modules.math.match.numerical_methods import without_named_method, without_start

    started = time.perf_counter()
    named_numerical_method(text)
    without_named_method(text)
    without_start(text)
    assert time.perf_counter() - started < 0.2

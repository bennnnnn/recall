"""The checked card holds the quantity the question asks, or there is none (2026-11-14 review).

An independent review of the derivative readers found new checked cards no question asked:
a constant or a substitution taken as the function ("x^n where n = 4" was 0), the first
derivative for y'' of a curve, a differential equation's stated rate read as a derivative
asked, a derivative that is one term of a larger expression ("f'(3) - f(3)" was 6), and
one of two orders asked. Words that name no operation (a speed limit, a stated
derivative) kept solve cards from their questions. Each class is held here through the
turn's real reading and solve, with the card the textbook gives or none.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sympy import Symbol
from sympy.parsing.sympy_parser import parse_expr

from app.core.config import Settings
from app.modules.math import solve as math_solve
from app.modules.math.match.asked_operations import call_answers_reading, call_computes_the_ask
from app.modules.math.schemas import MathIntent
from app.modules.math.subject import MathTool
from app.services.subjects.dispatch import build_subject_augmentation
from app.tests.behavior.stem_math_judge import close, pieces

_SETTINGS = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
_NAMES = {"x": Symbol("x"), "y": Symbol("y"), "t": Symbol("t")}


async def _card(text: str) -> str | None:
    verified = (await build_subject_augmentation(text, _SETTINGS)).verified
    if verified is None:
        return None
    return getattr(verified, "display_answer", None) or verified.canonical_answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        # A constant or a substitution given beside the function (4x^3, 6x, 10x, 3e^(3x),
        # 2x, 4 cos x, 3x^2 - 2, 24x, 10(x + 1) were asked).
        "Differentiate x^n where n = 4",
        "Differentiate kx^2 where k = 3",
        "Find the derivative of ax^2 where a = 5",
        "Differentiate e^(ax) where a = 3",
        "Find the derivative of x^2 + c where c = 7",
        "Find the derivative of A sin x where A = 4",
        "Differentiate x^3 - px, given p = 2",
        "Differentiate 3t^2 where t = 2x",
        "Find the derivative of 5u^2 where u = x + 1",
        # y'' of a curve, which one implicit differentiation does not reach.
        "Find y'' if x^2 + y^2 = 25",
        "Given xy = 1, find y''",
        "Find y'' for 2x + 3y = 6",
        "Find y'' if y^2 = 4x",
        "Find y''' for x + y^2 = 1",
        "x^2 + y^2 = 16. Find y'' in terms of x and y",
        "Find dy/dx and d^2y/dx^2 if x^2 + y^2 = 25",
        # A rate stated, not asked: a differential equation (y = x^2 + 5).
        "The rate of change of y with respect to x is 2x and y = 5 when x = 0. Find y.",
        "If the rate of change of y with respect to x is 3 and y = 2 when x = 0, find y",
        # A derivative as one term of more (-3, 4/5, 66, 2x^2, 4x^3, x^2 - 2x - 4, 6, 13,
        # 0, 0, x + 1 were asked), or one of two asks.
        "Given f(x) = x^2, find f'(3) - f(3)",
        "If f(x) = x^2 + 1, evaluate f'(2)/f(2)",
        "Let f(x) = x^3 - x. Find f(2)f'(2)",
        "If y = x^2, find x(dy/dx)",
        "If y = x^4, find 2 dy/dx",
        "Given f(x) = x^2 - 4x, find f'(x) + f(x)",
        "If f(x) = x^3, find 2f'(1)",
        "If f(x) = 3x^2, find f'(2) + 1",
        "If y = e^(2x), find y'' - 4y",
        "If y = sin x, find y'' + y",
        "If f(x) = x^2 + 2x, find f'(x)/2",
        "If y = 3x^2 + 2x, find the value of dy/dx and of y when x = 1",
        # Two orders asked, one read.
        "Find f'(x) and f''(x) for f(x) = x^3",
        "Find y' and y'' for y = sin x",
        "Given y = x^2, find the derivative and the second derivative",
        # A study of a function: no one value answers it (round 3, c009-c037).
        "Let f(x) = 4|x² − 1|/(x − 1) if x ≠ 1 and f(1) = 5. Find the largest interval(s) on "
        "which f is continuous, and show the function on a graph.",
        "For f(x) = (x² − 2x + 4)/(x − 2) find the critical numbers, local extreme values, "
        "intervals of monotonicity, intervals of concavity and inflection points, and sketch "
        "the graph with its asymptotes.",
        "Find the local maximum and minimum values of f(x) = (x² − 4)^(2/3) and sketch the "
        "graph, including where it is concave up or down.",
        # A derivative given by its value, not asked (Unit 5, u5-001: the card was 2).
        "Check that f(x) = x² + 3x + 1, g(x) = x² + 3x, h(x) = x² + 3x − 12 and k(x) = x² + 3x "
        "+ π all have the same derivative 2x + 3. Then draw the graphs of f, g, h and k "
        "together on the same axes. What does this tell you about ∫(2x + 3) dx?",
        "If the derivative is 2x - 4, where is the function increasing?",
        # Where or when, not how much; a rate of the formula given, not its value.
        "Find the x-coordinate of the local minimum of f(x) = x^3 - 3x",
        "A ball's height is h = 20t - 5t^2. When is the ball at its maximum height?",
        "Given s = 3t^2 + 4t, find the velocity at t = 2",
        "A car's velocity is v = 3t^2 - 2t. Find the acceleration when t = 2",
    ],
)
async def test_a_question_no_reading_answers_gets_no_card(text: str) -> None:
    assert await _card(text) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # A limit, an integral or a derivative the sentence does not ask is no limit asked.
        ("The speed limit is 65 mph. If 5x + 15 = 65, find x.", "10"),
        ("A lift has a weight limit of 800 kg. Solve 80n = 800.", "10"),
        ("There is a time limit of 60 minutes. If 4x + 20 = 60, find x.", "10"),
        ("My credit limit is $2000. Solve 400 + 200m = 2000.", "8"),
        ("The upper limit is 10. Solve 2x = 10.", "5"),
        ("Solve 3x - 7 = 11. There is no time limit.", "6"),
        ("The derivative of a function is 2x - 4. Solve 2x - 4 = 0.", "2"),
        # The derivative asked, in any wording, with its point.
        ("f(x) = x^3 - 2x^2 + 1. Find f'(2).", "4"),
        ("Find dy/dx at x = 2 for y = x^3 - 4x", "8"),
        ("s = 5t^2 + 2t, find ds/dt when t = 3", "32"),
        ("If x = 3y^2, find dx/dy", "6*y"),
        ("Find y'' when x = 1 for y = x^4", "12"),
        # At the point asked, a constant one included (main's cards: cos x, x = π, x = π/4).
        ("If f(x) = sin x, find f'(π/2)", "0"),
        ("Find f'(1/2) if f(x) = x^3", "3/4"),
        ("Find dy/dx at x = π for y = x sin x", "-pi"),
        ("Evaluate x² at x = π", "pi**2"),
        ("Evaluate sin x at x = π/4", "sqrt(2)/2"),
        # An order in plain digits (main solved y = x^4 for x).
        ("Find d3y/dx3 for y = x^4", "24*x"),
        ("Find d3s/dt3 for s = t^5", "60*t**2"),
    ],
)
async def test_the_card_asked_stays(text: str, answer: str) -> None:
    card = await _card(text)
    assert card is not None, text
    values = pieces(card)
    assert values and close(values[-1], parse_expr(answer, local_dict=_NAMES)), card


@pytest.mark.parametrize(
    ("intent", "args", "answers"),
    [
        # The server's own reading says what is asked: a curve's slope is its derivative.
        (
            MathIntent(kind="arithmetic", school_op="equation_slope", operation="solve"),
            {"action": "diff", "expr": "x**3 - 2*x"},
            True,
        ),
        (
            MathIntent(kind="equation", lhs="1000*1.05^t", rhs="2000", operation="solve"),
            {"action": "solve", "lhs": "1000*1.05**t", "rhs": "2000"},
            True,
        ),
        (
            MathIntent(kind="calculus", operation="differentiate", expr="x^4", derivative_order=2),
            {"action": "diff", "expr": "x**4", "order": 2},
            True,
        ),
        (
            MathIntent(kind="calculus", operation="differentiate", expr="x^4", derivative_order=2),
            {"action": "diff", "expr": "x**4"},
            False,
        ),
        # Its value at a point is asked; the tool differentiates at none.
        (
            MathIntent(
                kind="calculus", operation="differentiate", expr="x^2", evaluation_point="3"
            ),
            {"action": "diff", "expr": "x**2"},
            False,
        ),
        # A sketch, a curve's extreme values: no one operation is the answer.
        (
            MathIntent(kind="graph", operation="graph"),
            {"action": "simplify", "expr": "(2*x - 6)/(x**2 - 9)"},
            False,
        ),
        (
            MathIntent(kind="graph", operation="graph"),
            {"action": "graph", "expr": "(2*x - 6)/(x**2 - 9)"},
            True,
        ),
        # The value the user's numbers make, as any rewrite works it out.
        (
            MathIntent(kind="arithmetic", school_op="column_addition", operation="solve"),
            {"action": "simplify", "expr": "1200 + 800"},
            True,
        ),
        (
            MathIntent(kind="calculus", operation="critical_points", school_op="extreme_value"),
            {"action": "diff", "expr": "2*x - 3*x**(2/3)"},
            False,
        ),
    ],
)
def test_a_tool_call_answers_what_the_server_reads(
    intent: MathIntent, args: dict[str, Any], answers: bool
) -> None:
    assert call_answers_reading(args, intent) is answers


@pytest.mark.parametrize(
    ("text", "args", "matched"),
    [
        # Words that name no operation never refuse a solve.
        (
            "A population of 1000 is increasing at 5% a year. When does it reach 2000? "
            "Solve 1000(1.05)^t = 2000",
            {"action": "solve", "lhs": "1000*1.05**t", "rhs": "2000", "variable": "t"},
            True,
        ),
        (
            "The speed limit is 65 mph. If 5x + 15 = 65, find x.",
            {"action": "solve", "lhs": "5*x + 15", "rhs": "65"},
            True,
        ),
        (
            "Solve 2x + 4 = 30. The maximum is 30 seats.",
            {"action": "solve", "lhs": "2*x + 4", "rhs": "30"},
            True,
        ),
        (
            "Find the maximum value of x if 2x + 3 = 11",
            {"action": "solve", "lhs": "2*x + 3", "rhs": "11"},
            True,
        ),
        (
            "Find the slope of the curve y = x^3 - 2x",
            {"action": "diff", "expr": "x**3 - 2*x"},
            True,
        ),
        (
            "Find the gradient function of y = x^2 + 3x",
            {"action": "diff", "expr": "x**2 + 3*x"},
            True,
        ),
    ],
)
def test_a_tool_call_on_the_users_problem_stays_checked(
    text: str, args: dict[str, Any], matched: bool
) -> None:
    assert (MathTool().call_matches(json.dumps(args), [text]) is not None) is matched


@pytest.mark.parametrize(
    ("text", "args", "answers"),
    [
        # The function rewritten is no answer to where it is continuous.
        (
            "Let f(x) = 4|x² − 1|/(x − 1) if x ≠ 1 and f(1) = 5. Find the largest interval(s) "
            "on which f is continuous, and show the function on a graph.",
            {"action": "simplify", "expr": "4*Abs(x**2 - 1)/(x - 1)"},
            False,
        ),
        # One solve of a study's several features (its x-intercept) is no answer to it.
        (
            "Find the intervals in which f(x) = 2x³ − 3x² + 5 is strictly increasing or "
            "decreasing, then sketch the graph showing every extreme point, the inflection "
            "point and the x-intercept.",
            {"action": "solve", "lhs": "2*x**3 - 3*x**2 + 5", "rhs": "0"},
            False,
        ),
        ("Simplify (x^2 - 1)/(x - 1)", {"action": "simplify", "expr": "(x**2 - 1)/(x - 1)"}, True),
    ],
)
def test_a_model_computation_with_no_reading_answers_what_is_asked(
    text: str, args: dict[str, Any], answers: bool
) -> None:
    assert call_computes_the_ask(text, args) is answers


@pytest.mark.parametrize(
    ("integrand", "variable", "traced"),
    [
        # ln(2cos 2t - 2)/2 was the card: the log of a number never positive (Unit 5, u5-017).
        ("sin(2*t)/(1 - cos(2*t))", "t", True),
        ("sin(x)/(cos(x) - 1)", "x", True),
        ("1/(x - 3)", "x", True),
        ("-1/(1 - x)", "x", False),
    ],
)
def test_a_traced_antiderivative_is_real(integrand: str, variable: str, traced: bool) -> None:
    from app.modules.math.solve.antiderivative import differentiates_to
    from app.modules.math.solve.integral_steps import integral_trace

    steps, _problem, answer = integral_trace(integrand, variable)
    assert bool(steps) is traced, "the working is kept"
    card = answer or math_solve.integrate_expression(integrand, variable).latex
    assert "\\left|" in card, card
    result = math_solve.integrate_expression(integrand, variable)
    symbol = Symbol(variable, real=True)
    assert differentiates_to(
        parse_expr(result.result, local_dict={variable: symbol}),
        parse_expr(integrand, local_dict={variable: symbol}),
        symbol,
    )

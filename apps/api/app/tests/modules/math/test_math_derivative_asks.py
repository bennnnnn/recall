"""A derivative asked is read as a derivative, in any wording, and nothing else answers it.

"Find dy/dx if y = x^2 sin x" was read and "Find dy/dx for y = x ln x" was not: the reader
peeled only an "if" off the function, so "for", "when", "where", "given" and a function
stated first fell through to the equation solver, which solved y = x ln x for x and
certified x = e^{W(y)} as the derivative (2026-11-14, grade 12 book). The function is the
relation the message writes that defines it, wherever it stands; a solve reading never
answers a derivative, integral or limit asked.
"""

from __future__ import annotations

import pytest
from sympy import Symbol
from sympy.parsing.sympy_parser import parse_expr

from app.core.config import Settings
from app.modules.math import solve as math_solve
from app.modules.math import tools as math_tools
from app.modules.math.match.asked_operations import (
    AskedOperations,
    asked_operations,
    call_computes_the_ask,
    computes_the_ask,
    reading_computes_the_ask,
)
from app.modules.math.schemas import MathIntent, is_declined
from app.modules.math.tools.extract import extract_math_intent
from app.tests.behavior.stem_math_judge import close, pieces

X = Symbol("x")

_SOLVES = {"equation", "system", "inequality"}


@pytest.mark.parametrize(
    ("text", "function", "order", "point"),
    [
        ("Find dy/dx for y = (1 − ln x)/x²", "(1 - ln(x))/x**2", 1, None),
        ("Find dy/dx for y = (x² − 2x − 3)e^x", "(x**2 - 2*x - 3)*exp(x)", 1, None),
        ("Find dy/dx for y = x ln x", "x*ln(x)", 1, None),
        ("Find dy/dx when y = √(x² + 1)", "sqrt(x**2 + 1)", 1, None),
        ("Find dy/dx if y = x² sin x", "x**2*sin(x)", 1, None),
        ("Given y = x³ − 4x, find dy/dx", "x**3 - 4*x", 1, None),
        ("Find y' for y = ln(x² + 1)", "ln(x**2 + 1)", 1, None),
        ("If y = (x+1)/(x−1), find dy/dx", "(x + 1)/(x - 1)", 1, None),
        ("y = sin(3x)cos x. Find dy/dx.", "sin(3*x)*cos(x)", 1, None),
        ("Find dy/dx where y = e^(2x) sin x", "exp(2*x)*sin(x)", 1, None),
        ("For y = tan(2x), find dy/dx", "tan(2*x)", 1, None),
        ("What is dy/dx when y = x^2 e^x?", "x**2*exp(x)", 1, None),
        ("Determine dy/dx, given that y = (2x+1)^5", "(2*x + 1)**5", 1, None),
        ("Let y = x^3 cos x. Find dy/dx.", "x**3*cos(x)", 1, None),
        ("Find dy/dx given y = 3x^2 - 5x + 1", "3*x**2 - 5*x + 1", 1, None),
        ("Find dy/dx when y = 2x^3 - 5x", "2*x**3 - 5*x", 1, None),
        ("Find the rate of change of y with respect to x for y = x^3 + 2x", "x**3 + 2*x", 1, None),
        ("Find the derivative of y with respect to x, where y = x^2 ln x", "x**2*ln(x)", 1, None),
        ("Given f(x) = x^3 - 2x, find f'(x)", "x**3 - 2*x", 1, None),
        ("Find f'(x) for f(x) = sqrt(x) + 1/x", "sqrt(x) + 1/x", 1, None),
        ("Find d²y/dx² for y = cos²(2x + 1)", "cos(2*x + 1)**2", 2, None),
        ("Find y'' if y = x^4 - 3x^2", "x**4 - 3*x**2", 2, None),
        ("Find y″ if y = x^4 - 3x^2", "x**4 - 3*x**2", 2, None),
        ("Find f''(x) for f(x) = x^5", "x**5", 2, None),
        ("y = x^2 + 3x; find dy/dx at x = 2", "x**2 + 3*x", 1, "2"),
        ("Find dy/dx at x = 1 for y = x^3 - x", "x**3 - x", 1, "1"),
        ("Find dy/dx when x = 2 if y = x^3", "x**3", 1, "2"),
        ("Find f'(2) if f(x) = x^3 - 4x", "x**3 - 4*x", 1, "2"),
    ],
)
def test_a_derivative_ask_reads_its_function_in_any_wording(
    text: str, function: str, order: int, point: str | None
) -> None:
    intent = extract_math_intent(text)
    assert intent is not None
    assert (intent.kind, intent.operation) == ("calculus", "differentiate")
    assert intent.derivative_order == order
    assert intent.evaluation_point == point
    read = math_solve.parse_expression(intent.expr or "")
    assert math_solve.parse_expression(function).equals(read)


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("Find dy/dx for y = x ln x", "log(x) + 1"),
        ("Find dy/dx for y = (1 − ln x)/x²", "(2*log(x) - 3)/x**3"),
        ("Find d²y/dx² for y = cos²(2x + 1)", "-8*cos(4*x + 2)"),
        ("Find dy/dx at x = 1 for y = x^3 - x", "2"),
    ],
)
def test_the_card_is_the_derivative(text: str, answer: str) -> None:
    intent = extract_math_intent(text)
    assert intent is not None
    block = math_tools._build_verified_block(intent, Settings(math_tools_enabled=True))
    assert block is not None and block.canonical_answer is not None
    values = pieces(block.canonical_answer)
    assert len(values) == 1 and close(values[0], parse_expr(answer, local_dict={"x": X}))


@pytest.mark.parametrize(
    ("text", "relation"),
    [
        ("x² + y² = 25, find dy/dx", ("x^2 + y^2", "25")),
        ("Find dy/dx if x² + y² = 25", ("x^2 + y^2", "25")),
        ("Find dy/dx for x^2 + xy + y^2 = 7", ("x^2 + xy + y^2", "7")),
        ("Given x^3 + y^3 = 6xy, find dy/dx", ("x^3 + y^3", "6xy")),
        ("If xy = 4, find dy/dx", ("xy", "4")),
    ],
)
def test_a_relation_in_x_and_y_is_differentiated_implicitly(
    text: str, relation: tuple[str, str]
) -> None:
    intent = extract_math_intent(text)
    assert intent is not None
    assert (intent.operation, intent.school_op) == ("differentiate", "implicit")
    lhs, rhs = (math_solve.parse_expression(side) for side in relation)
    read = math_solve.parse_expression(intent.expr or "")
    assert read.equals(lhs - rhs)


@pytest.mark.parametrize(
    "text",
    [
        # Parametric: x and y each given by t (dy/dx = 3t/2, which no reader works).
        "If x = t^2 and y = t^3, find dy/dx",
        "Find dy/dx when x = 2t + 1 and y = t^2",
        "Given x = cos t, y = sin t, find dy/dx",
        # Through another function (dy/dx = 6(3x + 1)), or with a constant to put in.
        "Find dy/dx for y = u^2 where u = 3x + 1",
        "Find dy/dx for y = x^2 + kx, given k = 3",
        # Two points, two values.
        "Find dy/dx at x = 1 and x = 2 for y = x^3",
        # A prime that labels a point, not a derivative of the function the line defines.
        "The image of A(2, 3) under the reflection in the line y = x is A'(3, 2). Find the "
        "line of reflection.",
        "Triangle A'B'C' is the image of triangle ABC under a reflection in y = 2x.",
    ],
)
def test_givens_no_one_reading_carries_are_declined(text: str) -> None:
    intent = extract_math_intent(text)
    assert intent is None or is_declined(intent)


@pytest.mark.parametrize(
    "text",
    [
        "Find dy/dx for y = x ln x",
        "What is dy/dx when y = x^2 e^x?",
        "Find dy/dx at x = 1 for y = x^3 - x",
        "Find dy/dx when x = 2 if y = x^3",
        "If x = t^2 and y = t^3, find dy/dx",
        "Find the rate of change of y with respect to x for y = x^3 + 2x",
        "Find the integral of y where y = 3x^2",
        "Find lim_{x→2} y where y = (x^2 - 4)/(x - 2)",
    ],
)
def test_a_solve_reading_never_answers_another_ask(text: str) -> None:
    intent = extract_math_intent(text)
    assert intent is None or intent.kind not in _SOLVES


@pytest.mark.parametrize(
    "text",
    [
        # Where the function turns is a step to its extreme values (asked: -4 and 4).
        "Find the relative extrema of f(x) = x + 4/x.",
        "Find the local extrema of f(x) = x⁴ − 4x³.",
        "Find the absolute extrema of f(x) = x⁴ − 2x² on [−2, 1].",
        "Find the critical numbers of f(x) = x³ − 12x and its absolute extrema on [−3, 5].",
        # One extreme read for two asked (the minimum 1 and -7 left out).
        "Find the local maximum and minimum values of f(x) = x³ − 6x² + 9x + 1.",
        "Find the local maximum and minimum values of f(x) = 2x³ + 3x² − 12x.",
    ],
)
def test_critical_points_are_no_answer_to_extreme_values(text: str) -> None:
    intent = extract_math_intent(text)
    assert intent is None or intent.operation != "critical_points"


def test_one_extreme_asked_is_still_the_answer() -> None:
    intent = extract_math_intent("find the maximum value of y = -x^2 + 4x + 1")
    assert intent is not None and intent.school_op == "extreme_value"


def test_critical_points_asked_are_still_the_answer() -> None:
    intent = extract_math_intent("find the critical points of f(x) = x^3 - 3x")
    assert intent is not None and intent.operation == "critical_points"


@pytest.mark.parametrize(
    "text",
    [
        "Solve 2x + 5 = 17",
        "solve x^2 - 5x + 6 = 0",
        "Solve the system x + y = 5, x - y = 1",
        "Solve 2x + 1 > 7",
        # A derivative's spelling the readers do not count: a plural, a word.
        "The derivatives chapter is done. Solve 3x - 4 = 11",
    ],
)
def test_a_solve_asked_is_still_solved(text: str) -> None:
    intent = extract_math_intent(text)
    assert intent is not None and intent.kind in _SOLVES


@pytest.mark.parametrize(
    ("text", "asked"),
    [
        ("Find dy/dx for y = x ln x", AskedOperations(derivative_orders=frozenset({1}))),
        ("Find d²y/dx² for y = cos²(2x + 1)", AskedOperations(derivative_orders=frozenset({2}))),
        ("Find d^{2}y/dx^{2} if y = x^3", AskedOperations(derivative_orders=frozenset({2}))),
        ("Find the second derivative of x^4", AskedOperations(derivative_orders=frozenset({2}))),
        ("Find y″ if y = x^4", AskedOperations(derivative_orders=frozenset({2}))),
        (
            "Find f'(x) and f''(x)",
            AskedOperations(derivative_orders=frozenset({1, 2}), combined=True),
        ),
        ("Find f'(3)", AskedOperations(derivative_orders=frozenset({1}), at_point=True)),
        (
            "Find dy/dx at x = 2 for y = x^3",
            AskedOperations(derivative_orders=frozenset({1}), at_point=True),
        ),
        # A function defined by a formula is no point.
        (
            "Find dy/dx when y = 2x^3 - 5x",
            AskedOperations(derivative_orders=frozenset({1}), location=True),
        ),
        # A derivative given, not asked: "f'(x) = 3x^2, find f(x)".
        ("If f'(x) = 3x^2 and f(0) = 1, find f(x)", AskedOperations()),
        (
            "the rate of change of y with respect to x",
            AskedOperations(derivative_orders=frozenset({1})),
        ),
        ("the average rate of change of y with respect to x from 1 to 3", AskedOperations()),
        ("Find lim_{h→0} (f(3 + h) − f(3))/h", AskedOperations(limit=True)),
        ("Evaluate the limit of sin x / x as x approaches 0", AskedOperations(limit=True)),
        ("Integrate x^2 from 0 to 3", AskedOperations(integral=True)),
        ("∫ x^2 dx", AskedOperations(integral=True)),
        ("Find an antiderivative of 2x", AskedOperations(integral=True)),
        (
            "Find the absolute maximum of f(x) = x^3 on [0, 2]",
            AskedOperations(behaviour=True, extreme_values=True),
        ),
        (
            "Find the relative extrema of f(x) = x + 4/x",
            AskedOperations(behaviour=True, extreme_values=True),
        ),
        (
            "Find the local maximum and minimum values of f(x) = 2x³ + 3x² − 12x",
            AskedOperations(behaviour=True, extreme_values=True, both_extremes=True),
        ),
        (
            "Find the greatest and least values of y = x^2 on [0, 1]",
            AskedOperations(both_extremes=True),
        ),
        ("Find the critical numbers of f(x) = x^3 - 3x", AskedOperations(behaviour=True)),
        ("Where is f(x) = x^3 increasing?", AskedOperations(behaviour=True, location=True)),
        ("Find the asymptotes of y = 1/(x - 2)", AskedOperations(behaviour=True)),
        ("Solve 2x + 5 = 17", AskedOperations()),
        ("Simplify (x^2 - 1)/(x - 1)", AskedOperations()),
        # "min" for minutes is no minimum.
        ("Solve 3x = 12, then rest for 5 min", AskedOperations()),
    ],
)
def test_what_a_question_asks(text: str, asked: AskedOperations) -> None:
    assert asked_operations(text) == asked


_DERIVATIVE = AskedOperations(derivative_orders=frozenset({1}))
_SECOND = AskedOperations(derivative_orders=frozenset({2}))
_AT_A_POINT = AskedOperations(derivative_orders=frozenset({1}), at_point=True)
_EXTREMA = AskedOperations(behaviour=True)
_LIMIT = AskedOperations(limit=True)


@pytest.mark.parametrize(
    ("asked", "computation", "order", "at_point", "answers"),
    [
        (_DERIVATIVE, "derivative", 1, False, True),
        (_SECOND, "derivative", 1, False, False),  # dy/dx for d²y/dx²
        (_SECOND, "derivative", 2, False, True),
        (_AT_A_POINT, "derivative", 1, False, False),  # f'(x) for f'(3)
        (_AT_A_POINT, "derivative", 1, True, True),
        (_EXTREMA, "derivative", 1, False, False),  # f'(x) for the maximum
        (_LIMIT, "derivative", 1, False, False),  # f'(x) for lim (f(3 + h) - f(3))/h
        (_LIMIT, "limit", 1, False, True),
        (_DERIVATIVE, "limit", 1, False, False),
        (AskedOperations(integral=True), "integral", 1, False, True),
        (_DERIVATIVE, "integral", 1, False, False),
        (_DERIVATIVE, "solve", 1, False, False),  # y = x ln x solved for x
        (AskedOperations(), "solve", 1, False, True),
        # A sketch's simplified f is a step the server's reading of the sketch refuses
        # (``call_answers_reading``); words alone refuse no rewrite.
        (_EXTREMA, "rewrite", 1, False, True),
        (_EXTREMA, "solve", 1, False, True),  # "the maximum value of x if 2x + 3 = 11"
        (AskedOperations(), "rewrite", 1, False, True),
    ],
)
def test_a_computation_answers_only_what_is_asked(
    asked: AskedOperations, computation: str, order: int, at_point: bool, answers: bool
) -> None:
    got = computes_the_ask(asked, computation, order=order, at_point=at_point)  # type: ignore[arg-type]
    assert got is answers


@pytest.mark.parametrize(
    ("text", "args", "answers"),
    [
        (
            "Let f(x) = x² − x + 3. Find lim_{h→0} (f(3 + h) − f(3))/h.",
            {"action": "diff", "expr": "x^2 - x + 3"},
            False,
        ),
        ("Find d²y/dx² for y = cos²(2x + 1).", {"action": "diff", "expr": "cos(2*x+1)^2"}, False),
        (
            "Find d²y/dx² for y = cos²(2x + 1).",
            {"action": "diff", "expr": "cos(2*x+1)^2", "order": 2},
            True,
        ),
        (
            "Find the local maximum and minimum values of f(x) = 2x − 3x^(2/3).",
            {"action": "diff", "expr": "2*x - 3*x^(2/3)"},
            False,
        ),
        (
            "Sketch the graph of f(x) = (2x − 6)/(x² − 9), indicating the asymptotes.",
            {"action": "graph", "expr": "(2*x - 6)/(x^2 - 9)"},
            True,
        ),
        ("Differentiate x^3 sin x", {"action": "diff", "expr": "x^3*sin(x)"}, True),
        ("Solve 2x + 5 = 17", {"action": "solve", "lhs": "2*x + 5", "rhs": "17"}, True),
        ("Find dy/dx for y = x ln x", {"action": "solve", "lhs": "y", "rhs": "x*log(x)"}, False),
        ("Differentiate x^3", {"action": "diff", "expr": "x^3", "order": "two"}, False),
    ],
)
def test_a_tool_call_answers_only_what_is_asked(
    text: str, args: dict[str, object], answers: bool
) -> None:
    assert call_computes_the_ask(text, args) is answers


@pytest.mark.parametrize(
    ("text", "intent", "answers"),
    [
        (
            "Let f(x) = x² − x + 3. Find lim_{h→0} (f(3 + h) − f(3))/h.",
            MathIntent(kind="calculus", operation="differentiate", expr="x^2 - x + 3"),
            False,
        ),
        (
            "Find d²y/dx² for y = cos²(2x + 1).",
            MathIntent(kind="calculus", operation="differentiate", expr="cos(2x + 1)^2"),
            False,
        ),
        (
            "Identify the critical numbers and find the absolute maximum and absolute minimum "
            "values of f(x) = 2cos x + x on [0, 2π].",
            MathIntent(kind="calculus", operation="differentiate", expr="2cos(x) + x"),
            False,
        ),
        (
            "What is the derivative of x^3 sin x",
            MathIntent(kind="calculus", operation="differentiate", expr="x^3 sin(x)"),
            True,
        ),
        (
            "Find dy/dx for y = x ln x",
            MathIntent(kind="equation", operation="solve", lhs="y", rhs="x ln x"),
            False,
        ),
        # A school reading answers its own question; it is not judged here.
        (
            "Find the local maximum and minimum values of f(x) = 2x − 3x^(2/3).",
            MathIntent(kind="calculus", operation="critical_points", expr="2x - 3x^(2/3)"),
            True,
        ),
    ],
)
def test_a_reading_answers_only_what_is_asked(text: str, intent: MathIntent, answers: bool) -> None:
    assert reading_computes_the_ask(text, intent) is answers

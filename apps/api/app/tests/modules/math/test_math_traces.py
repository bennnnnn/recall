"""Verified step traces for inequalities and 2x2 systems, and their lessons."""

import json
import re

import pytest
from sympy import S, Symbol, solveset, sympify
from sympy.core.relational import Ge, Gt, Le, Lt

from app.core.config import Settings
from app.modules.math import tools as mt
from app.modules.math.solve.traces import (
    compound_inequality_key_steps,
    inequality_key_steps,
    system_key_steps,
    system_trace,
)
from app.modules.math.tools.direct import maybe_direct_math_reply
from app.modules.math.tools.extract import extract_math_intent

x = Symbol("x")
y = Symbol("y")
_RELATIONS = {"<": Lt, ">": Gt, "<=": Le, ">=": Ge}


def _steps(steps):
    return [(step.label, step.formula) for step in steps]


@pytest.mark.parametrize(
    ("lhs", "rhs", "comparator", "expected"),
    [
        (
            2 * x + 3,
            7,
            "<",
            [("Subtract 3 from both sides", "2 x < 4"), ("Divide both sides by 2", "x < 2")],
        ),
        (
            -3 * x + 2,
            8,
            ">=",
            [
                ("Subtract 2 from both sides", r"- 3 x \ge 6"),
                ("Divide both sides by -3", r"x \le -2"),
            ],
        ),
        (
            5 * x - 3,
            2 * x + 9,
            ">",
            [
                ("Subtract 2 x from both sides", "3 x - 3 > 9"),
                ("Add 3 to both sides", "3 x > 12"),
                ("Divide both sides by 3", "x > 4"),
            ],
        ),
        (
            7,
            2 * x + 3,
            "<",
            [
                ("Swap the sides", "2 x + 3 > 7"),
                ("Subtract 3 from both sides", "2 x > 4"),
                ("Divide both sides by 2", "x > 2"),
            ],
        ),
    ],
)
def test_inequality_trace_undoes_one_operation_per_line(lhs, rhs, comparator, expected):
    assert _steps(inequality_key_steps(sympify(lhs), sympify(rhs), "x", comparator)) == expected


def test_inequality_trace_says_why_a_negative_divisor_flips_the_sign():
    steps = inequality_key_steps(-3 * x + 2, sympify(8), "x", ">=")
    assert steps[-1].reason == "dividing by a negative number reverses the inequality"


@pytest.mark.parametrize(
    ("lhs", "rhs", "comparator"),
    [(2 * x + 3, 7, "<"), (-4 * x - 1, 3 * x + 13, "<="), (6 - x, 2, ">"), (9, -3 * x, ">=")],
)
def test_every_inequality_line_keeps_the_solution_set(lhs, rhs, comparator):
    target = solveset(_RELATIONS[comparator](sympify(lhs), sympify(rhs)), x, S.Reals)
    steps = inequality_key_steps(sympify(lhs), sympify(rhs), "x", comparator)
    assert steps
    for step in steps:
        text = step.formula.replace(r"\le", "<=").replace(r"\ge", ">=")
        text = re.sub(r"(\d)\s*x", r"\1*x", text)
        for symbol in ("<=", ">=", "<", ">"):
            if f" {symbol} " in text:
                left, right = text.split(f" {symbol} ")
                relation = _RELATIONS[symbol](sympify(left), sympify(right))
                assert solveset(relation, x, S.Reals) == target
                break


@pytest.mark.parametrize(
    ("lhs", "rhs"),
    [(x**2, 4), (1 / x, 2), (sympify(3), 5)],
)
def test_inequality_trace_is_empty_when_not_linear(lhs, rhs):
    assert inequality_key_steps(sympify(lhs), sympify(rhs), "x", "<") == []


def test_compound_trace_keeps_both_ends():
    steps = compound_inequality_key_steps(sympify(-1), "<", 2 * x + 3, "<", sympify(7), "x")
    assert _steps(steps) == [
        ("Subtract 3 from all three parts", "-4 < 2 x < 4"),
        ("Divide all three parts by 2", "-2 < x < 2"),
    ]


def test_compound_trace_rewrites_a_negative_division_smallest_first():
    steps = compound_inequality_key_steps(sympify(-1), "<", -2 * x + 3, "<=", sympify(7), "x")
    assert steps[-1].label == "Divide all three parts by -2"
    assert steps[-1].formula == r"-2 \le x < 2"
    assert "reverses both signs" in (steps[-1].reason or "")


def test_system_trace_substitutes_when_an_unknown_has_coefficient_one():
    steps = system_key_steps([(2 * x + 3 * y, sympify(12)), (x - y, sympify(1))], ["x", "y"])
    labels = [step.label for step in steps]
    assert labels[0] == "Solve equation (2) for x"
    assert steps[0].formula == "x = y + 1"
    assert labels[1] == "Substitute into equation (1)"
    assert steps[1].formula == r"2 \left(y + 1\right) + 3 y = 12"
    assert steps[-2].formula == "y = 2"
    assert steps[-1].formula == r"x = \left(2\right) + 1 = 3"


def test_system_trace_uses_an_equation_already_solved_for_an_unknown():
    steps = system_key_steps([(y, 2 * x + 1), (3 * x + y, sympify(11))], ["x", "y"])
    assert steps[0].label == "Substitute into equation (2)"
    assert steps[-1].formula == r"y = 2 \left(2\right) + 1 = 5"


def test_system_trace_eliminates_with_integer_multipliers():
    steps = system_key_steps(
        [(3 * x + 2 * y, sympify(16)), (5 * x - 3 * y, sympify(-5))], ["x", "y"]
    )
    assert _steps(steps)[:4] == [
        ("Multiply equation (1) by 3", "9 x + 6 y = 48"),
        ("Multiply equation (2) by 2", "10 x - 6 y = -10"),
        ("Add the equations", "19 x = 38"),
        ("Divide both sides by 19", "x = 2"),
    ]
    assert steps[-1].formula == "y = 5"


@pytest.mark.parametrize(
    "pairs",
    [
        [(2 * x + 4 * y, sympify(10)), (3 * x + 6 * y, sympify(15))],
        [(x + y, sympify(1)), (x + y, sympify(2))],
        [(x * y, sympify(6)), (x + y, sympify(5))],
    ],
)
def test_system_trace_is_empty_without_one_linear_solution(pairs):
    assert system_key_steps(pairs, ["x", "y"]) == []


def test_system_trace_checks_the_answer_in_both_equations():
    steps, given, check = system_trace([("2x+3y", "12"), ("x-y", "1")], ["x", "y"])
    assert steps
    assert given == r"2 x + 3 y = 12, \quad x - y = 1"
    assert check == (
        r"2 \left(3\right) + 3 \left(2\right) = 12 \text{ and } "
        r"\left(3\right) - \left(2\right) = 1"
    )


def _reply(text: str, style: str) -> str | None:
    intent = extract_math_intent(text)
    assert intent is not None
    verified = mt._build_verified_block(intent, Settings())
    assert verified is not None
    return maybe_direct_math_reply(verified, text, response_style=style)


def test_a_system_gets_a_server_rendered_lesson():
    reply = _reply("solve 2x+3y=12, x-y=1", "balanced")
    assert reply is not None
    assert reply.startswith(r"**Given:** $2 x + 3 y = 12, \quad x - y = 1$")
    assert "**1. Solve equation (2) for x**\n$x = y + 1$" in reply
    assert reply.endswith("```answer\nx = 3, y = 2\n```\n")


def test_an_inequality_lesson_keeps_its_number_line_and_a_clean_answer():
    reply = _reply("show steps for 2x + 3 < 7", "balanced")
    assert reply is not None
    assert "**1. Subtract 3 from both sides**\n$2 x < 4$" in reply
    assert "```answer\nx < 2\n```" in reply
    graph = reply.split("```graph\n", 1)[1].split("\n```", 1)[0]
    assert json.loads(graph)["type"] == "number_line"


def test_explain_adds_the_reason_for_the_flip():
    reply = _reply("explain how to solve -3x+2>=8", "balanced")
    assert reply is not None
    assert (
        r"**2. Divide both sides by -3** — dividing by a negative number reverses the inequality"
        "\n$x \\le -2$"
    ) in reply


def test_a_short_inequality_answer_uses_the_clean_spelling():
    reply = _reply("solve -3x+2>=8", "short")
    assert reply is not None
    assert reply.startswith("```answer\nx \\le -2\n```")
    assert "Given" not in reply


@pytest.mark.parametrize(
    ("expr", "labels"),
    [
        (
            "x**3 + 2*x",
            [
                "Differentiate term by term",
                "Power rule on $x^{3}$",
                "Keep $2$ and differentiate $x$",
                "Add the results",
            ],
        ),
        ("x**2*sin(x)", [r"Product rule with $u = x^{2}$ and $v = \sin{\left(x \right)}$"]),
        ("(x**2+1)/(x-1)", ["Quotient rule with $u = x^{2} + 1$ and $v = x - 1$"]),
        ("sin(3*x**2)", ["Chain rule with inside $3 x^{2}$"]),
        ("(x**2+1)**5", ["Chain rule with inside $x^{2} + 1$"]),
        ("2**x", ["Exponential rule on $2^{x}$"]),
        ("exp(x)", ["Derivative of $e^{x}$"]),
    ],
)
def test_derivative_trace_names_the_rule_for_each_part(expr, labels):
    from app.modules.math.solve.derivative_steps import derivative_key_steps

    assert [step.label for step in derivative_key_steps(sympify(expr), "x")] == labels


@pytest.mark.parametrize(
    "expr",
    ["x**3 + 2*x", "x**2*sin(x)", "(x**2+1)/(x-1)", "sin(3*x**2)", "5*x**4 - 3*x + 7", "x*exp(x)"],
)
def test_derivative_trace_ends_on_the_verified_answer(expr):
    from app.modules.math.solve.algebra import differentiate_expression
    from app.modules.math.solve.derivative_steps import derivative_key_steps

    steps = derivative_key_steps(sympify(expr), "x")
    assert steps[-1].formula.endswith(differentiate_expression(expr).latex)


def test_derivative_trace_is_empty_for_an_unknown_rule():
    from app.modules.math.solve.derivative_steps import derivative_key_steps

    assert derivative_key_steps(sympify("asinh(x)"), "x") == []


def test_a_multi_part_derivative_gets_a_lesson_with_a_find_line():
    reply = _reply("differentiate x^3 + 2x", "balanced")
    assert reply is not None
    assert reply.startswith(r"**Find:** $\frac{d}{dx}\left(x^{3} + 2 x\right)$")
    assert "**2. Power rule on $x^{3}$**" in reply
    assert reply.endswith("```answer\n3 x^{2} + 2\n```\n")


def test_a_one_rule_derivative_stays_an_answer_card_unless_detailed():
    assert _reply("differentiate x^2 sin(x)", "balanced") == (
        "```answer\nx \\left(x \\cos{\\left(x \\right)} + 2 \\sin{\\left(x \\right)}\\right)\n```\n"
    )
    detailed = _reply("differentiate x^2 sin(x)", "detailed")
    assert detailed is not None
    assert "— $(uv)' = u'v + uv'$" in detailed


@pytest.mark.parametrize(
    ("expr", "first_label"),
    [
        ("x**2 + 3*x", "Integrate term by term"),
        ("2*x*cos(x**2)", "Let $u = x^{2}$"),
        ("x*(x**2+1)**5", "Let $u = x^{2} + 1$"),
        ("x*exp(x)", r"Choose $u = x$ and $dv = e^{x}\,dx$"),
        ("log(x)", r"Choose $u = \log{\left(x \right)}$ and $dv = dx$"),
        ("x**3", "Power rule on $x^{3}$"),
    ],
)
def test_integral_trace_picks_the_method_from_the_integrand(expr, first_label):
    from app.modules.math.solve.integral_steps import integral_key_steps

    steps, _ = integral_key_steps(sympify(expr), "x")
    assert steps[0].label == first_label
    assert steps[-1].formula.endswith("+ C")


@pytest.mark.parametrize(
    "expr",
    [
        "x**2 + 3*x",
        "2*x*cos(x**2)",
        "x*(x**2+1)**5",
        "x*exp(x)",
        "x**2*exp(x)",
        "x*sin(x)",
        "x*log(x)",
    ],
)
def test_integral_trace_antiderivative_differentiates_back(expr):
    from sympy import diff, simplify

    from app.modules.math.solve.integral_steps import integral_key_steps

    _, antiderivative = integral_key_steps(sympify(expr), "x")
    assert simplify(diff(antiderivative, x) - sympify(expr)) == 0


def test_integration_by_parts_keeps_the_sign_of_what_is_left():
    from app.modules.math.solve.integral_steps import integral_key_steps

    steps, _ = integral_key_steps(sympify("x*sin(x)"), "x")
    assert steps[1].formula == (
        r"\int x \sin{\left(x \right)}\,dx = - x \cos{\left(x \right)} "
        r"+ \int \cos{\left(x \right)}\,dx"
    )
    assert steps[2].formula == r"\int \cos{\left(x \right)}\,dx = \sin{\left(x \right)}"


def test_integral_trace_is_empty_for_an_unknown_method():
    from app.modules.math.solve.integral_steps import integral_key_steps

    assert integral_key_steps(sympify("tan(x)"), "x") == ([], None)


def test_an_integral_lesson_ends_on_its_checked_antiderivative():
    reply = _reply("integrate x(x^2+1)^5", "balanced")
    assert reply is not None
    assert reply.startswith(r"**Find:** $\int x \left(x^{2} + 1\right)^{5}\,dx$")
    assert reply.endswith("```answer\n\\frac{\\left(x^{2} + 1\\right)^{6}}{12} + C\n```\n")


def test_a_short_integral_answer_reads_term_by_term():
    assert _reply("integrate x^2 + 3x", "short") == (
        "```answer\n\\frac{x^{3}}{3} + \\frac{3 x^{2}}{2} + C\n```\n"
    )


@pytest.mark.parametrize(
    "text, rule",
    [
        ("differentiate x^2 sin(x) step by step", "Product rule"),
        ("show steps: differentiate x^2 sin(x)", "Product rule"),
        ("explain how to integrate x e^x", "Choose $u = x$"),
        ("Show steps: integrate x(x^2+1)^5", "Let $u = x^{2} + 1$"),
    ],
)
def test_teaching_words_around_calculus_still_get_the_lesson(text: str, rule: str) -> None:
    reply = _reply(text, "balanced")
    assert reply is not None and "**1." in reply and rule in reply


def test_calculus_with_an_unrelated_ask_keeps_the_model() -> None:
    assert _reply("differentiate x^2 sin(x) and tell me a joke", "balanced") is None

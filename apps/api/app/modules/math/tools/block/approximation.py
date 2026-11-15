"""The verified block and worked reply of a named numerical method: a rule of integration
with n subintervals, Newton's method for n steps, Euler's method with step h.

Each value is the method's own (``solve/approximation.py``): T_4 = 2.75 for the
trapezoidal rule, never the integral 8/3 a model's correct 2.75 was once "corrected" to
(2026-11-13 audit, MATH-01). The reply is the worked layout every verified answer has
(Given, Required, Solution with the method's formula and its substitution, Answer).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from sympy import Symbol, latex

from app.core.config import Settings
from app.modules.math.response_intent import classify_math_response_intent
from app.modules.math.schemas import MathIntent
from app.modules.math.solve.approximation import (
    decimal_tex,
    euler_points,
    exact_number,
    newton_iterates,
    plain_tex,
    rule_sum,
    value_tex,
)
from app.modules.math.solve.declines import sympy_decline
from app.modules.math.solve.parse import parse_expression
from app.modules.math.tools.block.canonical import finish_with_answer
from app.services.solving import VerifiedMathBlock
from app.services.workout import Workout, math_line, render_workout

# The rule's letter and name, and its formula in general.
_RULES: dict[str, tuple[str, str, str]] = {
    "trapezoid": (
        "T",
        "Trapezoidal rule",
        r"T_n = \frac{h}{2}\left[f(x_0) + 2f(x_1) + \cdots + 2f(x_{n-1}) + f(x_n)\right]",
    ),
    "midpoint": (
        "M",
        "Midpoint rule",
        r"M_n = h\left[f(m_1) + f(m_2) + \cdots + f(m_n)\right]",
    ),
    "simpson": (
        "S",
        "Simpson's rule",
        r"S_n = \frac{h}{3}\left[f(x_0) + 4f(x_1) + 2f(x_2) + \cdots + 4f(x_{n-1}) + f(x_n)\right]",
    ),
    "left": ("L", "Left Riemann sum", r"L_n = h\left[f(x_0) + f(x_1) + \cdots + f(x_{n-1})\right]"),
    "right": ("R", "Right Riemann sum", r"R_n = h\left[f(x_1) + f(x_2) + \cdots + f(x_n)\right]"),
}
# A list longer than this is shown by its ends.
_SHOWN = 8


def approximation_block(intent: MathIntent, settings: Settings) -> VerifiedMathBlock | None:
    """The block for ``intent``'s named method, or None when it cannot be worked."""
    builder = {"newton": _newton_block, "euler": _euler_block}.get(intent.numeric_rule or "")
    with sympy_decline() as declined:
        block = (builder or _rule_block)(intent, settings)
    return None if declined else block


def _finish(intent: MathIntent, lines: list[str], answer: str, worked: str) -> VerifiedMathBlock:
    """The block, with the worked reply as its direct reply unless the question also asks
    for an explanation, which the model writes around the verified card."""
    block = finish_with_answer(lines, answer)
    request = intent._request_text or ""
    if classify_math_response_intent(request).wants_explanation:
        return block
    return replace(block, direct_reply=worked)


def _elided(items: Sequence[str]) -> list[str]:
    if len(items) <= _SHOWN:
        return list(items)
    return [*items[:4], r"\cdots", *items[-2:]]


def _rule_block(intent: MathIntent, settings: Settings) -> VerifiedMathBlock | None:
    rule, n = intent.numeric_rule or "", intent.numeric_steps or 0
    if rule not in _RULES or not (intent.expr and intent.integral_lower and intent.integral_upper):
        return None
    letter, name, formula = _RULES[rule]
    variable = intent.variable or "x"
    worked = rule_sum(
        intent.expr[: settings.math_max_expr_length],
        variable,
        intent.integral_lower,
        intent.integral_upper,
        n,
        rule,
    )
    expr = parse_expression(intent.expr, [variable])
    low, high = exact_number(intent.integral_lower), exact_number(intent.integral_upper)
    symbol = f"{letter}_{{{n}}}"
    integral = rf"\int_{{{latex(low)}}}^{{{latex(high)}}} {latex(expr)}\,d{variable}"
    calls = _elided(
        [
            _weighted(w, f"f({plain_tex(x)})")
            for w, x in zip(worked.weights, worked.nodes, strict=True)
        ]
    )
    values = _elided(
        [_weighted(w, plain_tex(v)) for w, v in zip(worked.weights, worked.values, strict=True)]
    )
    bracket = sum(w * v for w, v in zip(worked.weights, worked.values, strict=True))
    factor = plain_tex(worked.factor)
    value = value_tex(worked.total)
    answer = f"{symbol} {value}" if value.startswith(r"\approx") else f"{symbol} = {value}"
    lines = [
        f"{name} with n = {n} on [{low}, {high}] for f({variable}) = {expr}: h = {worked.h}.",
        f"Nodes: {', '.join(str(x) for x in worked.nodes)}; f there: "
        f"{', '.join(plain_tex(v) for v in worked.values)}.",
        f"{symbol} = {plain_tex(worked.factor)} * {plain_tex(bracket)} = {value}; this is the "
        "estimate asked for, not the exact integral.",
    ]
    reply = render_workout(
        Workout(
            given=(
                math_line(f"f({variable}) = {latex(expr)}"),
                math_line(f"a = {latex(low)},\\quad b = {latex(high)},\\quad n = {n}"),
            ),
            find=(math_line(symbol, f"the {name.lower()} estimate of ${integral}$"),),
            formula=(math_line(formula), math_line(r"h = \frac{b - a}{n}")),
            formula_heading=name,
            substitution=(
                math_line(
                    rf"h = \frac{{{latex(high)} - {latex(low)}}}{{{n}}} = {plain_tex(worked.h)}"
                ),
                math_line(rf"{symbol} = {factor}\left[{' + '.join(calls)}\right]"),
                math_line(rf"{symbol} = {factor}\left[{' + '.join(values)}\right]"),
                math_line(rf"{symbol} = {factor} \times {plain_tex(bracket)}"),
            ),
        ),
        answer,
    )
    return _finish(intent, lines, answer, reply)


def _weighted(weight: Any, term: str) -> str:
    return (
        term if weight == 1 else f"{weight}{term}" if term.startswith("f(") else f"{weight}({term})"
    )


def _steps_note(steps: int) -> str:
    return "after one Newton step" if steps == 1 else f"after {steps} Newton steps"


def _newton_block(intent: MathIntent, settings: Settings) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.newton_guess is not None and intent.numeric_steps):
        return None
    variable = intent.variable or "x"
    start = repr(intent.newton_guess)
    iterates = newton_iterates(
        intent.expr[: settings.math_max_expr_length], variable, start, intent.numeric_steps
    )
    f = parse_expression(intent.expr, [variable])
    slope = f.diff(Symbol(variable))
    first = intent.numeric_first_index

    def name(k: int) -> str:
        return f"{variable}_{{{first + k}}}"

    substitution: list[str] = []
    for k in range(1, len(iterates)):
        previous = iterates[k - 1]
        at = dict.fromkeys(f.free_symbols, previous)
        rise, run = plain_tex(f.subs(at)), plain_tex(slope.subs(at))
        point = plain_tex(previous)
        substitution.append(math_line(rf"f({point}) = {rise},\quad f'({point}) = {run}"))
        substitution.append(math_line(rf"{name(k)} = {point} - \frac{{{rise}}}{{{run}}}"))
        if k < len(iterates) - 1:
            substitution.append(math_line(f"{name(k)} = {value_tex(iterates[k])}"))
    # "find x_1 and x_2": the card holds every iterate asked; else the last alone.
    shown = range(1, len(iterates)) if intent.numeric_every_step else [len(iterates) - 1]
    answer = r",\quad ".join(f"{name(k)} = {value_tex(iterates[k])}" for k in shown)
    lines = [
        f"Newton's method on f({variable}) = {f}, f'({variable}) = {slope}, from "
        f"{name(0)} = {iterates[0]}, {_steps_note(intent.numeric_steps)} as asked:",
        *(f"  {name(k)} = {value}" for k, value in enumerate(iterates)),
        "The iterate asked for is the answer, not the root.",
    ]
    reply = render_workout(
        Workout(
            given=(
                math_line(f"f({variable}) = {latex(f)}"),
                math_line(f"{name(0)} = {plain_tex(iterates[0])}"),
            ),
            find=(math_line(", ".join(name(k) for k in shown), _steps_note(intent.numeric_steps)),),
            formula=(
                math_line(
                    rf"{variable}_{{n+1}} = {variable}_n"
                    rf" - \frac{{f({variable}_n)}}{{f'({variable}_n)}}"
                ),
                math_line(f"f'({variable}) = {latex(slope)}"),
            ),
            formula_heading="Newton's method",
            substitution=tuple(substitution),
        ),
        answer,
    )
    return _finish(intent, lines, answer, reply)


def _euler_block(intent: MathIntent, settings: Settings) -> VerifiedMathBlock | None:
    if not (
        intent.expr
        and intent.initial_x
        and intent.initial_y
        and intent.numeric_step_size
        and intent.numeric_steps
        and intent.evaluation_point
    ):
        return None
    points = euler_points(
        intent.expr[: settings.math_max_expr_length],
        intent.initial_x,
        intent.initial_y,
        intent.numeric_step_size,
        intent.numeric_steps,
    )
    rate = parse_expression(intent.expr, ["x", "y"])
    h = exact_number(intent.numeric_step_size)
    substitution: list[str] = []
    for k in range(1, len(points)):
        (x0, y0), (_x1, y1) = points[k - 1], points[k]
        slope = rate.subs({s: x0 if str(s) == "x" else y0 for s in rate.free_symbols})
        before, step = plain_tex(y0), plain_tex(h)
        substitution.append(
            math_line(
                rf"y_{{{k}}} = {before} + {step} \times f({plain_tex(x0)}, {before})"
                rf" = {before} + {step} \times {plain_tex(slope)}"
            )
        )
        if k < len(points) - 1:
            substitution.append(math_line(f"y_{{{k}}} = {value_tex(y1)}"))
    end_x, end_y = points[-1]
    target = f"y({plain_tex(end_x)})"
    # Euler's value estimates y; the card says so whatever its digits.
    answer = rf"{target} \approx {decimal_tex(end_y)}"
    lines = [
        f"Euler's method on y' = {rate}, y({points[0][0]}) = {points[0][1]}, h = {h}, "
        f"{intent.numeric_steps} steps:",
        *(f"  x_{k} = {x}, y_{k} = {y}" for k, (x, y) in enumerate(points)),
        "Euler's estimate is the answer asked for, not the exact solution.",
    ]
    reply = render_workout(
        Workout(
            given=(
                math_line(f"y' = {latex(rate)}"),
                math_line(f"y({plain_tex(points[0][0])}) = {plain_tex(points[0][1])}"),
                math_line(f"h = {plain_tex(h)}"),
            ),
            find=(math_line(target, "Euler's estimate"),),
            formula=(math_line(r"y_{n+1} = y_n + h\,f(x_n, y_n)"),),
            formula_heading="Euler's method",
            substitution=tuple(substitution),
        ),
        answer,
    )
    return _finish(intent, lines, answer, reply)

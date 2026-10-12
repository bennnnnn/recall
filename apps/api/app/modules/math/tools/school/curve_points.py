"""Tangent and normal lines, and stationary points, of ``y = f(x)``.

Read as plain algebra these went wrong: "the tangent to y = x^2 at x = 3" was
solved as the system ``y = x^2, x = 3`` and answered with the point (3, 9), and
"the stationary points of y = x^3 - 3x" solved the curve for ``x`` in terms of
``y``. Both now differentiate.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from app.modules.math.schemas import MathIntent
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.services.workout import Workout, math_line, render_workout

CURVE_POINT_OPS = frozenset({"tangent_line", "normal_line", "stationary_points"})

_NUMBER = r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s*/\s*\d+)?"
_CURVE = r"(?:the\s+(?:curve|graph|function)\s+)?(?:(?:y|[a-z]\s*\(\s*x\s*\))\s*=\s*)?"
_TANGENT = re.compile(
    rf"\b(?P<kind>tangent|normal)(?:\s+line)?\s+(?:to|of|for)\s+{_CURVE}(?P<expr>.+?)\s+"
    rf"(?:at|where|when)\s+(?:the\s+point\s+)?"
    rf"(?:x\s*=\s*(?P<x>{_NUMBER})|\(\s*(?P<px>{_NUMBER})\s*,\s*(?P<py>{_NUMBER})\s*\))\s*$",
    re.IGNORECASE,
)
_STATIONARY = re.compile(
    # Not "critical points": those include where dy/dx is undefined, which
    # the critical-point solver looks for and this block does not.
    rf"\b(?:stationary|turning)\s+points?\s+(?:of|for|on)\s+{_CURVE}(?P<expr>.+?)\s*$"
    rf"|\b(?:local\s+)?(?:maximum|max)\s+and\s+(?:local\s+)?(?:minimum|min)(?:\s+points?)?"
    rf"\s+(?:of|for)\s+{_CURVE}(?P<expr2>.+?)\s*$",
    re.IGNORECASE,
)
_LEAD = re.compile(
    r"^\s*(?:(?:please\s+)?(?:find|determine|work\s+out|calculate|what\s+(?:is|are)|give)\s+)?"
    r"(?:the\s+)?(?:equation\s+of\s+(?:the\s+)?)?(?:all\s+(?:the\s+)?)?",
    re.IGNORECASE,
)


def _expression(raw: str) -> str | None:
    from app.modules.math.tools.helpers import math_expr_or_none

    text = raw.strip().rstrip(".?!").strip()
    return math_expr_or_none(text) if text else None


def extract_curve_point_intent(cleaned: str) -> MathIntent | None:
    """``find the equation of the tangent to y = x^2 at x = 3``; ``stationary points of ...``."""
    body = " ".join(cleaned.split()).rstrip(".?!")
    lead = _LEAD.match(body)
    request = body[lead.end() :] if lead else body
    tangent = _TANGENT.fullmatch(request)
    if tangent is not None:
        expr = _expression(tangent["expr"])
        point = tangent["x"] or tangent["px"]
        if expr is None or point is None:
            return None
        return MathIntent(
            kind="calculus",
            operation="differentiate",
            school_op="tangent_line" if tangent["kind"].lower() == "tangent" else "normal_line",
            expr=expr,
            variable="x",
            evaluation_point=point.replace(" ", ""),
        )
    stationary = _STATIONARY.fullmatch(request)
    if stationary is not None:
        expr = _expression(stationary["expr"] or stationary["expr2"] or "")
        if expr is None:
            return None
        return MathIntent(
            kind="calculus",
            operation="critical_points",
            school_op="stationary_points",
            expr=expr,
            variable="x",
        )
    return None


def _parse(expr: str, variable: str) -> tuple[Any, Any] | None:
    from sympy import Symbol

    from app.modules.math import solve as math_solve
    from app.services.solving import MathServiceError

    symbol = Symbol(variable, real=True)
    try:
        parsed = math_solve._parse_expression(expr, [variable], real=True)
    except (MathServiceError, SyntaxError, TypeError, ValueError):
        return None
    if isinstance(parsed, tuple) or parsed.free_symbols - {symbol}:
        return None
    return symbol, parsed


def _line_tex(slope: Any, intercept: Any, variable: str) -> str:
    """``y = mx + c`` in that order: no ``1x``, no ``+ 0``.

    ``y = -\\frac{1}{2} x + \\frac{3}{2}``, not SymPy's ``y = \\frac{3}{2} - \\frac{x}{2}``.
    """
    from sympy import latex

    if slope == 0:
        return f"y = {latex(intercept)}"
    if slope == 1:
        term = variable
    elif slope == -1:
        term = f"-{variable}"
    else:
        term = f"{latex(slope)} {variable}"
    if intercept == 0:
        return f"y = {term}"
    sign = "-" if intercept.is_negative else "+"
    return f"y = {term} {sign} {latex(abs(intercept))}"


def _tangent_block(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    from sympy import diff, latex, simplify, sympify

    from app.modules.math.tools.school.function_value import _substituted_tex

    parsed = _parse(intent.expr or "", intent.variable)
    if parsed is None or intent.evaluation_point is None:
        return None
    symbol, curve = parsed
    x1 = sympify(intent.evaluation_point)
    y1 = simplify(curve.subs(symbol, x1))
    derivative = simplify(diff(curve, symbol))
    slope = simplify(derivative.subs(symbol, x1))
    if not (y1.is_real and slope.is_real):
        return None
    var = intent.variable
    normal = intent.school_op == "normal_line"
    steps = [
        math_line(f"y_1 = {_substituted_tex(curve, var, x1)} = {latex(y1)}", "point on the curve"),
        math_line(rf"\frac{{dy}}{{d{var}}} = {latex(derivative)}"),
        math_line(
            f"m = {_substituted_tex(derivative, var, x1)} = {latex(slope)}",
            f"gradient at ${var} = {latex(x1)}$",
        ),
    ]
    if normal:
        if slope == 0:
            answer = f"{var} = {latex(x1)}"
            steps.append(math_line(answer, "the tangent is flat, so the normal is vertical"))
            return _finish(intent, lines, steps, answer, curve)
        tangent_slope, slope = slope, simplify(-1 / slope)
        steps.append(
            math_line(
                rf"m_{{n}} = -\frac{{1}}{{{latex(tangent_slope)}}} = {latex(slope)}",
                "perpendicular to the tangent",
            )
        )
    intercept = simplify(y1 - slope * x1)
    coefficient = {1: "", -1: "-"}.get(slope, latex(slope)) if slope.is_Integer else latex(slope)
    point_form = f"y - {latex(y1)} = {coefficient}\\left({var} - {latex(x1)}\\right)"
    steps.append(math_line(point_form.replace("- -", "+ "), "point-slope form"))
    answer = _line_tex(slope, intercept, var)
    return _finish(intent, lines, steps, answer, curve)


def _finish(
    intent: MathIntent, lines: list[str], steps: list[str], answer: str, curve: Any
) -> VerifiedMathBlock:
    from sympy import latex

    name = "normal" if intent.school_op == "normal_line" else "tangent"
    lines.extend(steps)
    block = _finish_with_answer(lines, answer)
    working = render_workout(
        Workout(
            given=(
                math_line(f"y = {latex(curve)}"),
                math_line(f"{intent.variable} = {intent.evaluation_point}"),
            ),
            find=(f"the {name} line",),
            formula=(math_line("y - y_1 = m(x - x_1)", "Point-slope form"),),
            steps=tuple(steps),
        ),
        answer,
    )
    return replace(block, worked_reply=working)


def _nature(derivative: Any, second: Any, symbol: Any, point: Any, others: list[Any]) -> str:
    """Maximum or minimum by the second derivative; the sign of dy/dx either side if it is 0."""
    value = second.subs(symbol, point)
    if value.is_negative:
        return "maximum"
    if value.is_positive:
        return "minimum"
    gaps = [abs(point - other) for other in others if other != point]
    step = min([*gaps, 1]) / 2
    before = derivative.subs(symbol, point - step)
    after = derivative.subs(symbol, point + step)
    if before.is_positive and after.is_negative:
        return "maximum"
    if before.is_negative and after.is_positive:
        return "minimum"
    return "point of inflection"


def _stationary_block(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    from sympy import Eq, FiniteSet, S, diff, latex, simplify, solveset

    parsed = _parse(intent.expr or "", intent.variable)
    if parsed is None:
        return None
    symbol, curve = parsed
    var = intent.variable
    derivative = simplify(diff(curve, symbol))
    roots = solveset(Eq(derivative, 0), symbol, domain=S.Reals)
    if not isinstance(roots, FiniteSet) or len(roots) > 6:
        return None
    points = sorted(roots, key=lambda root: float(root))
    second = simplify(diff(derivative, symbol))
    dy = rf"\frac{{dy}}{{d{var}}}"
    d2y = rf"\frac{{d^{{2}}y}}{{d{var}^{{2}}}}"
    steps = [math_line(f"{dy} = {latex(derivative)}")]
    if not points:
        answer = r"\text{no stationary points}"
        steps.append(math_line(f"{latex(derivative)} = 0", "has no real solution"))
    else:
        roots_tex = r",\; ".join(f"{var} = {latex(point)}" for point in points)
        steps.append(
            math_line(f"{latex(derivative)} = 0 \\Rightarrow {roots_tex}", "set the gradient to 0")
        )
        steps.append(math_line(f"{d2y} = {latex(second)}"))
        found: list[str] = []
        for point in points:
            y_value = simplify(curve.subs(symbol, point))
            nature = _nature(derivative, second, symbol, point, points)
            curvature = simplify(second.subs(symbol, point))
            sign = "< 0" if curvature.is_negative else "> 0" if curvature.is_positive else "= 0"
            steps.append(
                math_line(
                    f"{var} = {latex(point)}:\\ y = {latex(y_value)},\\ {d2y} = "
                    f"{latex(curvature)} {sign}",
                    nature,
                )
            )
            found.append(rf"\left({latex(point)}, {latex(y_value)}\right)\ \text{{{nature}}}")
        answer = r",\; ".join(found)
    lines.extend(steps)
    block = _finish_with_answer(lines, answer)
    working = render_workout(
        Workout(
            given=(math_line(f"y = {latex(curve)}"),),
            find=("the stationary points",),
            steps=tuple(steps),
        ),
        answer,
    )
    return replace(block, worked_reply=working)


def curve_point_block(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    if intent.school_op == "stationary_points":
        return _stationary_block(intent, lines)
    return _tangent_block(intent, lines)

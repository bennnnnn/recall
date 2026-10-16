"""Calculus verified blocks: one function per ``operation``."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from app.core.config import Settings
from app.modules.math import solve as math_solve
from app.modules.math.schemas import MathExprResult, MathIntent
from app.modules.math.solve.derivative_steps import derivative_trace
from app.modules.math.solve.key_steps import KeyStep, written_side
from app.modules.math.tools.block.calculus_applications import (
    _CALCULUS_APPLICATION_OPS,
    _verified_calculus_application,
)
from app.modules.math.tools.block.canonical import _finish_with_answer
from app.modules.math.tools.block.derivatives import (
    _derivative_at_point,
    _higher_derivative_at_point,
)
from app.modules.math.tools.block.integrals import (
    _definite_integral_reply,
    _improper_integral_block,
    _integral,
    _is_log_over_x_integral,
    _log_over_x_reply,
)
from app.services.solving import VerifiedMathBlock
from app.services.workout import Workout, math_line, render_workout, text_line

_FUNCTION_ANALYSIS_OPS = {
    "function_domain",
    "function_range",
    "function_inverse",
    "function_compose",
    "function_symmetry",
}
# The school extension answers these. When it declines, the plain operation would answer
# another question (an average value's operation is "integrate").
_SCHOOL_ONLY_OPS = {
    "average_value",
    "linear_approx",
    "gradient",
    "directional",
    "divergence",
    "curl",
    "implicit",
    "identity",
}

_Operation = Callable[[MathIntent, str, Settings, list[str]], VerifiedMathBlock | None]


def _verified_block_calculus(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.operation):
        return None
    if intent.school_op in _FUNCTION_ANALYSIS_OPS:
        return _verified_function_analysis(intent, lines)
    if intent.school_op in _CALCULUS_APPLICATION_OPS:
        return _verified_calculus_application(intent, lines)
    from app.modules.math.tools.school.curve_points import CURVE_POINT_OPS, curve_point_block

    if intent.school_op in CURVE_POINT_OPS:
        return curve_point_block(intent, lines)
    from app.modules.math.tools.school import apply_calculus_extension

    extended = apply_calculus_extension(intent, settings, lines)
    if extended is not None:
        return extended
    if intent.school_op in _SCHOOL_ONLY_OPS:
        return None
    operation = _CALCULUS_OPERATIONS.get(intent.operation)
    return operation(intent, intent.expr, settings, lines) if operation else None


def _no_closed_form(out: MathExprResult, lines: list[str]) -> VerifiedMathBlock:
    lines.append(f"No closed-form result (got: {out.latex}).")
    return VerifiedMathBlock(text="\n".join(lines))


def _finish_operation(
    out: MathExprResult,
    lines: list[str],
    answer: str,
    trace: list[KeyStep] | tuple[KeyStep, ...] = (),
    given: str | None = None,
) -> VerifiedMathBlock:
    # Verified worked steps (differentiation): copy these verbatim instead of
    # inventing a derivation — the model's self-derived steps were often wrong
    # even with a verified final answer.
    if out.steps:
        lines.extend(out.steps)
    else:
        lines.append(f"Result: {answer}")
    return _finish_with_answer(lines, answer, key_steps=trace, given_latex=given)


def _simplify(
    intent: MathIntent, expr: str, settings: Settings, lines: list[str]
) -> VerifiedMathBlock:
    out = math_solve.simplify_expression(expr, intent.variable)
    if not out.solved:
        return _no_closed_form(out, lines)
    block = _finish_operation(out, lines, out.latex)
    return replace(block, direct_reply=_simplification_direct_reply(intent, out.latex))


def _factor(
    intent: MathIntent, expr: str, settings: Settings, lines: list[str]
) -> VerifiedMathBlock:
    out = math_solve.factor_expression(expr, intent.variable)
    if not out.solved:
        return _no_closed_form(out, lines)
    return _finish_operation(out, lines, out.latex)


def _expand(
    intent: MathIntent, expr: str, settings: Settings, lines: list[str]
) -> VerifiedMathBlock:
    out = math_solve.expand_expression(expr, intent.variable)
    if not out.solved:
        return _no_closed_form(out, lines)
    return _finish_operation(out, lines, out.latex)


def _differentiate(
    intent: MathIntent, expr: str, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    point = intent.evaluation_point
    if point is not None and (intent.derivative_order or 1) > 1:
        return _higher_derivative_at_point(intent, lines)
    if point is not None:
        return _derivative_at_point(intent, expr, point, lines)
    trace: list[KeyStep] = []
    given: str | None = None
    if intent.derivative_order in (None, 1):
        trace, given = derivative_trace(expr[: settings.math_max_expr_length], intent.variable)
    out = math_solve.differentiate_expression(expr, intent.variable, intent.derivative_order)
    if not out.solved:
        return _no_closed_form(out, lines)
    answer = out.latex
    block = _finish_operation(out, lines, answer, trace, given)
    if trace:
        from app.modules.math.tools.lesson import format_equation_lesson_reply

        return replace(block, direct_reply=format_equation_lesson_reply(block))
    steps = tuple(text_line(step) for step in out.steps)
    given_lines = (math_line(given),) if given else ()
    return replace(
        block,
        direct_reply=render_workout(Workout(find=given_lines, steps=steps), answer),
    )


def _integrate(
    intent: MathIntent, expr: str, settings: Settings, lines: list[str]
) -> VerifiedMathBlock:
    out, trace, given, checked_answer = _integral(intent, expr, settings)
    improper = _improper_integral_block(out, lines)
    if improper is not None:
        return improper
    if not out.solved:
        return _no_closed_form(out, lines)
    answer = out.latex
    if intent.integral_lower is None and _is_log_over_x_integral(expr, intent.variable):
        answer = rf"\ln\left|\ln\left({intent.variable}\right)\right| + C"
        direct = _log_over_x_reply(intent.variable, answer)
        return replace(_finish_with_answer(lines, answer), direct_reply=direct)
    if intent.integral_lower is None:
        # The service computes one antiderivative; the user's indefinite
        # integral asks for the family, including on the direct reply path.
        answer += " + C"
    block = _finish_operation(out, lines, answer, trace, given)
    if intent.integral_lower is not None and intent.integral_upper is not None:
        return replace(block, direct_reply=_definite_integral_reply(intent, expr, answer))
    if not trace:
        return block
    # An antiderivative the trace found (checked by differentiating back) may
    # differ from SymPy's by a constant; the lesson ends on its own spelling.
    return replace(block, given_label="Find", display_answer=checked_answer)


_CALCULUS_OPERATIONS: dict[str, _Operation] = {
    "simplify": _simplify,
    "differentiate": _differentiate,
    "integrate": _integrate,
    "factor": _factor,
    "expand": _expand,
}


def _simplification_direct_reply(intent: MathIntent, answer: str) -> str:
    """Render a verified simplification and preserve the original domain."""
    from sympy import Eq, Symbol, latex, preorder_traversal, solve

    names = math_solve.guess_variables(intent.expr or "") or [intent.variable]
    original = math_solve._parse_expression(intent.expr or "", names, evaluate=False)
    display_original = math_solve._parse_expression(intent.expr or "", names)
    parsed = math_solve._parse_expression(intent.expr or "", names, real=True)
    restrictions: list[str] = []
    seen_symmetric: set[tuple[str, str]] = set()
    denominator_bases = [
        node.base
        for node in preorder_traversal(original)
        if getattr(node, "is_Pow", False)
        and getattr(node.exp, "is_number", False)
        and bool(node.exp < 0)
    ]
    for name in names:
        sym = next((item for item in original.free_symbols if str(item) == name), Symbol(name))
        excluded_values: list[Any] = []
        for denominator in denominator_bases:
            if sym not in getattr(denominator, "free_symbols", set()):
                continue
            try:
                for value in solve(Eq(denominator, 0), sym):
                    if value not in excluded_values:
                        excluded_values.append(value)
            except Exception:  # noqa: S112 - one unsolved symbolic factor is non-fatal
                continue
        for value in sorted(excluded_values, key=str):
            if getattr(value, "is_Symbol", False):
                first, second = sorted((str(sym), str(value)))
                pair = (first, second)
                if pair in seen_symmetric:
                    continue
                seen_symmetric.add(pair)
            restrictions.append(rf"{latex(sym)} \ne {latex(value)}")
    # As typed: ``log(100)`` evaluates to 2 at parse, which would show ``2 = 2``.
    written = written_side(intent.expr or "", names)
    shown = written[1] if written else latex(display_original)
    steps = [math_line(f"{shown} = {answer}", "simplify")]
    if restrictions:
        steps.append(math_line(r",\; ".join(restrictions), "excluded by the original expression"))
    elif "Abs(" in str(parsed):
        steps.append(
            text_line("a principal square root is never negative, so keep the absolute value")
        )
    workout = Workout(given=(math_line(shown),), steps=tuple(steps))
    return render_workout(workout, answer)


def _verified_function_analysis(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    from app.modules.math import function_analysis

    if not intent.expr or intent.school_op not in _FUNCTION_ANALYSIS_OPS:
        return None
    if intent.school_op == "function_domain":
        answer = function_analysis.real_domain(intent.expr, intent.variable)
        lines.append(f"Real domain: {answer}")
    elif intent.school_op == "function_range":
        answer = function_analysis.real_range(intent.expr, intent.variable)
        lines.append(f"Real range: {answer}")
    elif intent.school_op == "function_inverse":
        answer = function_analysis.inverse_function(intent.expr, intent.variable)
        lines.append(f"Inverse function: {answer}")
    elif intent.school_op == "function_symmetry":
        answer = function_analysis.symmetry(intent.expr, intent.variable)
        lines.append(f"Symmetry: {answer}")
    else:
        if not intent.expr2:
            return None
        answer = function_analysis.compose_functions(intent.expr, intent.expr2, intent.variable)
        lines.append(f"Composition: {answer}")
    return _finish_with_answer(lines, answer)

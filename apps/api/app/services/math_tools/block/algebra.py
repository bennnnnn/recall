"""Equation / inequality / system / Newton verified blocks."""

from __future__ import annotations

from dataclasses import replace

from app.core.config import Settings
from app.models.schemas.math import (
    EquationInput,
    MathIntent,
    NewtonMethodInput,
    SystemOfEquationsInput,
)
from app.services import math_service
from app.services.math_tools.block.common import (
    VerifiedMathBlock,
    _diagram_block,
    _finish_with_answer,
    _format_equation_answer,
    _format_system_answer,
)


def _verified_block_equation(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.lhs and intent.rhs):
        return None
    eq = EquationInput(
        lhs=intent.lhs[: settings.math_max_expr_length],
        rhs=intent.rhs[: settings.math_max_expr_length],
        variables=[intent.variable],
    )
    result = math_service.solve_equation(eq)
    lines.extend(result.steps)
    answer = _format_equation_answer(
        result.canonical_solutions_latex or result.solutions_latex,
        result.solution_kind,
    )
    return _finish_with_answer(lines, answer)


def _verified_block_inequality(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.lhs and intent.rhs and intent.comparator):
        return None
    max_len = settings.math_max_expr_length
    if intent.lower is not None and intent.comparator_upper is not None:
        result = math_service.solve_compound_inequality(
            intent.lower[:max_len],
            intent.comparator,
            intent.lhs[:max_len],
            intent.comparator_upper,
            intent.rhs[:max_len],
            intent.variable,
        )
    else:
        result = math_service.solve_inequality(
            intent.lhs[:max_len],
            intent.rhs[:max_len],
            intent.variable,
            intent.comparator,
        )
    lines.extend(result.steps)
    answer = _format_equation_answer(result.solutions_latex, result.solution_kind)
    # Reconstruct the inequality text ("x > 4" / "1 < x < 5") so the
    # number-line builder can render the solution set as a diagram. The
    # model often emits a malformed ```graph fence for the number line and
    # validate_math_fences then shows "Could not render that diagram.";
    # attaching the verified number_line as canonical_fence lets the
    # post-stream rewriter replace that broken fence with the real one.
    if intent.lower is not None and intent.comparator_upper is not None:
        ineq_text = (
            f"{intent.lower} {intent.comparator} {intent.lhs} "
            f"{intent.comparator_upper} {intent.rhs}"
        )
    else:
        ineq_text = f"{intent.lhs} {intent.comparator} {intent.rhs}"
    line_spec = math_service.number_line_spec_from_expr(ineq_text[:max_len], intent.variable)
    if line_spec is not None:
        return _diagram_block(lines, line_spec, answer)
    return _finish_with_answer(lines, answer)


def _verified_block_system(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.system_equations:
        return None
    capped_equations = [
        (
            lhs[: settings.math_max_expr_length],
            rhs[: settings.math_max_expr_length],
        )
        for lhs, rhs in intent.system_equations
    ]
    sys_input = SystemOfEquationsInput(
        equations=capped_equations,
        variables=intent.system_variables or ["x", "y"],
    )
    sys_result = math_service.solve_system(sys_input)
    lines.extend(sys_result.steps)
    answer = _format_system_answer(sys_result.solutions, sys_result.solution_kind)
    return _finish_with_answer(lines, answer)


def _verified_block_numerical_method(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.newton_guess is not None):
        return None
    newton_input = NewtonMethodInput(
        expr=intent.expr[: settings.math_max_expr_length],
        variable=intent.variable,
        initial_guess=intent.newton_guess,
    )
    newton_result = math_service.newton_method(newton_input)
    lines.append(f"Newton's method for {newton_input.expr} = 0, x0 = {newton_input.initial_guess}:")
    for step in newton_result.iterations:
        lines.append(f"  n={step.n}: x_{step.n} = {step.x_n}, f(x_{step.n}) = {step.f_x_n}")
    if not newton_result.converged or newton_result.root is None:
        lines.append(
            f"Did not converge within {newton_result.iterations_used} iterations "
            "(the derivative may have vanished, or more iterations are needed)."
        )
        # No ```answer — post-stream must not force a root that was not found.
        return VerifiedMathBlock(
            text="\n".join(lines),
            newton_input=newton_input.model_copy(deep=True),
            newton_result=newton_result.model_copy(deep=True),
        )

    lines.append(
        f"Converged after {newton_result.iterations_used} iterations: root ≈ {newton_result.root}"
    )
    answer = f"{newton_result.root:g}"
    return replace(
        _finish_with_answer(lines, answer),
        newton_input=newton_input.model_copy(deep=True),
        newton_result=newton_result.model_copy(deep=True),
    )

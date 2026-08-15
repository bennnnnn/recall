"""Equation / inequality / system / Newton verified blocks."""

from __future__ import annotations

from app.core.config import Settings
from app.models.math_schemas import (
    EquationInput,
    MathIntent,
    NewtonMethodInput,
    SystemOfEquationsInput,
)
from app.services import math_service
from app.services.math_tools.block.common import (
    VerifiedMathBlock,
    _answer_canonical,
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
    answer = _format_equation_answer(result.solutions_latex, result.solution_kind)
    lines.append(
        "Formula shape: INLINE $...$ for every step (never backticks around "
        "`$...$`; never ```math for step equations — those stream blank). "
        "A ```math fence is OK only for a standalone final display equation. "
        "Do NOT recompute the solutions. Show worked steps by COPYING the "
        "verified steps above verbatim — do NOT derive intermediate algebra "
        "yourself. Keep any spacing (e.g. \\quad) INSIDE the $...$ delimiters. "
        "End with this final-answer fence (copy verbatim):\n"
        f"```answer\n{answer}\n```"
    )
    return VerifiedMathBlock(
        text="\n".join(lines),
        canonical_fence=_answer_canonical(answer),
    )


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
    lines.append(
        "Formula shape: INLINE $...$ for the inequality and its solution "
        "set (never backticks around `$...$`). Do NOT recompute — copy the "
        "verified solution above verbatim. Render unions with \\lor "
        "(e.g. $x < -1 \\lor x > 1$) exactly as given. "
        "End with this final-answer fence (copy verbatim):\n"
        f"```answer\n{answer}\n```"
    )
    return VerifiedMathBlock(
        text="\n".join(lines),
        canonical_fence=_answer_canonical(answer),
    )


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
    lines.append(
        "Formula shape: INLINE $...$ for every step (never backticks around "
        "`$...$`; never ```math for step equations). Do NOT recompute the "
        "solutions. Show worked steps by COPYING the verified steps above "
        "verbatim — do NOT derive intermediate algebra yourself. "
        "End with this final-answer fence (copy verbatim):\n"
        f"```answer\n{answer}\n```"
    )
    return VerifiedMathBlock(
        text="\n".join(lines),
        canonical_fence=_answer_canonical(answer),
    )


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
            "(the derivative may have vanished, or more iterations are needed) — "
            "do NOT present a root as found."
        )
        lines.append(
            "Do NOT recompute or invent different iteration values. Show the "
            "worked steps by COPYING the verified iteration table above verbatim."
        )
        # No ```answer — post-stream must not force a root that was not found.
        return VerifiedMathBlock(text="\n".join(lines))

    lines.append(
        f"Converged after {newton_result.iterations_used} iterations: root ≈ {newton_result.root}"
    )
    answer = f"{newton_result.root:g}"
    return _finish_with_answer(
        lines,
        answer,
        preface=(
            "Do NOT recompute or invent different iteration values. Show the "
            "worked steps by COPYING the verified iteration table above verbatim. "
            "End with this final-answer fence (copy verbatim):"
        ),
    )

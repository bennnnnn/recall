"""Taylor, partial, and ODE extractor plus the calculus block extension."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.modules.math import match as mtm
from app.modules.math import school as math_school
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer

_ODE_START_RE = re.compile(r"dy\s*/\s*dx|d\^?2\s*y\s*/\s*dx\^?2|[A-Za-z]'")
_ODE_INITIAL_RE = re.compile(
    r"\b([A-Za-z])\s*\(\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*\)\s*=\s*"
    r"([+-]?(?:\d+(?:\.\d+)?|\.\d+))\b"
)


def _ode_equation(cleaned: str) -> str | None:
    """Span from the first derivative mark through the rhs. Linear scan.

    Accepts the bare first-order forms (``dy/dx = 2y``) and the general linear
    ones (``y'' + y = 0``, ``y'' + 3y' + 2y = 0``). Everything between the
    derivative and the ``=`` must be math: ``Find dy/dx if y = x^2`` is a
    derivative ask, not an ODE, and the word ``if`` is what says so.
    """
    from app.modules.math.tools.helpers import _strip_trailing_filler

    match = _ODE_START_RE.search(cleaned)
    if match is None:
        return None
    rest = cleaned[match.start() :]
    eq_at = rest.find("=")
    if eq_at == -1:
        return None
    between = rest[:eq_at]
    for token in between.split():
        word = token.strip(".,?!:;()[]").lower()
        if word.isalpha() and len(word) >= 2:
            return None
    return _strip_trailing_filler(rest)


def _extract_taylor_or_ode(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    taylor_ok = (
        "taylor of " in lower or "maclaurin" in lower or ("taylor" in lower and "series" in lower)
    )
    if taylor_ok:
        expr = mtm.graph_expr(cleaned) or cleaned
        n = mtm.number_after(cleaned, "order") or mtm.number_after(cleaned, "degree") or 5
        point = "0"
        if "maclaurin" not in lower and "at " in lower:
            pt = mtm.number_after(cleaned, "at")
            if pt is not None:
                point = f"{pt:g}"
        # pull expr after "of "
        idx = lower.find(" of ")
        if idx != -1:
            rest = cleaned[idx + 4 :]
            for stop in (" at ", " order", " degree", " around"):
                sidx = rest.lower().find(stop)
                if sidx != -1:
                    rest = rest[:sidx]
            expr = rest.strip()
        return MathIntent(
            kind="calculus",
            operation="taylor",
            expr=expr,
            taylor_n=int(n),
            limit_point=point,
            variable="x",
        )
    if "partial" in lower and (
        "partial of " in lower
        or "partial derivative" in lower
        or " wrt" in lower
        or "with respect to" in lower
    ):
        var = "x"
        if "wrt" in lower:
            after = cleaned.lower().find("wrt")
            rest = cleaned[after + 3 :].strip()
            if rest:
                var = rest[0]
        elif "with respect to" in lower:
            after = lower.find("with respect to")
            rest = cleaned[after + len("with respect to") :].strip()
            if rest:
                var = rest[0]
        idx = lower.find(" of ")
        expr = cleaned[idx + 4 :] if idx != -1 else cleaned
        for stop in (" wrt", " with respect"):
            sidx = expr.lower().find(stop)
            if sidx != -1:
                expr = expr[:sidx]
        return MathIntent(
            kind="calculus",
            operation="partial",
            expr=expr.strip(),
            variable=var,
        )
    if "dy/dx" in lower or "'" in cleaned or "dsolve" in lower:
        initial = _ODE_INITIAL_RE.search(cleaned)
        ode_source = cleaned
        initial_x: str | None = None
        initial_y: str | None = None
        if initial is not None:
            initial_x, initial_y = initial.group(2), initial.group(3)
            ode_source = cleaned[: initial.start()].rstrip(" ,;.")
            for suffix in (" with", " where", " and"):
                if ode_source.lower().endswith(suffix):
                    ode_source = ode_source[: -len(suffix)].rstrip()
                    break
        ode_eq = _ode_equation(ode_source)
        if ode_eq is None:
            return None
        return MathIntent(
            kind="calculus",
            operation="dsolve",
            expr=ode_eq,
            variable="x",
            initial_x=initial_x,
            initial_y=initial_y,
        )
    return None


def apply_calculus_extension(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.operation == "taylor" and intent.expr:
        out = math_school.taylor_series(
            intent.expr, intent.variable, intent.limit_point or "0", intent.taylor_n or 5
        )
        lines.append(f"Taylor: {out.latex}")
        return _finish_with_answer(lines, out.latex)
    if (
        intent.operation == "partial"
        and intent.expr
        and intent.school_op
        not in {
            "gradient",
            "directional",
            "divergence",
            "curl",
        }
    ):
        out = math_school.partial_derivative(intent.expr, intent.variable)
        lines.append(f"Partial: {out.latex}")
        return _finish_with_answer(lines, out.latex)
    if intent.operation == "dsolve" and intent.expr:
        out = math_school.solve_ode(
            intent.expr,
            intent.variable,
            initial_x=intent.initial_x,
            initial_y=intent.initial_y,
        )
        lines.append(f"ODE: {out.latex}")
        block = _finish_with_answer(lines, out.latex)
        if not out.steps:
            return block
        labels = ["Separate variables", "Integrate both sides", "Write the general solution"]
        if len(out.steps) == 4:
            labels.append("Use the initial condition")
        chunks = [f"**Given:** ${intent.expr}$"]
        chunks.extend(
            f"**{index}. {label}**\n${formula}$"
            for index, (label, formula) in enumerate(zip(labels, out.steps, strict=True), start=1)
        )
        chunks.append(f"```answer\n{out.latex}\n```\n")
        return replace(block, direct_reply="\n\n".join(chunks))
    if intent.operation == "critical_points" and intent.expr:
        out = math_school.critical_points(intent.expr, intent.variable)
        lines.append(f"Critical points: {out.latex}")
        return _finish_with_answer(lines, out.latex)
    if intent.school_op == "identity" and intent.lhs and intent.rhs:
        holds, condition, counterexample = math_school.analyze_identity(intent.lhs, intent.rhs)
        if holds:
            lines.append("Identity holds for every real value in its domain.")
            return _finish_with_answer(lines, "true")
        lines.append("The equality is not an identity over the real numbers.")
        details: list[str] = []
        if condition:
            lines.append(f"Equality set: {condition}")
            details.append(f"It holds only for ${condition}$.")
        if counterexample:
            lines.append(f"Counterexample: {counterexample}")
            details.append(f"For example, ${counterexample}$.")
        answer = r"\text{false}"
        direct = "**No — it is not always true.**"
        if details:
            direct += "\n\n" + " ".join(details)
        direct += f"\n\n```answer\n{answer}\n```\n"
        return replace(
            _finish_with_answer(lines, answer),
            direct_reply=direct,
            direct_answer_binding=answer,
        )
    from app.modules.math import formulas as math_formulas

    if intent.school_op == "average_value" and intent.expr and intent.integral_lower is not None:
        if intent.integral_upper is None:
            return None
        answer = math_formulas.average_value(
            intent.expr, intent.variable, intent.integral_lower, intent.integral_upper
        )
        lines.append(f"Average value: {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "linear_approx" and intent.expr and intent.limit_point is not None:
        answer = math_formulas.linear_approximation(
            intent.expr, intent.variable, intent.limit_point
        )
        lines.append(f"Linear approximation: {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "gradient" and intent.expr:
        answer = math_formulas.gradient_of(intent.expr)
        lines.append(f"Gradient: {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "directional" and intent.expr and intent.vec_a and intent.vec_b:
        answer = math_formulas.directional_derivative(
            intent.expr, tuple(intent.vec_a), intent.vec_b
        )
        lines.append(f"Directional derivative: {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "divergence" and intent.expr:
        answer = math_formulas.divergence_of(intent.expr)
        lines.append(f"Divergence: {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "curl" and intent.expr:
        answer = math_formulas.curl_of(intent.expr)
        lines.append(f"Curl: {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "implicit" and intent.lhs and intent.rhs:
        from app.modules.math import solve as math_solve

        answer = math_formulas.implicit_derivative(intent.lhs, intent.rhs)
        lines.append(f"dy/dx = {answer}")
        block = _finish_with_answer(lines, answer)
        try:
            from sympy import Derivative, Function, Symbol, diff, latex

            independent = Symbol(intent.variable or "x", real=True)
            dependent = Symbol("y", real=True)
            dependent_fn = Function("y")(independent)
            left = math_solve._parse_expression(
                intent.lhs, [str(independent), "y"], real=True
            ).xreplace({dependent: dependent_fn})
            right = math_solve._parse_expression(
                intent.rhs, [str(independent), "y"], real=True
            ).xreplace({dependent: dependent_fn})
            marker = Symbol("DERIVATIVE_MARKER")
            left_d = diff(left, independent).xreplace(
                {Derivative(dependent_fn, independent): marker, dependent_fn: dependent}
            )
            right_d = diff(right, independent).xreplace(
                {Derivative(dependent_fn, independent): marker, dependent_fn: dependent}
            )

            def _derivative_tex(value: Any) -> str:
                return (
                    latex(value)
                    .replace("DERIVATIVE_{MARKER}", r"\frac{dy}{dx}")
                    .replace("DERIVATIVE\\_MARKER", r"\frac{dy}{dx}")
                )

            differentiated = f"{_derivative_tex(left_d)} = {_derivative_tex(right_d)}"
            direct = (
                f"**Given:** ${latex(left.xreplace({dependent_fn: dependent}))} = "
                f"{latex(right.xreplace({dependent_fn: dependent}))}$\n\n"
                "**1. Differentiate both sides with respect to $x$**\n"
                f"${differentiated}$\n\n"
                "**2. Collect the $\\frac{dy}{dx}$ terms and solve**\n"
                f"$\\frac{{dy}}{{dx}} = {answer}$\n\n"
                f"```answer\n\\frac{{dy}}{{dx}} = {answer}\n```\n"
            )
            return replace(block, direct_reply=direct)
        except Exception:
            return block
    return None

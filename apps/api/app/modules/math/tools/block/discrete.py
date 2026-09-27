"""Calculus / stats / discrete / matrix verified blocks."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.core.config import Settings
from app.models.schemas.math import (
    CombinatoricsInput,
    MathIntent,
    MatrixInput,
    NumberTheoryInput,
    NumberTheoryResult,
    StatisticsInput,
)
from app.modules.math import solve as math_solve
from app.modules.math.solve.derivative_steps import derivative_trace
from app.modules.math.solve.integral_steps import integral_trace
from app.modules.math.solve.key_steps import KeyStep
from app.modules.math.tools.calculus_outcome import infinite_integral_note, undefined_integral_note
from app.services.solving import (
    VerifiedMathBlock,
    _finish_with_answer,
)

_FUNCTION_ANALYSIS_OPS = {
    "function_domain",
    "function_range",
    "function_inverse",
    "function_compose",
    "function_symmetry",
}
_CALCULUS_APPLICATION_OPS = {
    "area_between_curves",
    "arc_length",
    "volume_revolution_x",
    "volume_revolution_y",
}
_BIVARIATE_STATS_OPS = {
    "correlation",
    "covariance",
    "sample_covariance",
    "linear_regression",
}


def _verified_calculus_application(
    intent: MathIntent, lines: list[str]
) -> VerifiedMathBlock | None:
    from app.modules.math import calculus_applications as apps

    op = intent.school_op
    if op not in _CALCULUS_APPLICATION_OPS:
        return None
    if not intent.expr or intent.integral_lower is None or intent.integral_upper is None:
        return None

    if op == "area_between_curves":
        if not intent.expr2:
            return None
        answer = apps.area_between_curves(
            intent.expr, intent.expr2, intent.integral_lower, intent.integral_upper, intent.variable
        )
        lines.append(f"Area between the curves: {answer}")
    elif op == "arc_length":
        answer = apps.arc_length(
            intent.expr, intent.integral_lower, intent.integral_upper, intent.variable
        )
        lines.append(f"Arc length: {answer}")
    else:
        axis = "x" if op.endswith("_x") else "y"
        answer = apps.volume_of_revolution(
            intent.expr, intent.integral_lower, intent.integral_upper, axis, intent.variable
        )
        lines.append(f"Volume about the {axis}-axis: {answer}")
    block = _finish_with_answer(lines, answer)
    from sympy import (
        Eq,
        FiniteSet,
        Interval,
        Symbol,
        diff,
        integrate,
        latex,
        simplify,
        solveset,
        sqrt,
    )

    sym = Symbol(intent.variable, real=True)
    parsed = math_solve._parse_expression(intent.expr, [intent.variable], real=True)
    low, high = intent.integral_lower, intent.integral_upper
    if op == "area_between_curves" and intent.expr2:
        second = math_solve._parse_expression(intent.expr2, [intent.variable], real=True)
        difference = simplify(parsed - second)
        low_expr = math_solve._parse_expression(str(low), [], real=True)
        high_expr = math_solve._parse_expression(str(high), [], real=True)
        roots = solveset(Eq(difference, 0), sym, domain=Interval(low_expr, high_expr))
        interior_roots = []
        if isinstance(roots, FiniteSet):
            interior_roots = [root for root in roots if root != low_expr and root != high_expr]
        midpoint = simplify((low_expr + high_expr) / 2)
        sample = difference.subs(sym, midpoint)
        single_order = (
            isinstance(roots, FiniteSet) and not interior_roots and sample.is_real is True
        )
        if single_order and sample.is_nonnegative is True:
            upper, lower_curve, gap = parsed, second, difference
        elif single_order and sample.is_nonpositive is True:
            upper, lower_curve, gap = second, parsed, -difference
        else:
            upper = lower_curve = None
            gap = None
        if gap is not None:
            antiderivative = integrate(gap, sym)
            direct = (
                "**1. Identify the upper curve**\n\n"
                f"On $[{low},{high}]$, ${latex(upper)} \\ge {latex(lower_curve)}$, "
                f"so use upper minus lower.\n\n"
                "**2. Set up the area**\n\n"
                f"$A = \\int_{{{low}}}^{{{high}}} \\left({latex(gap)}\\right)"
                f"\\,d{intent.variable}$\n\n"
                "**3. Find an antiderivative**\n\n"
                f"$A = \\left[{latex(antiderivative)}\\right]_{{{low}}}^{{{high}}}$\n\n"
                "**4. Evaluate the endpoints**\n\n"
                f"$A = {latex(antiderivative.subs(sym, high_expr))}"
                f" - \\left({latex(antiderivative.subs(sym, low_expr))}\\right)$\n\n"
                f"$A = {answer}$\n\n"
            )
        else:
            direct = (
                "**1. The curves change order, so use absolute difference**\n\n"
                f"$A = \\int_{{{low}}}^{{{high}}} \\left|{latex(difference)}\\right|"
                f"\\,d{intent.variable}$\n\n"
                f"**2. Evaluate the integral**\n\n$A = {answer}$\n\n"
            )
    elif op == "arc_length":
        derivative = diff(parsed, sym)
        integrand = sqrt(1 + derivative**2)
        direct = (
            "**Differentiate the curve**\n"
            f"$y' = {latex(derivative)}$\n\n"
            "**Arc-length formula**\n"
            f"$L = \\int_{{{low}}}^{{{high}}} \\sqrt{{1+(y')^2}}\\,d{intent.variable}"
            f" = \\int_{{{low}}}^{{{high}}} {latex(integrand)}\\,d{intent.variable}$\n\n"
            f"**Evaluate**\n$L = {answer}$\n\n"
        )
    else:
        axis = "x" if op.endswith("_x") else "y"
        if axis == "x":
            cross_section = simplify(parsed**2)
            antiderivative = integrate(cross_section, sym)
            low_expr = math_solve._parse_expression(str(low), [], real=True)
            high_expr = math_solve._parse_expression(str(high), [], real=True)
            setup = (
                rf"V = \pi\int_{{{low}}}^{{{high}}}\left({latex(parsed)}\right)^2"
                rf"\,d{intent.variable}"
            )
            working = (
                "**2. Simplify the cross-sectional area**\n\n"
                f"$\\left({latex(parsed)}\\right)^2 = {latex(cross_section)}$\n\n"
                "**3. Integrate**\n\n"
                f"$V = \\pi\\left[{latex(antiderivative)}\\right]_{{{low}}}^{{{high}}}$\n\n"
                "**4. Evaluate the endpoints**\n\n"
                f"$V = \\pi\\left({latex(antiderivative.subs(sym, high_expr))}"
                f" - {latex(antiderivative.subs(sym, low_expr))}\\right)$\n\n"
            )
        else:
            shell_integrand = simplify(sym * parsed)
            antiderivative = integrate(shell_integrand, sym)
            low_expr = math_solve._parse_expression(str(low), [], real=True)
            high_expr = math_solve._parse_expression(str(high), [], real=True)
            setup = (
                rf"V = 2\pi\int_{{{low}}}^{{{high}}}{intent.variable}"
                rf"\left({latex(parsed)}\right)\,d{intent.variable}"
            )
            working = (
                "**2. Simplify the shell integrand**\n\n"
                f"${intent.variable}\\left({latex(parsed)}\\right) = {latex(shell_integrand)}$\n\n"
                "**3. Integrate**\n\n"
                f"$V = 2\\pi\\left[{latex(antiderivative)}\\right]_{{{low}}}^{{{high}}}$\n\n"
                "**4. Evaluate the endpoints**\n\n"
                f"$V = 2\\pi\\left({latex(antiderivative.subs(sym, high_expr))}"
                f" - {latex(antiderivative.subs(sym, low_expr))}\\right)$\n\n"
            )
        direct = (
            f"**1. Set up the {'disk' if axis == 'x' else 'shell'} method**\n\n"
            f"${setup}$\n\n"
            f"{working}"
            f"$V = {answer}$\n\n"
        )
    direct += f"```answer\n{answer}\n```\n"
    return replace(block, direct_reply=direct)


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
    body = f"**Simplify**\n${latex(display_original)} = {answer}$\n"
    if restrictions:
        body += (
            "\n**Restrictions from the original expression**\n$"
            + r",\; ".join(restrictions)
            + "$\n"
        )
    elif "Abs(" in str(parsed):
        body += (
            "\nThe principal square root is nonnegative, so the result is an "
            "absolute value, not simply the variable.\n"
        )
    return f"{body}\n```answer\n{answer}\n```\n"


def _is_log_over_x_integral(expr: str, variable: str) -> bool:
    from sympy import Symbol, log, simplify

    sym = Symbol(variable, real=True)
    try:
        parsed = math_solve._parse_expression(expr, [variable], real=True)
        return bool(simplify(parsed - 1 / (sym * log(sym))) == 0)
    except Exception:
        return False


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


def _verified_block_calculus(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.operation):
        return None
    if intent.school_op in _FUNCTION_ANALYSIS_OPS:
        return _verified_function_analysis(intent, lines)
    if intent.school_op in _CALCULUS_APPLICATION_OPS:
        return _verified_calculus_application(intent, lines)
    from app.modules.math.tools.school import apply_calculus_extension

    extended = apply_calculus_extension(intent, settings, lines)
    if extended is not None:
        return extended
    if intent.school_op in {
        "average_value",
        "linear_approx",
        "gradient",
        "directional",
        "divergence",
        "curl",
        "implicit",
    }:
        return None
    if intent.school_op == "identity":
        return None
    trace: list[KeyStep] = []
    given: str | None = None
    checked_answer: str | None = None
    if intent.operation == "simplify":
        out = math_solve.simplify_expression(intent.expr, intent.variable)
    elif intent.operation == "differentiate":
        if intent.evaluation_point is not None:
            out = math_solve.differentiate_at_point(
                intent.expr, intent.variable, intent.evaluation_point
            )
            point_tex = intent.evaluation_point
            lines.extend(out.steps)
            answer = out.latex
            direct = (
                f"At ${intent.variable}={point_tex}$, {out.steps[0]}\n\n```answer\n{answer}\n```\n"
            )
            return replace(
                _finish_with_answer(lines, answer),
                direct_reply=direct,
                direct_requires_calculus_guard=True,
            )
        if intent.derivative_order in (None, 1):
            trace, given = derivative_trace(
                intent.expr[: settings.math_max_expr_length], intent.variable
            )
        out = math_solve.differentiate_expression(
            intent.expr, intent.variable, intent.derivative_order
        )
    elif intent.operation == "integrate":
        if (
            intent.integral_lower is not None
            and intent.integral_upper is not None
            and intent.integral_lower2 is not None
            and intent.integral_upper2 is not None
            and intent.integral_lower3 is not None
            and intent.integral_upper3 is not None
        ):
            out = math_solve.integrate_triple(
                intent.expr,
                intent.variable,
                intent.integral_lower,
                intent.integral_upper,
                intent.variable2 or "y",
                intent.integral_lower2,
                intent.integral_upper2,
                intent.variable3 or "z",
                intent.integral_lower3,
                intent.integral_upper3,
            )
        elif (
            intent.integral_lower is not None
            and intent.integral_upper is not None
            and intent.integral_lower2 is not None
            and intent.integral_upper2 is not None
        ):
            out = math_solve.integrate_double(
                intent.expr,
                intent.variable,
                intent.integral_lower,
                intent.integral_upper,
                intent.variable2 or "y",
                intent.integral_lower2,
                intent.integral_upper2,
            )
        elif intent.integral_lower is not None and intent.integral_upper is not None:
            out = math_solve.integrate_definite(
                intent.expr,
                intent.variable,
                intent.integral_lower,
                intent.integral_upper,
            )
        else:
            out = math_solve.integrate_expression(intent.expr, intent.variable)
            trace, given, checked_answer = integral_trace(
                intent.expr[: settings.math_max_expr_length], intent.variable
            )
    elif intent.operation == "factor":
        out = math_solve.factor_expression(intent.expr, intent.variable)
    elif intent.operation == "expand":
        out = math_solve.expand_expression(intent.expr, intent.variable)
    else:
        return None
    if intent.operation == "integrate":
        undefined_note = undefined_integral_note(out.result)
        if undefined_note is not None:
            lines.append(undefined_note)
            return VerifiedMathBlock(
                text="\n".join(lines),
                direct_reply=(
                    "This ordinary improper integral does not converge. "
                    "A Cauchy principal value is a separate convention and was not requested."
                ),
            )
        infinite_note = infinite_integral_note(out.result)
        if infinite_note is not None:
            lines.append(infinite_note)
            direction = "+\u221e" if out.result == "oo" else "\u2212\u221e"
            message = (
                f"This improper integral diverges to {direction}; "
                "it does not converge to a finite value."
            )
            return VerifiedMathBlock(text="\n".join(lines), direct_reply=message)
    if not out.solved:
        lines.append(f"No closed-form result (got: {out.latex}).")
        return VerifiedMathBlock(text="\n".join(lines))
    answer = out.latex
    if (
        intent.operation == "integrate"
        and intent.integral_lower is None
        and _is_log_over_x_integral(intent.expr, intent.variable)
    ):
        answer = rf"\log\left|\log\left({intent.variable}\right)\right| + C"
        direct = (
            "**Substitute**\n"
            f"$u = \\log({intent.variable}), \\quad du = \\frac{{1}}{{{intent.variable}}}"
            f"\\,d{intent.variable}$\n\n"
            "**Integrate**\n"
            r"$\int \frac{1}{u}\,du = \log|u| + C$"
            "\n\n**Substitute back**\n"
            f"${answer}$\n\n"
            f"For real values, the domain is ${intent.variable}>0$ with "
            f"${intent.variable}\\ne1$.\n\n"
            f"```answer\n{answer}\n```\n"
        )
        return replace(_finish_with_answer(lines, answer), direct_reply=direct)
    if intent.operation == "integrate" and intent.integral_lower is None:
        # The service computes one antiderivative; the user's indefinite
        # integral asks for the family, including on the direct reply path.
        answer += " + C"
    # Verified worked steps (differentiation): copy these verbatim instead of
    # inventing a derivation — the model's self-derived steps were often wrong
    # even with a verified final answer.
    if out.steps:
        lines.extend(out.steps)
    else:
        lines.append(f"Result: {answer}")
    block = _finish_with_answer(lines, answer, key_steps=trace, given_latex=given)
    if (
        intent.operation == "integrate"
        and intent.integral_lower is not None
        and intent.integral_upper is not None
    ):
        from sympy import latex

        parsed = math_solve._parse_expression(intent.expr, [intent.variable], real=True)
        direct = (
            "**Set up the definite integral**\n"
            f"$\\int_{{{intent.integral_lower}}}^{{{intent.integral_upper}}} "
            f"{latex(parsed)}\\,d{intent.variable}$\n\n"
            "**Evaluate (using endpoint limits if the integral is improper)**\n"
            f"$= {answer}$\n\n"
            f"```answer\n{answer}\n```\n"
        )
        return replace(block, direct_reply=direct)
    if intent.operation == "simplify":
        return replace(block, direct_reply=_simplification_direct_reply(intent, answer))
    if intent.operation == "differentiate":
        chunks: list[str] = []
        if given:
            chunks.append(f"**Find:** ${given}$")
        for index, step in enumerate(trace, start=1):
            chunks.append(f"**{index}. {step.label}**\n${step.formula}$")
        if not trace:
            chunks.extend(out.steps)
        chunks.append(f"```answer\n{answer}\n```\n")
        return replace(block, direct_reply="\n\n".join(chunks))
    if not trace:
        return block
    # An antiderivative the trace found (checked by differentiating back) may
    # differ from SymPy's by a constant; the lesson ends on its own spelling.
    return replace(block, given_label="Find", display_answer=checked_answer)


def _verified_block_limit(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.limit_point is not None):
        return None
    limit_out = math_solve.compute_limit(
        intent.expr, intent.variable, intent.limit_point, intent.limit_direction
    )
    if limit_out.result == "zoo":
        message = "The two-sided limit does not exist because the one-sided limits disagree."
        lines.append(f"{message} Do not call it infinity.")
        return VerifiedMathBlock(text="\n".join(lines), direct_reply=message)
    lines.append(f"Result: {limit_out.latex}")
    if limit_out.is_infinite:
        lines.append(
            "This limit is infinite — preserve its sign, do not treat it as an ordinary "
            "finite number."
        )
    return _finish_with_answer(lines, limit_out.latex)


def _verified_block_series(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.series_start is not None and intent.series_end is not None):
        return None
    series_out = math_solve.evaluate_series_sum(
        intent.expr, intent.variable, intent.series_start, intent.series_end
    )
    if intent.school_op == "series_convergence":
        outcomes = [(intent.expr, series_out)]
        if intent.expr2:
            outcomes.append(
                (
                    intent.expr2,
                    math_solve.evaluate_series_sum(
                        intent.expr2,
                        intent.variable,
                        intent.series_start,
                        intent.series_end,
                    ),
                )
            )
        from sympy import latex

        rendered: list[str] = []
        for expression, outcome in outcomes:
            if outcome.is_convergent is False:
                status = "diverges"
            elif outcome.is_convergent is True and outcome.is_absolutely_convergent is False:
                status = "converges conditionally"
            elif outcome.is_convergent is True:
                status = "converges absolutely"
            else:
                status = "could not be classified"
            lines.append(f"Series {expression}: {status}; sum={outcome.latex}")
            parsed = math_solve._parse_expression(expression, [intent.variable], real=True)
            rendered.append(
                f"$\\sum_{{{intent.variable}=1}}^{{\\infty}} {latex(parsed)}$ {status}."
            )
        direct = "**Convergence**\n\n" + "\n\n".join(rendered)
        return VerifiedMathBlock(text="\n".join(lines), direct_reply=direct)
    lines.append(f"Result: {series_out.latex}")
    if series_out.is_convergent is not None:
        lines.append(
            f"Convergent: {series_out.is_convergent}"
            + (
                f" (absolutely convergent: {series_out.is_absolutely_convergent})"
                if series_out.is_absolutely_convergent is not None
                else ""
            )
            + "."
        )
    if series_out.is_convergent is False and not series_out.is_infinite:
        lines.append("This series diverges; it has no ordinary sum. Do not present a finite value.")
        return VerifiedMathBlock(
            text="\n".join(lines),
            direct_reply="This series diverges; it has no ordinary sum.",
        )
    if not series_out.solved:
        lines.append("The sum was not evaluated. Do not claim a closed-form answer.")
        return VerifiedMathBlock(text="\n".join(lines))
    if series_out.is_infinite:
        lines.append(
            "This series diverges to infinity — preserve its sign, do not "
            "treat it as an ordinary finite number."
        )
    return _finish_with_answer(lines, series_out.latex)


def _verified_block_statistics(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.stats_numbers or len(intent.stats_numbers) < 2:
        return None
    if intent.stats_op in _BIVARIATE_STATS_OPS:
        if not intent.stats_numbers_b or len(intent.stats_numbers_b) != len(intent.stats_numbers):
            first_count = len(intent.stats_numbers)
            second_count = len(intent.stats_numbers_b or [])
            message = (
                "The two data lists must have the same number of values before "
                f"{intent.stats_op.replace('_', ' ')} can be calculated "
                f"({first_count} values versus {second_count})."
            )
            lines.append(message)
            return VerifiedMathBlock(text="\n".join(lines), direct_reply=message)
        answer, steps = math_solve.compute_bivariate_statistics(
            intent.stats_op,
            intent.stats_numbers,
            intent.stats_numbers_b,
        )
        lines.extend(steps)
        return _finish_with_answer(lines, answer)

    result = math_solve.compute_statistics(StatisticsInput(numbers=intent.stats_numbers))
    lines.append(f"Data ({result.count} values): {', '.join(f'{v:g}' for v in result.numbers)}")
    sample_stdev = (
        f"{result.stdev_sample:g}" if result.stdev_sample is not None else "n/a (needs 2+ values)"
    )
    lines.append(
        f"mean={result.mean:g} median={result.median:g} mode={result.labels.get('mode', 'none')} "
        f"range={result.range:g} population variance={result.variance_population:g} "
        f"population stdev={result.stdev_population:g} sample stdev={sample_stdev}"
    )
    if intent.stats_op == "median":
        answer = result.labels["median"]
    elif intent.stats_op == "mode":
        answer = result.labels["mode"]
    elif intent.stats_op == "stdev":
        answer = result.labels["population_stdev"]
    elif intent.stats_op == "sample_stdev":
        answer = result.labels.get("sample_stdev", "n/a")
    elif intent.stats_op == "variance":
        answer = f"{result.variance_population:g}"
    elif intent.stats_op == "sample_variance":
        answer = f"{result.variance_sample:g}" if result.variance_sample is not None else "n/a"
    elif intent.stats_op == "range":
        answer = result.labels["range"]
    elif intent.stats_op in {"iqr", "quartiles", "percentile"}:
        from app.modules.math import formulas as math_formulas

        if intent.stats_op == "iqr":
            answer = math_formulas.interquartile_range(intent.stats_numbers)
        elif intent.stats_op == "quartiles":
            answer = math_formulas.quartiles(intent.stats_numbers)
        elif intent.combo_n is None:
            return None
        else:
            answer = math_formulas.percentile(intent.stats_numbers, intent.combo_n)
    else:
        answer = result.labels["mean"]
    return _finish_with_answer(
        lines,
        answer,
    )


def _format_number_theory_answer(result: NumberTheoryResult) -> str:
    """Short final for ```answer — matches the verified step language."""
    if result.operation == "factorize" and result.factors is not None:
        parts = [f"{p}^{{{e}}}" if e > 1 else f"{p}" for p, e in sorted(result.factors.items())]
        return " \\times ".join(parts)
    if result.operation == "is_prime" and result.result_bool is not None:
        return "prime" if result.result_bool else "not prime"
    if result.result_int is not None:
        return str(result.result_int)
    return result.steps[-1] if result.steps else ""


def _verified_block_combinatorics(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.combo_op is None or intent.combo_n is None:
        return None
    if intent.combo_op != "factorial" and intent.combo_k is None:
        return None
    result = math_solve.compute_combinatorics(
        CombinatoricsInput(operation=intent.combo_op, n=intent.combo_n, k=intent.combo_k)
    )
    lines.extend(result.steps)
    lines.append(f"Result: {result.result}")
    return _finish_with_answer(
        lines,
        str(result.result),
    )


def _verified_block_number_theory(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.numtheory_op == "crt":
        if not intent.vec_a or len(intent.vec_a) != 4:
            return None
        from app.modules.math.formulas import chinese_remainder

        a, m, b, n = (int(value) for value in intent.vec_a)
        answer = chinese_remainder(a, m, b, n)
        lines.append(f"x \\equiv {answer} \\pmod{{{int(intent.vec_a[1] * intent.vec_a[3])}}}")
        return _finish_with_answer(lines, answer)
    if intent.numtheory_op is None or intent.numtheory_a is None:
        return None
    result = math_solve.compute_number_theory(
        NumberTheoryInput(operation=intent.numtheory_op, a=intent.numtheory_a, b=intent.numtheory_b)
    )
    lines.extend(result.steps)
    answer = _format_number_theory_answer(result)
    if not answer:
        return VerifiedMathBlock(text="\n".join(lines))
    return _finish_with_answer(
        lines,
        answer,
    )


def _verified_block_matrix(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.matrix_op is None or not intent.matrix_rows:
        return None
    if intent.matrix_op == "inverse":
        determinant = math_solve.compute_matrix(
            MatrixInput(operation="determinant", rows=intent.matrix_rows)
        )
        if determinant.determinant == 0:
            lines.extend(determinant.steps)
            message = "This matrix has no inverse because its determinant is 0."
            lines.append(message)
            return VerifiedMathBlock(text="\n".join(lines), direct_reply=message)
    try:
        result = math_solve.compute_matrix(
            MatrixInput(
                operation=intent.matrix_op,
                rows=intent.matrix_rows,
                rows_b=intent.matrix_rows_b,
            )
        )
    except math_solve.MathServiceError as exc:
        if intent.matrix_op == "diagonalize" and "not diagonalizable" in str(exc).lower():
            message = (
                "This matrix is not diagonalizable: it does not have enough "
                "linearly independent eigenvectors."
            )
            lines.append(message)
            return VerifiedMathBlock(text="\n".join(lines), direct_reply=message)
        raise
    lines.extend(result.steps)
    if result.operation == "inverse" and result.inverse_latex:
        answer = result.inverse_latex
    elif result.result_latex:
        answer = result.result_latex
    elif result.determinant is not None:
        answer = f"{result.determinant:g}"
    else:
        return VerifiedMathBlock(text="\n".join(lines))
    return _finish_with_answer(
        lines,
        answer,
    )

"""Calculus / stats / discrete / matrix verified blocks."""

from __future__ import annotations

from app.core.config import Settings
from app.models.schemas.math import (
    CombinatoricsInput,
    MathIntent,
    MatrixInput,
    NumberTheoryInput,
    NumberTheoryResult,
    StatisticsInput,
)
from app.services import math_service
from app.services.math_tools.block.common import (
    VerifiedMathBlock,
    _finish_with_answer,
)
from app.services.math_tools.calculus_outcome import infinite_integral_note, undefined_integral_note


def _verified_block_calculus(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.operation):
        return None
    from app.services.math_tools.school import apply_calculus_extension

    extended = apply_calculus_extension(intent, settings, lines)
    if extended is not None:
        return extended
    if intent.operation == "simplify":
        out = math_service.simplify_expression(intent.expr, intent.variable)
    elif intent.operation == "differentiate":
        out = math_service.differentiate_expression(
            intent.expr, intent.variable, intent.derivative_order
        )
    elif intent.operation == "integrate":
        if intent.integral_lower is not None and intent.integral_upper is not None:
            out = math_service.integrate_definite(
                intent.expr,
                intent.variable,
                intent.integral_lower,
                intent.integral_upper,
            )
        else:
            out = math_service.integrate_expression(intent.expr, intent.variable)
    elif intent.operation == "factor":
        out = math_service.factor_expression(intent.expr, intent.variable)
    elif intent.operation == "expand":
        out = math_service.expand_expression(intent.expr, intent.variable)
    else:
        return None
    if intent.operation == "integrate":
        undefined_note = undefined_integral_note(out.result)
        if undefined_note is not None:
            lines.append(undefined_note)
            return VerifiedMathBlock(text="\n".join(lines))
        infinite_note = infinite_integral_note(out.result)
        if infinite_note is not None:
            lines.append(infinite_note)
    if not out.solved:
        lines.append(f"No closed-form result (got: {out.latex}).")
        return VerifiedMathBlock(text="\n".join(lines))
    answer = out.latex
    if intent.operation == "integrate" and intent.integral_lower is None:
        # The service computes one antiderivative; the user's indefinite
        # integral asks for the family, including on the direct reply path.
        answer += " + C"
    # Verified worked steps (differentiation): copy these verbatim instead of
    # inventing a derivation — the model's self-derived steps were often wrong
    # even with a verified final answer.
    if out.steps:
        lines.extend(out.steps)
        return _finish_with_answer(lines, answer)
    lines.append(f"Result: {answer}")
    return _finish_with_answer(lines, answer)


def _verified_block_limit(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.limit_point is not None):
        return None
    limit_out = math_service.compute_limit(
        intent.expr, intent.variable, intent.limit_point, intent.limit_direction
    )
    if limit_out.result == "zoo":
        lines.append(
            "The two-sided limit does not exist: the sides disagree. Do not call it infinity."
        )
        return VerifiedMathBlock(text="\n".join(lines))
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
    series_out = math_service.evaluate_series_sum(
        intent.expr, intent.variable, intent.series_start, intent.series_end
    )
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
        return VerifiedMathBlock(text="\n".join(lines))
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
    result = math_service.compute_statistics(StatisticsInput(numbers=intent.stats_numbers))
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
    result = math_service.compute_combinatorics(
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
    if intent.numtheory_op is None or intent.numtheory_a is None:
        return None
    result = math_service.compute_number_theory(
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
    result = math_service.compute_matrix(
        MatrixInput(operation=intent.matrix_op, rows=intent.matrix_rows)
    )
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

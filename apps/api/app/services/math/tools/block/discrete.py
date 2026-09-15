"""Calculus / stats / discrete / matrix verified blocks."""

from __future__ import annotations

from typing import cast

from app.core.config import Settings
from app.models.schemas.math import (
    CombinatoricsInput,
    MathIntent,
    MatrixInput,
    NumberTheoryInput,
    NumberTheoryResult,
    StatisticsInput,
)
from app.services.math import solve as math_solve
from app.services.math.tools.block.common import VerifiedMathBlock, _finish_with_answer
from app.services.math.tools.calculus_outcome import infinite_integral_note, undefined_integral_note


def _verified_block_calculus(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not (intent.expr and intent.operation):
        return None
    if intent.school_op in {
        "function_domain",
        "function_range",
        "function_inverse",
        "function_composition",
    }:
        from app.services.math.solve.advanced import FunctionFeature, compute_function_feature

        feature = cast(FunctionFeature, intent.school_op.removeprefix("function_"))
        answer, steps = compute_function_feature(
            feature, intent.expr, intent.variable, expr2=intent.expr2
        )
        lines.extend(steps)
        return _finish_with_answer(lines, answer)
    if intent.school_op in {"area_between_curves", "arc_length", "volume_revolution_x"}:
        if intent.integral_lower is None or intent.integral_upper is None:
            return None
        from app.services.math.solve.advanced import (
            CalculusApplicationFeature,
            compute_calculus_application,
        )

        application = cast(CalculusApplicationFeature, intent.school_op)
        answer, steps = compute_calculus_application(
            application,
            intent.expr,
            intent.variable,
            intent.integral_lower,
            intent.integral_upper,
            expr2=intent.expr2,
        )
        lines.extend(steps)
        return _finish_with_answer(lines, answer)

    from app.services.math.tools.school import apply_calculus_extension

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
    if intent.operation == "simplify":
        out = math_solve.simplify_expression(intent.expr, intent.variable)
    elif intent.operation == "differentiate":
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
                intent.expr, intent.variable, intent.integral_lower, intent.integral_upper
            )
        else:
            out = math_solve.integrate_expression(intent.expr, intent.variable)
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
            return VerifiedMathBlock(text="\n".join(lines))
        infinite_note = infinite_integral_note(out.result)
        if infinite_note is not None:
            lines.append(infinite_note)
    if not out.solved:
        lines.append(f"No closed-form result (got: {out.latex}).")
        return VerifiedMathBlock(text="\n".join(lines))
    answer = out.latex
    if intent.operation == "integrate" and intent.integral_lower is None:
        answer += " + C"
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
    limit_out = math_solve.compute_limit(
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
            "This limit is infinite — preserve its sign, do not treat it as an ordinary finite number."
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
            "This series diverges to infinity — preserve its sign, do not treat it as an ordinary finite number."
        )
    return _finish_with_answer(lines, series_out.latex)


def _verified_block_statistics(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.school_op in {
        "statistics_correlation",
        "statistics_regression",
        "statistics_covariance_sample",
        "statistics_covariance_population",
    }:
        if not intent.vec_a or not intent.vec_b:
            return None
        from app.services.math.solve.advanced import (
            BivariateStatisticsFeature,
            compute_bivariate_statistics,
        )

        feature = cast(BivariateStatisticsFeature, intent.school_op.removeprefix("statistics_"))
        answer, steps = compute_bivariate_statistics(intent.vec_a, intent.vec_b, feature)
        lines.append(f"Paired data: n={len(intent.vec_a)}")
        lines.extend(steps)
        return _finish_with_answer(lines, answer)

    if not intent.stats_numbers or len(intent.stats_numbers) < 2:
        return None
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
        from app.services.math import formulas as math_formulas

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
    return _finish_with_answer(lines, answer)


def _format_number_theory_answer(result: NumberTheoryResult) -> str:
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
    return _finish_with_answer(lines, str(result.result))


def _verified_block_number_theory(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.numtheory_op == "crt":
        if not intent.vec_a or len(intent.vec_a) != 4:
            return None
        from app.services.math.formulas import chinese_remainder

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
    return _finish_with_answer(lines, answer)


def _verified_block_matrix(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.matrix_rows:
        return None
    if intent.school_op in {
        "matrix_rank",
        "matrix_nullspace",
        "matrix_columnspace",
        "matrix_rowspace",
        "matrix_eigenvectors",
        "matrix_diagonalize",
    }:
        from app.services.math.solve.advanced import MatrixFeature, compute_matrix_feature

        feature = cast(MatrixFeature, intent.school_op.removeprefix("matrix_"))
        answer, steps = compute_matrix_feature(intent.matrix_rows, feature)
        lines.extend(steps)
        return _finish_with_answer(lines, answer)
    if intent.matrix_op is None:
        return None
    result = math_solve.compute_matrix(
        MatrixInput(
            operation=intent.matrix_op, rows=intent.matrix_rows, rows_b=intent.matrix_rows_b
        )
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
    return _finish_with_answer(lines, answer)

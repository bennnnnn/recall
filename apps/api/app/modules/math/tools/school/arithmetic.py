"""Arithmetic extractor and verified block. The if ladder keeps today's fall-through."""

from __future__ import annotations

from dataclasses import replace

from app.core.config import Settings
from app.modules.math import match as mtm
from app.modules.math import school as math_school
from app.modules.math.schemas import MathIntent
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.modules.math.tools.extractors.readings import read
from app.modules.math.tools.helpers import substituted_eval_expr
from app.modules.math.tools.school.fractions import _block_fraction
from app.modules.math.tools.school.interest import (
    _block_interest,
    _block_present_value,
    _extract_interest_intent,
    extract_present_value,
)
from app.modules.math.tools.school.percentages import (
    _block_discount,
    _block_original_before_percent,
    _block_percent,
    _block_percent_chain,
    _block_percent_change,
    _block_percent_change_from,
    _block_percent_is,
    _extract_percent_change,
    _extract_percent_is,
    _extract_percent_of,
    extract_discount,
    extract_original_before_percent,
    extract_percent_change_from,
    extract_with_percent_total,
)
from app.modules.math.tools.school.rates import (
    _block_mixture,
    _block_twice_as_many,
    _block_work_together,
    _extract_word_problem_intent,
)
from app.modules.math.tools.school.ratios import (
    _block_proportion,
    _block_ratio,
    _block_ratio_split,
    _extract_colon_ratio,
    _extract_ratio_split,
    extract_proportion,
)
from app.modules.math.tools.school.rounding import ROUNDING_OPS, extract_rounding, rounding_block
from app.modules.math.tools.school.sequences import (
    _block_infinite_gp,
    _block_sequence,
    _extract_sequence_intent,
    extract_infinite_geometric,
)
from app.modules.math.tools.school.sets import _block_sets, _extract_set_intent
from app.modules.math.tools.school.statistics import _block_z_score
from app.modules.math.tools.school.teaching import _attach_picture, _block_teaching
from app.services.workout import Workout, math_line, render_workout


def _extract_percent_or_ratio(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    # "% of " stays first so "Out of 250 people, what is 30% of 80?" is 24.
    percent_of = _extract_percent_of(cleaned)
    if percent_of is not None:
        return percent_of
    changed = _extract_percent_change(cleaned, lower)
    if changed is not None:
        return changed
    percent_is = _extract_percent_is(cleaned, lower)
    if percent_is is not None:
        return percent_is
    split = _extract_ratio_split(cleaned, lower)
    if split is not None:
        return split
    return _extract_colon_ratio(cleaned, lower)


# Closed school formulas, tried in this order after "a% of b" and ratios.
_FORMULA_READERS = (
    extract_original_before_percent,
    extract_discount,
    extract_with_percent_total,
    extract_percent_change_from,
    extract_present_value,
    extract_proportion,
    extract_rounding,
)


def extract_arithmetic_formulas(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    for reader in _FORMULA_READERS:
        intent = reader(cleaned, lower)
        if intent is not None:
            return intent
    return None


def _extract_arithmetic_intent(cleaned: str) -> MathIntent | None:
    lower_cleaned = cleaned.lower()
    if "decimal approximation" in lower_cleaned and "exact" in lower_cleaned:
        cut = lower_cleaned.find("give exact")
        if cut == -1:
            cut = lower_cleaned.find("give an exact")
        if cut != -1:
            base = cleaned[:cut].rstrip(" .?!")
            extracted = _extract_arithmetic_intent(base)
            if extracted is not None and extracted.expr:
                return extracted.model_copy(update={"school_op": "eval_exact_decimal"})
    spoken_power = mtm.spoken_power_request(cleaned)
    if spoken_power is not None:
        variable = next((char for char in spoken_power if char.isalpha()), "x")
        return MathIntent(
            kind="arithmetic",
            school_op="symbolic_power" if any(char.isalpha() for char in spoken_power) else "eval",
            expr=spoken_power,
            operation="solve",
            variable=variable,
        )
    addition = mtm.written_addition_request(cleaned)
    if addition is not None:
        return MathIntent(
            kind="arithmetic",
            school_op="column_addition",
            expr="+".join(addition),
            arithmetic_operands=addition,
            operation="solve",
        )
    written = mtm.written_arithmetic_request(cleaned)
    if written is not None:
        left, right, operator, school_op = written
        return MathIntent(
            kind="arithmetic",
            school_op=school_op,
            expr=f"{left}{operator}{right}",
            arithmetic_operands=[left, right],
            division_answer_mode=(
                mtm.division_answer_mode(cleaned, left, right)
                if school_op == "long_division"
                else None
            ),
            operation="solve",
        )
    substituted = substituted_eval_expr(cleaned)
    if substituted is not None:
        return MathIntent(kind="arithmetic", school_op="eval", expr=substituted, operation="solve")
    if mtm.has_equation(cleaned):
        return None
    percent = _extract_percent_or_ratio(cleaned)
    if percent is not None:
        return percent
    formulas = read(extract_arithmetic_formulas, cleaned)
    if formulas is not None:
        return formulas
    lower = cleaned.lower()
    interest = _extract_interest_intent(cleaned, lower)
    if interest is not None:
        return interest
    from app.modules.math.tools.school.shopping import extract_change_intent

    change = read(extract_change_intent, cleaned)
    if change is not None:
        return change
    sets = _extract_set_intent(cleaned, lower)
    if sets is not None:
        return sets
    word = _extract_word_problem_intent(cleaned, lower)
    if word is not None:
        return word
    infinite = extract_infinite_geometric(cleaned)
    if infinite is not None:
        return infinite
    sequence = _extract_sequence_intent(cleaned)
    if sequence is not None:
        return sequence
    expr = mtm.bare_arithmetic_expr(cleaned)
    if expr is None:
        return None
    return MathIntent(kind="arithmetic", school_op="eval", expr=expr, operation="solve")


def _verified_block_arithmetic(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.teaching_op and intent.teaching_payload:
        return _block_teaching(intent, lines)
    if intent.school_op in {"function_value", "expression_value"}:
        from app.modules.math.tools.school.function_value import _block_function_value

        return _block_function_value(intent, lines)
    if intent.school_op in {
        "pythagoras_leg",
        "polygon_angle_sum",
        "polygon_interior",
        "polygon_exterior",
    }:
        from app.modules.math.tools.school.geometry_facts import geometry_fact_block

        return geometry_fact_block(intent, lines)
    from app.modules.math.tools.school.algebra_facts import ALGEBRA_FACT_OPS, algebra_fact_block
    from app.modules.math.tools.school.geometry_measures import (
        geometry_measure_block,
        is_geometry_measure,
    )
    from app.modules.math.tools.school.number_facts import NUMBER_FACT_OPS, number_fact_block

    if is_geometry_measure(intent.school_op):
        return geometry_measure_block(intent, lines)
    if intent.school_op in NUMBER_FACT_OPS:
        return number_fact_block(intent, lines)
    if intent.school_op in ALGEBRA_FACT_OPS:
        return algebra_fact_block(intent, lines)
    from app.modules.math.tools.school.equation_features import (
        FEATURE_OPS,
        equation_feature_block,
    )

    if intent.school_op in FEATURE_OPS:
        return equation_feature_block(intent, lines)
    if intent.school_op and intent.school_op.startswith("fraction_"):
        fraction_block = _block_fraction(intent, lines)
        if fraction_block is not None:
            return fraction_block
    if (
        intent.school_op
        in {
            "column_addition",
            "column_subtraction",
            "column_multiplication",
            "long_division",
        }
        and intent.expr
    ):
        from app.modules.math.solve.written_arithmetic import build_written_arithmetic_operands

        # ``intent.expr`` is the extractor-owned canonical expression. Prefix
        # its ASCII slash with a calculation cue so the public grammar can
        # keep rejecting ambiguous bare dates such as ``9/9``.
        operands = intent.arithmetic_operands
        if operands is None:
            request = mtm.written_arithmetic_request(f"calculate {intent.expr}")
            operands = list(request[:2]) if request is not None else None
        if operands is not None:
            arithmetic_work = build_written_arithmetic_operands(
                operands,
                intent.school_op,
                intent.expr,
                division_answer_mode=intent.division_answer_mode,
            )
            if arithmetic_work is not None:
                from app.modules.math.tools.direct_arithmetic import (
                    final_answer,
                    written_fact_line,
                )

                lines.append(f"Verified {arithmetic_work.operation} procedure:")
                lines.extend(arithmetic_work.explanations)
                block = _finish_with_answer(lines, final_answer(arithmetic_work))
                return replace(
                    block,
                    canonical_fences=[arithmetic_work.model_dump()],
                    display_answer=written_fact_line(arithmetic_work),
                )
    if (
        intent.school_op == "z_score"
        and intent.point_x is not None
        and intent.percent_base is not None
        and intent.percent_rate is not None
    ):
        return _block_z_score(intent, lines)
    if (
        intent.school_op == "percent"
        and intent.percent_rate is not None
        and intent.percent_base is not None
    ):
        return _block_percent(intent, lines)
    if intent.school_op == "percent_chain":
        return _block_percent_chain(intent, lines)
    if (
        intent.school_op in {"percent_increase", "percent_decrease"}
        and intent.percent_rate is not None
        and intent.percent_base is not None
    ):
        return _block_percent_change(intent, lines)
    if (
        intent.school_op == "percent_is"
        and intent.percent_rate is not None
        and intent.percent_base is not None
    ):
        return _block_percent_is(intent, lines)
    if (
        intent.school_op == "discount"
        and intent.percent_rate is not None
        and intent.percent_base is not None
    ):
        return _block_discount(intent, lines)
    if intent.school_op in {"original_before_decrease", "original_before_increase"}:
        return _block_original_before_percent(intent, lines)
    if (
        intent.school_op == "percent_change_from"
        and intent.percent_base is not None
        and intent.percent_rate is not None
    ):
        return _block_percent_change_from(intent, lines)
    if intent.school_op in {"direct_proportion", "inverse_proportion"} and intent.stats_numbers:
        return _block_proportion(intent, lines)
    if (
        intent.school_op in ROUNDING_OPS
        and intent.percent_base is not None
        and intent.combo_n is not None
    ):
        return rounding_block(intent, lines)
    if intent.school_op == "infinite_gp" and intent.stats_numbers:
        return _block_infinite_gp(intent, lines)
    if (
        intent.school_op == "present_value"
        and intent.percent_base is not None
        and intent.percent_rate is not None
        and intent.combo_n is not None
    ):
        return _block_present_value(intent, lines)
    if (
        intent.school_op == "ratio"
        and intent.percent_rate is not None
        and intent.percent_base is not None
    ):
        return _block_ratio(intent, lines)
    if (
        intent.school_op == "ratio_split"
        and intent.percent_base is not None
        and intent.stats_numbers
    ):
        return _block_ratio_split(intent, lines)
    if (
        intent.school_op in {"sequence_nth", "sequence_sum"}
        and intent.stats_numbers
        and intent.combo_n is not None
    ):
        return _block_sequence(intent, lines)
    if (
        intent.school_op in {"simple_interest", "compound_interest", "compound_amount"}
        and intent.percent_base is not None
        and intent.percent_rate is not None
        and intent.combo_n is not None
    ):
        return _block_interest(intent, lines)
    if (
        intent.school_op in {"set_union", "set_intersection", "set_difference"}
        and intent.vec_a is not None
        and intent.vec_b is not None
    ):
        return _block_sets(intent, lines)
    if (
        intent.school_op == "work_together"
        and intent.percent_base is not None
        and intent.percent_rate is not None
    ):
        return _block_work_together(intent, lines)
    if intent.school_op == "mixture" and intent.vec_a and intent.vec_b and len(intent.vec_a) == 2:
        return _block_mixture(intent, lines)
    if intent.school_op == "change_from_payment":
        from app.modules.math.tools.school.shopping import change_block

        return change_block(intent, lines)
    if intent.school_op == "twice_as_many" and intent.percent_base is not None:
        return _block_twice_as_many(intent, lines)
    if not intent.expr:
        return None
    if intent.school_op == "symbolic_power":
        from app.modules.math import solve as math_solve

        answer = math_solve.simplify_expression(intent.expr, intent.variable).latex
        lines.append(f"Power notation: {answer}")
        block = _finish_with_answer(lines, answer)
        base, separator, exponent_text = intent.expr.rpartition("^")
        if not separator or not exponent_text.isdigit():
            return block
        exponent = int(exponent_text)
        if exponent == 0:
            formula = math_line("a^0 = 1, \\quad a \\ne 0", "Zero-exponent law")
            line = math_line(f"{base}^0 = 1")
        elif exponent == 1:
            formula = math_line("a^1 = a", "First power")
            line = math_line(f"{base}^1 = {answer}")
        elif exponent <= 8:
            factors = r" \times ".join(base for _ in range(exponent))
            formula = math_line("a^{n} = a \\times \\cdots \\times a", "Power notation")
            line = math_line(f"{base}^{exponent} = {factors} = {answer}")
        else:
            formula = math_line("a^{n} = a \\times \\cdots \\times a", "Power notation")
            line = math_line(f"{base}^{exponent}", f"{exponent} factors of ${base}$")
        working = render_workout(
            Workout(
                given=(math_line(f"{base}^{{{exponent}}}"),),
                formula=(formula,),
                substitution=(line,),
            )
        )
        return replace(
            block,
            direct_reply=f"{working}\n\n```answer\n{answer}\n```\n",
        )
    answer = math_school.evaluate_arithmetic(intent.expr)
    if intent.school_op == "eval_exact_decimal":
        from app.modules.math import solve as math_solve

        parsed = math_solve._parse_expression(intent.expr, [intent.variable])
        if isinstance(parsed, tuple) or parsed.free_symbols:
            return None
        decimal = str(parsed.evalf(6))
        direct = render_workout(
            Workout(
                given=(math_line(intent.expr),),
                steps=(math_line(answer, "exact"), math_line(f"\\approx {decimal}", "decimal")),
            ),
            answer,
        )
        block = _finish_with_answer(lines, answer)
        return VerifiedMathBlock(
            text=block.text,
            canonical_fence=block.canonical_fence,
            canonical_answer=block.canonical_answer,
            direct_reply=direct,
        )
    factorials = _factorial_block(intent.expr or "", answer, lines)
    if factorials is not None:
        return factorials
    lines.append(f"Result: {answer}")
    block = _finish_with_answer(lines, answer)
    from app.modules.math.tools.direct_arithmetic import arithmetic_equation

    shown = arithmetic_equation(intent.expr or "", answer)
    if shown is not None:
        if answer == math_school.UNDEFINED_LATEX:
            # "5 ÷ 0 is undefined", not an equation with a word on one side.
            shown = shown.removesuffix(f" = {answer}") + r" \text{ is undefined}"
        return replace(block, display_answer=shown)
    if intent.school_op != "eval" or not intent.expr:
        return block
    from app.modules.math.solve.teaching_elementary import number_line_for_expr

    move = number_line_for_expr(intent.expr, answer)
    if move is None:
        return block
    return _attach_picture(block, move, intent, direct=True)


def _factorial_block(expr: str, answer: str, lines: list[str]) -> VerifiedMathBlock | None:
    """``6!/4! = 720/24``, then the answer on its own line: the left side is written once."""
    if "!" not in expr:
        return None
    from sympy import Rational

    from app.modules.math import solve as math_solve
    from app.modules.math.solve.factorial_working import factorial_working

    working = factorial_working(expr)
    parsed = math_solve._parse_expression(expr, ["x"])
    if working is None or isinstance(parsed, tuple):
        return None
    if parsed != Rational(working.value.numerator, working.value.denominator):
        return None
    lines.append(f"Working: ${working.tex}$")
    lines.append(f"Result: {answer}")
    block = _finish_with_answer(lines, answer)
    return replace(block, worked_reply=f"{math_line(working.tex)}\n\n```answer\n{answer}\n```\n")

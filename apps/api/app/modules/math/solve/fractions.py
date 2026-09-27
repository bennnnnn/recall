"""Exact primary-school fraction procedures."""

from __future__ import annotations

from fractions import Fraction
from math import gcd, lcm
from typing import Literal, cast

from app.models.schemas.math import FractionStep, FractionWorkSpec, MathIntent


def _parse_fraction(value: str) -> tuple[int, int] | None:
    numerator_text, separator, denominator_text = value.partition("/")
    if not separator:
        return None
    try:
        numerator, denominator = int(numerator_text), int(denominator_text)
    except ValueError:
        return None
    if numerator < 0 or denominator <= 0:
        return None
    return numerator, denominator


def _latex(numerator: int, denominator: int) -> str:
    return str(numerator) if denominator == 1 else rf"\frac{{{numerator}}}{{{denominator}}}"


def _finish(
    operation: str,
    operands: list[str],
    value: Fraction,
    steps: list[FractionStep],
    *,
    answer: str | None = None,
) -> FractionWorkSpec:
    return FractionWorkSpec(
        operation=cast(
            Literal[
                "simplify",
                "equivalent",
                "add",
                "subtract",
                "multiply",
                "divide",
                "mixed_to_improper",
                "improper_to_mixed",
                "of_quantity",
                "compare",
            ],
            operation,
        ),
        operands=operands,
        answer=answer or _latex(value.numerator, value.denominator),
        exact_numerator=value.numerator,
        exact_denominator=value.denominator,
        steps=steps,
    )


def _binary(intent: MathIntent) -> FractionWorkSpec | None:
    operands = intent.fraction_operands or []
    if len(operands) != 2:
        return None
    left_parts, right_parts = _parse_fraction(operands[0]), _parse_fraction(operands[1])
    if left_parts is None or right_parts is None:
        return None
    a, b = left_parts
    c, d = right_parts
    left, right = Fraction(a, b), Fraction(c, d)
    op = intent.school_op
    steps: list[FractionStep] = []
    if op in {"fraction_add", "fraction_subtract"}:
        common = lcm(b, d)
        left_scaled, right_scaled = a * (common // b), c * (common // d)
        steps.append(
            FractionStep(
                kind="common_denominator",
                explanation=f"Use the least common denominator {common}.",
                expression=rf"\frac{{{a}}}{{{b}}},\ \frac{{{c}}}{{{d}}}",
                result=rf"\frac{{{left_scaled}}}{{{common}}},\ \frac{{{right_scaled}}}{{{common}}}",
            )
        )
        combined = (
            left_scaled + right_scaled if op == "fraction_add" else left_scaled - right_scaled
        )
        if combined < 0:
            return None
        value = Fraction(combined, common)
        symbol = "+" if op == "fraction_add" else "-"
        steps.append(
            FractionStep(
                kind="combine",
                explanation="Combine the numerators and keep the common denominator.",
                expression=rf"\frac{{{left_scaled} {symbol} {right_scaled}}}{{{common}}}",
                result=_latex(value.numerator, value.denominator),
            )
        )
        operation = "add" if op == "fraction_add" else "subtract"
        return _finish(operation, operands, value, steps)
    if op == "fraction_multiply":
        value = left * right
        steps.append(
            FractionStep(
                kind="multiply",
                explanation="Multiply numerators and multiply denominators.",
                expression=rf"\frac{{{a}\times {c}}}{{{b}\times {d}}}",
                result=_latex(value.numerator, value.denominator),
            )
        )
        return _finish("multiply", operands, value, steps)
    if op == "fraction_divide" and c != 0:
        steps.append(
            FractionStep(
                kind="reciprocal",
                explanation=(
                    "Keep the first fraction, change division to multiplication, "
                    "and flip the second."
                ),
                expression=rf"\frac{{{a}}}{{{b}}}\div\frac{{{c}}}{{{d}}}",
                result=rf"\frac{{{a}}}{{{b}}}\times\frac{{{d}}}{{{c}}}",
            )
        )
        value = left / right
        steps.append(
            FractionStep(
                kind="multiply",
                explanation="Multiply, then simplify.",
                expression=rf"\frac{{{a}\times {d}}}{{{b}\times {c}}}",
                result=_latex(value.numerator, value.denominator),
            )
        )
        return _finish("divide", operands, value, steps)
    return None


def build_fraction_work(intent: MathIntent) -> FractionWorkSpec | None:
    operands = intent.fraction_operands or []
    op = intent.school_op
    if op in {"fraction_add", "fraction_subtract", "fraction_multiply", "fraction_divide"}:
        return _binary(intent)
    if op == "fraction_simplify" and len(operands) == 1:
        parts = _parse_fraction(operands[0])
        if parts is None:
            return None
        numerator, denominator = parts
        divisor = gcd(numerator, denominator)
        value = Fraction(numerator, denominator)
        return _finish(
            "simplify",
            operands,
            value,
            [
                FractionStep(
                    kind="gcd",
                    explanation=(
                        f"The greatest common divisor is {divisor}; divide both parts by it."
                    ),
                    expression=(
                        rf"\frac{{{numerator}\div {divisor}}}"
                        rf"{{{denominator}\div {divisor}}}"
                    ),
                    result=_latex(value.numerator, value.denominator),
                )
            ],
        )
    if op == "fraction_equivalent" and len(operands) == 1 and intent.fraction_target:
        parts = _parse_fraction(operands[0])
        if parts is None:
            return None
        numerator, denominator = parts
        target = intent.fraction_target
        if target <= 0 or target % denominator:
            return None
        factor = target // denominator
        result_numerator = numerator * factor
        value = Fraction(result_numerator, target)
        return _finish(
            "equivalent",
            [*operands, str(target)],
            value,
            [
                FractionStep(
                    kind="equivalent",
                    explanation=f"Multiply numerator and denominator by {factor}.",
                    expression=(
                        rf"\frac{{{numerator}\times {factor}}}"
                        rf"{{{denominator}\times {factor}}}"
                    ),
                    result=rf"\frac{{{result_numerator}}}{{{target}}}",
                )
            ],
            answer=rf"\frac{{{result_numerator}}}{{{target}}}",
        )
    if op == "fraction_mixed_to_improper" and len(operands) == 2:
        parts = _parse_fraction(operands[1])
        if parts is None:
            return None
        whole, (numerator, denominator) = int(operands[0]), parts
        improper = whole * denominator + numerator
        value = Fraction(improper, denominator)
        return _finish(
            "mixed_to_improper",
            operands,
            value,
            [
                FractionStep(
                    kind="convert",
                    explanation="Multiply the whole number by the denominator.",
                    expression=rf"{whole}\times {denominator}",
                    result=str(whole * denominator),
                ),
                FractionStep(
                    kind="convert",
                    explanation=("Add the old numerator, then keep the original denominator."),
                    expression=rf"\frac{{{whole * denominator}+{numerator}}}{{{denominator}}}",
                    result=rf"\frac{{{improper}}}{{{denominator}}}",
                ),
            ],
            answer=rf"\frac{{{improper}}}{{{denominator}}}",
        )
    if op == "fraction_improper_to_mixed" and len(operands) == 1:
        parts = _parse_fraction(operands[0])
        if parts is None:
            return None
        numerator, denominator = parts
        whole, remainder = divmod(numerator, denominator)
        value = Fraction(numerator, denominator)
        answer = str(whole) if not remainder else rf"{whole}\frac{{{remainder}}}{{{denominator}}}"
        return _finish(
            "improper_to_mixed",
            operands,
            value,
            [
                FractionStep(
                    kind="convert",
                    explanation=(
                        f"{denominator} goes into {numerator} exactly {whole} whole times, "
                        f"with {remainder} left over."
                    ),
                    expression=str(numerator),
                    result=rf"{denominator}\times {whole}+{remainder}",
                ),
                FractionStep(
                    kind="convert",
                    explanation=(
                        "Keep the quotient as the whole number and put the remainder over "
                        "the original denominator."
                    ),
                    expression=rf"\frac{{{numerator}}}{{{denominator}}}",
                    result=rf"{whole}+\frac{{{remainder}}}{{{denominator}}}",
                ),
            ],
            answer=answer,
        )
    if op == "fraction_of_quantity" and len(operands) == 2:
        parts = _parse_fraction(operands[0])
        if parts is None:
            return None
        try:
            quantity = Fraction(operands[1])
        except ValueError:
            return None
        numerator, denominator = parts
        value = Fraction(numerator, denominator) * quantity
        return _finish(
            "of_quantity",
            operands,
            value,
            [
                FractionStep(
                    kind="quantity",
                    explanation="'Of' means multiply.",
                    expression=rf"\frac{{{numerator}}}{{{denominator}}}\times {operands[1]}",
                    result=_latex(value.numerator, value.denominator),
                )
            ],
        )
    if op == "fraction_compare" and len(operands) == 2:
        left_parts, right_parts = _parse_fraction(operands[0]), _parse_fraction(operands[1])
        if left_parts is None or right_parts is None:
            return None
        a, b = left_parts
        c, d = right_parts
        left_cross, right_cross = a * d, c * b
        symbol = ">" if left_cross > right_cross else "<" if left_cross < right_cross else "="
        answer = rf"\frac{{{a}}}{{{b}}} {symbol} \frac{{{c}}}{{{d}}}"
        return FractionWorkSpec(
            operation="compare",
            operands=operands,
            answer=answer,
            steps=[
                FractionStep(
                    kind="compare",
                    explanation="Cross-multiply; both products use the same positive denominator.",
                    expression=rf"{a}\times {d}\ ?\ {c}\times {b}",
                    result=f"{left_cross} {symbol} {right_cross}",
                )
            ],
        )
    return None

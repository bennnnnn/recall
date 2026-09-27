"""Exact long-division traces, including terminating decimal work."""

from __future__ import annotations

from decimal import Decimal
from math import gcd

from app.models.schemas.math import ArithmeticWorkSpec, LongDivisionStep
from app.modules.math.solve.written_arithmetic_common import (
    MAX_DECIMAL_PLACES,
    format_scaled,
    number_parts,
    scaled_integer,
)


def _plain_decimal(value: Decimal) -> str:
    raw = format(value, "f")
    return (raw.rstrip("0").rstrip(".") if "." in raw else raw) or "0"


def _terminating_places(numerator: int, denominator: int) -> int | None:
    common = gcd(numerator, denominator)
    denominator //= common
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    places = max(twos, fives)
    return places if denominator == 1 and places <= MAX_DECIMAL_PLACES else None


def _division_steps(
    digits: str, divisor: int, extra_zeros: int
) -> tuple[list[LongDivisionStep], int]:
    remainder = 0
    current = 0
    steps: list[LongDivisionStep] = []
    working_digits = [int(char) for char in digits]
    working_digits.extend([0] * extra_zeros)
    for digit_index, digit in enumerate(working_digits):
        current = remainder * 10 + digit
        if not steps and current < divisor:
            remainder = current
            continue
        quotient_digit, remainder = divmod(current, divisor)
        next_digit = (
            working_digits[digit_index + 1] if digit_index + 1 < len(working_digits) else None
        )
        next_partial = str(remainder * 10 + next_digit) if next_digit is not None else None
        steps.append(
            LongDivisionStep(
                index=len(steps),
                column_end=digit_index,
                partial_dividend=str(current),
                quotient_digit=quotient_digit,
                product=str(quotient_digit * divisor),
                remainder=str(remainder),
                bring_down=next_digit,
                next_partial=next_partial,
            )
        )
    if not steps:
        steps.append(
            LongDivisionStep(
                index=0,
                column_end=max(0, len(digits) - 1),
                partial_dividend=str(int(digits or "0")),
                quotient_digit=0,
                product="0",
                remainder=str(int(digits or "0")),
            )
        )
        remainder = int(digits or "0")
    return steps, remainder


def build_long_division(
    left_token: str, right_token: str, expression: str
) -> ArithmeticWorkSpec | None:
    left_parts, right_parts = number_parts(left_token), number_parts(right_token)
    if left_parts is None or right_parts is None:
        return None
    left, left_scale = left_parts
    right, right_scale = right_parts
    if right == 0:
        return None
    shift = right_scale
    working_left = left.scaleb(shift)
    divisor = scaled_integer(right, shift)
    if divisor <= 0:
        return None
    working_text = _plain_decimal(working_left)
    digits = working_text.replace(".", "")
    integer_digits = len(working_text.partition(".")[0])
    numerator = int(digits or "0")
    denominator = divisor * (10 ** max(0, len(digits) - integer_digits))
    has_decimal_input = left_scale > 0 or right_scale > 0
    places = _terminating_places(numerator, denominator) if has_decimal_input else None
    if has_decimal_input:
        if places is None:
            return None
        quotient_decimal = Decimal(numerator) / Decimal(denominator)
        quotient = _plain_decimal(quotient_decimal)
        target_extra = max(0, places - max(0, len(digits) - integer_digits))
    else:
        quotient_int, _ = divmod(numerator, divisor)
        quotient = str(quotient_int)
        target_extra = 0
    steps, remainder = _division_steps(digits, divisor, target_extra)
    division_display = working_text
    if target_extra:
        separator = "" if "." in division_display else "."
        division_display += separator + ("0" * target_extra)
    explanations: list[str] = []
    if shift:
        plural = "" if shift == 1 else "s"
        explanations.append(
            f"Move both decimal points {shift} place{plural} right: {working_text} ÷ {divisor}."
        )
    if target_extra:
        plural = "" if target_extra == 1 else "s"
        explanations.append(
            f"Append {target_extra} placeholder zero{plural} to continue the division."
        )
    for step in steps:
        text = (
            f"{step.partial_dividend} ÷ {divisor} gives {step.quotient_digit}. "
            f"Multiply: {step.quotient_digit} x {divisor} = {step.product}. "
            f"Subtract: {step.partial_dividend} - {step.product} = {step.remainder}."
        )
        if step.bring_down is not None:
            text += f" Bring down {step.bring_down} → {step.next_partial}."
        explanations.append(text)
    remainder_text = "0" if has_decimal_input else str(remainder)
    answer = (
        quotient if remainder_text == "0" else f"{quotient}\\text{{ remainder }}{remainder_text}"
    )
    explanations.append(
        f"Quotient: {quotient}."
        if remainder_text == "0"
        else f"Quotient: {quotient}; remainder: {remainder_text}."
    )
    return ArithmeticWorkSpec(
        operation="division",
        operator="÷",
        expression=expression,
        operands=[
            format_scaled(scaled_integer(left, left_scale), left_scale),
            format_scaled(scaled_integer(right, right_scale), right_scale),
        ],
        working_operands=[division_display, str(divisor)],
        answer=answer,
        decimal_places=places or 0,
        quotient=quotient,
        remainder=remainder_text,
        division_steps=steps,
        explanations=explanations,
    )

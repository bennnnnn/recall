"""Whole-request guards and direct formatting for written arithmetic."""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.models.schemas.math import ArithmeticWorkSpec, FractionWorkSpec
from app.modules.math.response_intent import MathResponseMode, classify_math_response_intent
from app.modules.math.tools.lesson import lesson_math_text
from app.services.solving import VerifiedMathBlock


def arithmetic_work_spec(verified: VerifiedMathBlock) -> ArithmeticWorkSpec | None:
    specs = [verified.canonical_fence, *verified.canonical_fences]
    candidates = [
        spec for spec in specs if isinstance(spec, dict) and spec.get("type") == "arithmetic"
    ]
    if len(candidates) != 1:
        return None
    try:
        return ArithmeticWorkSpec.model_validate(candidates[0])
    except ValidationError:
        return None


def fraction_work_spec(verified: VerifiedMathBlock) -> FractionWorkSpec | None:
    specs = [verified.canonical_fence, *verified.canonical_fences]
    candidates = [
        spec for spec in specs if isinstance(spec, dict) and spec.get("type") == "fraction"
    ]
    if len(candidates) != 1:
        return None
    try:
        return FractionWorkSpec.model_validate(candidates[0])
    except ValidationError:
        return None


def can_direct_written_arithmetic(
    verified: VerifiedMathBlock, user_text: str, spec: ArithmeticWorkSpec
) -> bool:
    """Require the entire request to describe the exact traced operation."""
    if len(user_text) > 1000 or verified.canonical_answer != spec.answer:
        return False
    from app.modules.math import match as mtm

    if spec.operation == "addition" and len(spec.operands) > 2:
        requested_addends = mtm.written_addition_request(lesson_math_text(user_text))
        return requested_addends == spec.operands
    requested = mtm.written_arithmetic_request(lesson_math_text(user_text))
    solved = mtm.written_arithmetic_request(f"calculate {spec.expression}")
    return requested is not None and requested == solved


def can_direct_fraction(
    verified: VerifiedMathBlock, user_text: str, spec: FractionWorkSpec
) -> bool:
    if len(user_text) > 1000 or verified.canonical_answer != spec.answer:
        return False
    from app.modules.math.tools.extractors.fractions import extract_fraction_intent

    intent = extract_fraction_intent(user_text)
    if intent is None:
        return False
    operation = (intent.school_op or "").removeprefix("fraction_")
    operation = {
        "mixed_to_improper": "mixed_to_improper",
        "improper_to_mixed": "improper_to_mixed",
        "of_quantity": "of_quantity",
    }.get(operation, operation)
    request_operands = intent.fraction_operands or []
    return operation == spec.operation and request_operands == spec.operands[
        : len(request_operands)
    ]


def format_direct_written_arithmetic(spec: ArithmeticWorkSpec, user_text: str) -> str:
    response = classify_math_response_intent(user_text)
    answer = f"```answer\n{spec.answer}\n```\n"
    if response.mode == MathResponseMode.ANSWER_ONLY or (
        not response.wants_explanation and spec.operation != "division"
    ):
        return answer
    body = json.dumps(spec.model_dump(), separators=(",", ":"))
    return f"```arithmetic\n{body}\n```\n\n{answer}"


def format_direct_fraction(spec: FractionWorkSpec, user_text: str) -> str:
    response = classify_math_response_intent(user_text)
    answer = f"```answer\n{spec.answer}\n```\n"
    if response.mode == MathResponseMode.ANSWER_ONLY or not response.wants_explanation:
        return answer
    body = json.dumps(spec.model_dump(), separators=(",", ":"))
    return f"```arithmetic\n{body}\n```\n\n{answer}"

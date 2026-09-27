"""Whole-request guards and direct formatting for written arithmetic."""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.models.schemas.math import ArithmeticWorkSpec
from app.modules.math.response_intent import classify_math_response_intent
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


def can_direct_written_arithmetic(
    verified: VerifiedMathBlock, user_text: str, spec: ArithmeticWorkSpec
) -> bool:
    """Require the entire request to describe the exact traced operation."""
    if len(user_text) > 1000 or verified.canonical_answer != spec.answer:
        return False
    from app.modules.math import match as mtm

    requested = mtm.written_arithmetic_request(lesson_math_text(user_text))
    solved = mtm.written_arithmetic_request(f"calculate {spec.expression}")
    return requested is not None and requested == solved


def format_direct_written_arithmetic(spec: ArithmeticWorkSpec, user_text: str) -> str:
    response = classify_math_response_intent(user_text)
    answer = f"```answer\n{spec.answer}\n```\n"
    if not response.wants_explanation:
        return answer
    body = json.dumps(spec.model_dump(), separators=(",", ":"))
    return f"```arithmetic\n{body}\n```\n\n{answer}"

"""Attach a solver-owned teaching picture to a verified math block."""

from __future__ import annotations

import json
from dataclasses import replace

from app.models.schemas.math.teaching import TEACHING_TYPES, TeachingSpec
from app.services.solving import VerifiedMathBlock


def attach_teaching(
    block: VerifiedMathBlock,
    spec: TeachingSpec,
    *,
    direct: bool,
    request_text: str | None,
) -> VerifiedMathBlock:
    data = spec.model_dump()
    fences = [*block.canonical_fences, data]
    if not direct:
        return replace(block, canonical_fences=fences)
    body = json.dumps(data, separators=(",", ":"))
    # The answer chip leads so a single-digit fact stays a verified chip.
    # The picture follows and does not change that answer.
    reply = f"```answer\n{spec.answer}\n```\n\n```arithmetic\n{body}\n```\n"
    return replace(
        block,
        canonical_fences=fences,
        direct_reply=reply,
        direct_request_text=request_text or block.direct_request_text,
    )


def teaching_fence(block: VerifiedMathBlock) -> dict[str, object] | None:
    for fence in (*block.canonical_fences, block.canonical_fence):
        if isinstance(fence, dict) and fence.get("type") in TEACHING_TYPES:
            return fence
    return None


def prepend_teaching_fence(reply: str, block: VerifiedMathBlock, user_text: str) -> str:
    from app.modules.math.response_intent import MathResponseMode, classify_math_response_intent

    if classify_math_response_intent(user_text).mode == MathResponseMode.ANSWER_ONLY:
        return reply
    fence = teaching_fence(block)
    if fence is None or "```arithmetic" in reply:
        return reply
    body = json.dumps(fence, separators=(",", ":"))
    return f"```arithmetic\n{body}\n```\n\n{reply}"

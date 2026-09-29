"""Teaching-picture attachment and the arithmetic teaching branch."""

from __future__ import annotations

from app.models.schemas.math import MathIntent
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer


def _attach_picture(
    block: VerifiedMathBlock,
    spec: object,
    intent: MathIntent,
    *,
    direct: bool,
) -> VerifiedMathBlock:
    from app.models.schemas.math.teaching import TeachingSpec
    from app.modules.math.tools.direct_teaching import attach_teaching

    if not isinstance(spec, TeachingSpec):
        return block
    return attach_teaching(block, spec, direct=direct, request_text=intent._request_text)


def _block_teaching(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    from app.modules.math.solve.teaching import build_teaching

    if intent.teaching_op is None or intent.teaching_payload is None:
        return None
    picture = build_teaching(intent.teaching_op, intent.teaching_payload)
    if picture is None:
        return None
    lines.append(picture.speech)
    return _attach_picture(_finish_with_answer(lines, picture.answer), picture, intent, direct=True)

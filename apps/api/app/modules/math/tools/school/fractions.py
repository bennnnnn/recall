"""Verified fraction procedure branch."""

from __future__ import annotations

from dataclasses import replace

from app.models.schemas.math import MathIntent
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.modules.math.tools.school.teaching import _attach_picture


def _block_fraction(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    from app.modules.math.solve.fractions import build_fraction_work

    fraction_work = build_fraction_work(intent)
    if fraction_work is not None:
        from app.modules.math.solve.teaching_elementary import fraction_bar_spec

        lines.append("Verified fraction procedure:")
        lines.extend(step.explanation for step in fraction_work.steps)
        block = _finish_with_answer(lines, fraction_work.answer)
        block = replace(block, canonical_fences=[fraction_work.model_dump()])
        bars = fraction_bar_spec(
            fraction_work.operation, fraction_work.operands, fraction_work.answer
        )
        if bars is None:
            return block
        return _attach_picture(block, bars, intent, direct=False)
    return None

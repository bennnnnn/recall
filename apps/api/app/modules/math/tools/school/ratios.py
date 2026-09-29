"""Ratio and proportion extractors and verified blocks."""

from __future__ import annotations

import re

from app.models.schemas.math import MathIntent
from app.modules.math import match as mtm
from app.modules.math import school as math_school
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.modules.math.tools.school._parse import (
    _colon_ratio_parts,
    _finite_match_value,
    _has_any_word,
)

_RATIO_SPLIT_WORDS = ("split", "share", "divide")


def _extract_ratio_split(cleaned: str, lower: str) -> MathIntent | None:
    if not _has_any_word(lower, _RATIO_SPLIT_WORDS) or "ratio" not in lower:
        return None
    grouped = _colon_ratio_parts(cleaned)
    if grouped is None:
        return None
    parts, spans = grouped
    if any(part < 0 for part in parts) or sum(parts) <= 0:
        return None
    leftover: list[re.Match[str]] = []
    used = set(spans)
    for match in mtm._NUM.finditer(cleaned):
        if (match.start(), match.end()) in used:
            continue
        leftover.append(match)
    if len(leftover) != 1:
        return None
    total = _finite_match_value(leftover[0])
    if total is None or total <= 0:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="ratio_split",
        percent_base=total,
        stats_numbers=parts,
        operation="solve",
    )


def _extract_colon_ratio(cleaned: str, lower: str) -> MathIntent | None:
    if ":" in cleaned and ("ratio" in lower or "simplify" in lower):
        first = mtm._NUM.search(cleaned)
        if first:
            second = mtm._NUM.search(cleaned, first.end())
            if second:
                left = _finite_match_value(first)
                right = _finite_match_value(second)
                if left is None or right is None:
                    return None
                extra = mtm._NUM.search(cleaned, second.end())
                if extra is not None:
                    return None
                return MathIntent(
                    kind="arithmetic",
                    school_op="ratio",
                    percent_rate=left,
                    percent_base=right,
                    operation="solve",
                )
    return None


def _block_proportion(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    from app.modules.math import formulas as math_formulas

    if intent.stats_numbers is None or len(intent.stats_numbers) != 3:
        return None
    a, b, c = intent.stats_numbers
    if intent.school_op == "direct_proportion":
        answer = math_formulas.direct_proportion(a, b, c)
    else:
        answer = math_formulas.inverse_proportion(a, b, c)
    lines.append(f"{intent.school_op}: {answer}")
    return _finish_with_answer(lines, answer)


def _block_ratio(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    if intent.percent_rate is None or intent.percent_base is None:
        return None
    answer = math_school.simplify_ratio(intent.percent_rate, intent.percent_base)
    lines.append(f"Simplified ratio: {answer}")
    return _finish_with_answer(lines, answer)


def _block_ratio_split(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    if intent.percent_base is None or intent.stats_numbers is None:
        return None
    answer = math_school.split_ratio(intent.percent_base, intent.stats_numbers)
    lines.append(f"{intent.percent_base:g} in ratio split = {answer}")
    return _finish_with_answer(lines, answer)

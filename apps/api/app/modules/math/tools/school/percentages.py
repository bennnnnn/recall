"""Percent extractors and verified blocks."""

from __future__ import annotations

import re

from app.models.schemas.math import MathIntent
from app.modules.math import match as mtm
from app.modules.math import school as math_school
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.modules.math.tools.school._parse import (
    _count_char,
    _finite_match_value,
    _has_any_word,
    _number_immediately_before,
)
from app.services.text_match import word_index

_PERCENT_INCREASE_WORDS = ("increase", "increased", "increasing", "markup", "marked up")
_PERCENT_DECREASE_WORDS = ("decrease", "decreased", "decreasing")


def _extract_percent_of(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    pct = lower.find("% of ")
    if pct == -1:
        return None
    rate_m = None
    for match in mtm._NUM.finditer(cleaned[:pct]):
        rate_m = match
    base_m = mtm._NUM.search(cleaned, pct + 5)
    if rate_m is None or base_m is None:
        return None
    rate = _finite_match_value(rate_m)
    base = _finite_match_value(base_m)
    if rate is None or base is None:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="percent",
        percent_rate=rate,
        percent_base=base,
        operation="solve",
    )


def _extract_percent_change(cleaned: str, lower: str) -> MathIntent | None:
    increase = _has_any_word(lower, _PERCENT_INCREASE_WORDS)
    decrease = _has_any_word(lower, _PERCENT_DECREASE_WORDS)
    if increase == decrease:
        return None
    if _count_char(cleaned, "%") != 1:
        return None
    by_at = word_index(lower, "by")
    if by_at == -1:
        return None
    nums = list(mtm._NUM.finditer(cleaned))
    if len(nums) != 2:
        return None
    pct_at = cleaned.find("%")
    rate_m = _number_immediately_before(cleaned, pct_at)
    if rate_m is None:
        return None
    base_m = nums[0] if nums[0].span() != rate_m.span() else nums[1]
    if base_m.span() == rate_m.span() or base_m.end() > by_at or rate_m.start() < by_at:
        return None
    rate = _finite_match_value(rate_m)
    base = _finite_match_value(base_m)
    if rate is None or base is None:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="percent_increase" if increase else "percent_decrease",
        percent_rate=rate,
        percent_base=base,
        operation="solve",
    )


def _extract_percent_is(cleaned: str, lower: str) -> MathIntent | None:
    if _count_char(cleaned, "%") != 0:
        return None
    nums = list(mtm._NUM.finditer(cleaned))
    if len(nums) != 2:
        return None
    part_m: re.Match[str] | None = None
    whole_m: re.Match[str] | None = None
    for cue in (" is what percent of ", " is what percentage of "):
        idx = lower.find(cue)
        if idx == -1:
            continue
        before = None
        for match in nums:
            if match.end() <= idx:
                before = match
        after = mtm._NUM.search(cleaned, idx + len(cue))
        if before is None or after is None:
            return None
        part_m, whole_m = before, after
        break
    if part_m is None or whole_m is None:
        for cue in ("what percent of ", "what percentage of "):
            idx = lower.find(cue)
            if idx == -1:
                continue
            whole = mtm._NUM.search(cleaned, idx + len(cue))
            if whole is None:
                return None
            rest = cleaned[whole.end() :].lstrip()
            if not rest.lower().startswith("is"):
                return None
            after_is = rest[2:]
            if after_is[:1].isalpha():
                return None
            part = mtm._NUM.search(after_is)
            if part is None:
                return None
            part_m, whole_m = part, whole
            break
    if part_m is None or whole_m is None:
        return None
    if {part_m.group(0), whole_m.group(0)} != {nums[0].group(0), nums[1].group(0)}:
        return None
    part_value = _finite_match_value(part_m)
    whole_value = _finite_match_value(whole_m)
    if part_value is None or whole_value is None:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="percent_is",
        percent_rate=part_value,
        percent_base=whole_value,
        operation="solve",
    )


def _block_percent(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    if intent.percent_rate is None or intent.percent_base is None:
        return None
    answer = math_school.percent_of(intent.percent_rate, intent.percent_base)
    lines.append(f"{intent.percent_rate:g}% of {intent.percent_base:g} = {answer}")
    return _finish_with_answer(lines, answer)


def _block_percent_change(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    if intent.percent_base is None or intent.percent_rate is None:
        return None
    if intent.school_op == "percent_increase":
        answer = math_school.percent_increase(intent.percent_base, intent.percent_rate)
        verb = "increased"
    else:
        answer = math_school.percent_decrease(intent.percent_base, intent.percent_rate)
        verb = "decreased"
    lines.append(f"{intent.percent_base:g} {verb} by {intent.percent_rate:g}% = {answer}")
    return _finish_with_answer(lines, answer)


def _block_percent_is(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    if intent.percent_rate is None or intent.percent_base is None:
        return None
    answer = math_school.percent_is(intent.percent_rate, intent.percent_base)
    lines.append(f"{intent.percent_rate:g} is {answer}% of {intent.percent_base:g}")
    return _finish_with_answer(lines, answer)


def _block_discount(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    from app.modules.math import formulas as math_formulas

    if intent.percent_base is None or intent.percent_rate is None:
        return None
    answer = math_formulas.sale_price(intent.percent_base, intent.percent_rate)
    lines.append(f"{intent.percent_rate:g}% off {intent.percent_base:g} = {answer}")
    return _finish_with_answer(lines, answer)


def _block_percent_change_from(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    from app.modules.math import formulas as math_formulas

    if intent.percent_base is None or intent.percent_rate is None:
        return None
    answer = math_formulas.percent_change_from(intent.percent_base, intent.percent_rate)
    lines.append(
        f"Percent change from {intent.percent_base:g} to {intent.percent_rate:g} = {answer}"
    )
    return _finish_with_answer(lines, answer)

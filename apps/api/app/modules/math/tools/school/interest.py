"""Interest extractor and verified blocks."""

from __future__ import annotations

from app.models.schemas.math import MathIntent
from app.modules.math import match as mtm
from app.modules.math import school as math_school
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.modules.math.tools.school._parse import (
    _count_char,
    _finite_match_value,
    _number_immediately_before,
)
from app.services.text_match import word_index

_INTEREST_YEAR_MAX = 100


def _extract_interest_intent(cleaned: str, lower: str) -> MathIntent | None:
    compound = word_index(lower, "compound") != -1
    simple = word_index(lower, "simple") != -1
    if compound == simple:
        return None
    if simple and "interest" not in lower:
        return None
    if compound and "interest" not in lower and "amount" not in lower:
        return None
    if _count_char(cleaned, "%") != 1:
        return None
    if any(
        word_index(lower, word) != -1
        for word in ("month", "months", "weekly", "daily", "continuous")
    ):
        return None
    nums = list(mtm._NUM.finditer(cleaned))
    if len(nums) != 3:
        return None
    on_at = word_index(lower, "on")
    if on_at == -1:
        on_at = word_index(lower, "of")
    year_at = lower.find("year")
    pct_at = cleaned.find("%")
    if on_at == -1 or year_at == -1 or pct_at == -1:
        return None
    principal_m = mtm._NUM.search(cleaned, on_at + 2)
    rate_m = _number_immediately_before(cleaned, pct_at)
    years_m = _number_immediately_before(cleaned, year_at)
    if principal_m is None or rate_m is None or years_m is None:
        return None
    if {principal_m.span(), rate_m.span(), years_m.span()} != {match.span() for match in nums}:
        return None
    principal = _finite_match_value(principal_m)
    rate = _finite_match_value(rate_m)
    years_value = _finite_match_value(years_m)
    if principal is None or rate is None or years_value is None:
        return None
    if principal <= 0 or rate < 0 or not years_value.is_integer():
        return None
    years = int(years_value)
    if years < 1 or years > _INTEREST_YEAR_MAX:
        return None
    if simple:
        op = "simple_interest"
    elif word_index(lower, "amount") != -1 and "interest" not in lower:
        op = "compound_amount"
    else:
        op = "compound_interest"
    return MathIntent(
        kind="arithmetic",
        school_op=op,
        percent_base=principal,
        percent_rate=rate,
        combo_n=years,
        operation="solve",
    )


def _block_present_value(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    from app.modules.math import formulas as math_formulas

    if intent.percent_base is None or intent.percent_rate is None or intent.combo_n is None:
        return None
    answer = math_formulas.present_value(intent.percent_base, intent.percent_rate, intent.combo_n)
    lines.append(f"Present value = {answer}")
    return _finish_with_answer(lines, answer)


def _block_interest(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    if intent.percent_base is None or intent.percent_rate is None or intent.combo_n is None:
        return None
    principal, rate, years = intent.percent_base, intent.percent_rate, intent.combo_n
    if intent.school_op == "simple_interest":
        answer = math_school.simple_interest(principal, rate, years)
        label = "Simple interest"
    elif intent.school_op == "compound_amount":
        answer = math_school.compound_amount(principal, rate, years)
        label = "Compound amount"
    else:
        answer = math_school.compound_interest(principal, rate, years)
        label = "Compound interest"
    lines.append(f"{label} on {principal:g} at {rate:g}% for {years} years = {answer}")
    return _finish_with_answer(lines, answer)

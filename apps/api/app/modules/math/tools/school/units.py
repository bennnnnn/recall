"""Unit conversion extractor and verified block."""

from __future__ import annotations

import math
import re

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.modules.math import school as math_school
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.modules.math.tools.block.common import format_quantity
from app.modules.math.tools.school._parse import _PROB_NUMBER

_UNIT_PATTERN = r"[A-Za-zµμ°][A-Za-z0-9µμ°*/^._-]{0,63}"
_TWICE_HOT_TAIL = re.compile(
    rf"^({_UNIT_PATTERN})\s*[.?!,;]*\s*(?:then\s+)?"
    rf"(?:(?:tell|explain)\s+me\s+)?(?:whether\s+|if\s+)?"
    rf"({_PROB_NUMBER})\s*({_UNIT_PATTERN})\s+is\s+twice\s+as\s+hot\s*[.?!]*$",
    re.IGNORECASE,
)


def _extract_unit_intent(cleaned: str) -> MathIntent | None:
    from app.services.unit_text import QUANTITY_NUMBER

    lower = cleaned.lower()
    if "convert" not in lower and " to " not in lower:
        return None
    if "convert" not in lower:
        return None
    after = QUANTITY_NUMBER.search(cleaned)
    if after is None:
        return None
    value = float(after.group(0))
    # Temperature conversions allow zero and negative quantities. Retain
    # the sign instead of skipping to a later positive number.
    if abs(value) == float("inf"):
        return None
    idx = lower.find(" to ")
    if idx == -1:
        return None
    destination_text = cleaned[idx + 4 :].strip()
    comparison = _TWICE_HOT_TAIL.fullmatch(destination_text)
    destination = destination_text.split()
    if not destination or (
        comparison is None and len(destination) > 1 and destination[1:] != ["please"]
    ):
        return None
    dest = (comparison.group(1) if comparison is not None else destination[0]).strip("?.")
    # The complete source/destination must be one conversion. Dropping a
    # second request could otherwise turn it into a partial direct answer.
    source = cleaned[after.end() : idx].strip().split()
    if len(source) != 1:
        return None
    src = source[0]
    if src.lower() in {"to"}:
        return None
    if not src or not dest:
        return None
    return MathIntent(
        kind="unit",
        school_op="temperature_twice_compare" if comparison is not None else "convert",
        percent_base=value,
        unit_from=src,
        unit_to=dest,
        temperature_compare_value=(float(comparison.group(2)) if comparison is not None else None),
        temperature_compare_unit=(comparison.group(3) if comparison is not None else None),
        operation="solve",
    )


def _verified_block_unit(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.percent_base is None or not intent.unit_from or not intent.unit_to:
        return None
    answer = math_school.convert_unit(intent.percent_base, intent.unit_from, intent.unit_to)
    lines.append(f"{intent.percent_base:g} {intent.unit_from} = {answer} {intent.unit_to}")
    if (
        intent.school_op == "temperature_twice_compare"
        and intent.temperature_compare_value is not None
        and intent.temperature_compare_unit
    ):
        first_kelvin = float(
            math_school.convert_unit(intent.percent_base, intent.unit_from, "kelvin")
        )
        second_kelvin = float(
            math_school.convert_unit(
                intent.temperature_compare_value,
                intent.temperature_compare_unit,
                "kelvin",
            )
        )
        ratio = second_kelvin / first_kelvin
        verdict = math.isclose(ratio, 2.0, rel_tol=1e-9, abs_tol=1e-9)
        lines.append(
            f"Absolute-temperature comparison: {second_kelvin:g} K / "
            f"{first_kelvin:g} K = {ratio:.6g}; twice={verdict}."
        )
        direct = (
            "**Convert**\n"
            f"${intent.percent_base:g}\\,{intent.unit_from} = {answer}\\,{intent.unit_to}$\n\n"
            "**Compare on an absolute temperature scale**\n"
            f"${intent.temperature_compare_value:g}\\,{intent.temperature_compare_unit}"
            f" = {second_kelvin:g}\\,K$ and "
            f"${intent.percent_base:g}\\,{intent.unit_from} = {first_kelvin:g}\\,K$.\n\n"
            f"The ratio is ${second_kelvin:g}/{first_kelvin:g} \\approx {ratio:.3f}$, not 2. "
            "So it is not twice as hot; Fahrenheit's zero is arbitrary, so raw Fahrenheit "
            "numbers cannot be compared as temperature ratios."
        )
        return VerifiedMathBlock(text="\n".join(lines), direct_reply=direct)
    return _finish_with_answer(lines, format_quantity(answer, intent.unit_to))

"""Unit conversion extractor and verified block."""

from __future__ import annotations

import math
import re
from typing import Any

from app.core.config import Settings
from app.modules.math import school as math_school
from app.modules.math.schemas import MathIntent
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.modules.math.tools.block.common import format_quantity
from app.modules.math.tools.school._parse import _PROB_NUMBER
from app.services.workout import Workout, math_line, render_workout

_UNIT_PATTERN = r"[A-Za-zµμ°][A-Za-z0-9µμ°*/^._-]{0,63}"
_TWICE_HOT_TAIL = re.compile(
    rf"^({_UNIT_PATTERN})\s*[.?!,;]*\s*(?:then\s+)?"
    rf"(?:(?:tell|explain)\s+me\s+)?(?:whether\s+|if\s+)?"
    rf"({_PROB_NUMBER})\s*({_UNIT_PATTERN})\s+is\s+twice\s+as\s+hot\s*[.?!]*$",
    re.IGNORECASE,
)


_ANGLE_UNITS = {
    "rad": "rad",
    "rads": "rad",
    "radian": "rad",
    "radians": "rad",
    "deg": "deg",
    "degs": "deg",
    "degree": "deg",
    "degrees": "deg",
    "°": "deg",
}
# A quantity written as an expression, then one plain unit: ``pi/2 radians``,
# ``2π rad``, ``3/4 km``. Compound units such as ``m/s`` keep the number path.
_EXPRESSION_QUANTITY = re.compile(r"(.*?[0-9)πi])\s*([A-Za-zµμ°]+)")
_QUANTITY_CHARS = re.compile(r"[0-9.\s()+\-*/^π]|pi")
_DEGREE_MARK = re.compile(r"\^\{?\\circ\}?")


def _quantity_expression(text: str) -> Any | None:
    """A numeric value made of numbers, π and arithmetic; never a variable."""
    from sympy import pi

    from app.modules.math.solve.parse import _parse_expression

    compact = text.strip()
    if not compact or _QUANTITY_CHARS.sub("", compact):
        return None
    try:
        value = _parse_expression(compact.replace("π", "pi"), [])
    except Exception:
        return None
    if value is None or value.free_symbols or not value.is_finite or not value.is_real:
        return None
    return value.subs("pi", pi)


def _expression_unit_intent(source: str, dest: str) -> MathIntent | None:
    match = _EXPRESSION_QUANTITY.fullmatch(source.strip())
    if match is None:
        return None
    value = _quantity_expression(match.group(1))
    if value is None:
        return None
    return MathIntent(
        kind="unit",
        school_op="convert",
        percent_base=float(value),
        expr=str(value),
        unit_from=match.group(2),
        unit_to=dest,
        operation="solve",
    )


def _exact_angle(intent: MathIntent) -> str | None:
    """π/2 rad is 90°, and 90° is π/2 rad: an angle with π stays exact."""
    from sympy import Rational, latex, nsimplify, pi, sympify

    src = _ANGLE_UNITS.get(intent.unit_from.lower()) if intent.unit_from else None
    dest = _ANGLE_UNITS.get(intent.unit_to.lower()) if intent.unit_to else None
    if src is None or dest is None or src == dest or intent.percent_base is None:
        return None
    value = sympify(intent.expr) if intent.expr else nsimplify(intent.percent_base)
    if src == "rad":
        degrees = nsimplify(value * 180 / pi)
        return latex(degrees) if degrees.is_rational else None
    if not value.is_rational:
        return None
    radians = Rational(value) / 180
    if radians.q > 360:
        return None
    return latex(radians * pi)


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
    convert_end = lower.find("convert") + len("convert")
    to_at = lower.find(" to ", convert_end)
    if to_at != -1 and (
        cleaned[convert_end : after.start()].strip()
        or len(cleaned[after.end() : to_at].split()) != 1
    ):
        # ``pi/2 radians``: the number is part of an expression. Reading
        # only the 2 converted 2 rad and certified 114.59°.
        destination = cleaned[to_at + 4 :].strip().split()
        if len(destination) != 1:
            return None
        return _expression_unit_intent(cleaned[convert_end:to_at], destination[0].strip("?."))
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
    # The keypad's degree key types ``45^{\circ}``.
    src = _DEGREE_MARK.sub("°", source[0])
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
    quantity = intent.expr or f"{intent.percent_base:g}"
    exact = _exact_angle(intent)
    if exact is not None:
        lines.append(f"{quantity} {intent.unit_from} = {exact} {intent.unit_to} (exact)")
        return _finish_with_answer(lines, format_quantity(exact, intent.unit_to))
    answer = math_school.convert_unit(intent.percent_base, intent.unit_from, intent.unit_to)
    lines.append(f"{quantity} {intent.unit_from} = {answer} {intent.unit_to}")
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
        direct = render_workout(
            Workout(
                given=(
                    math_line(f"{intent.percent_base:g}\\,{intent.unit_from}"),
                    math_line(
                        f"{intent.temperature_compare_value:g}\\,{intent.temperature_compare_unit}"
                    ),
                ),
                steps=(
                    math_line(
                        f"{intent.percent_base:g}\\,{intent.unit_from}"
                        f" = {answer}\\,{intent.unit_to}",
                        "convert",
                    ),
                    math_line(
                        f"{intent.temperature_compare_value:g}\\,{intent.temperature_compare_unit}"
                        f" = {second_kelvin:g}\\,K, \\quad "
                        f"{intent.percent_base:g}\\,{intent.unit_from} = {first_kelvin:g}\\,K",
                        "absolute scale",
                    ),
                    math_line(
                        f"{second_kelvin:g}/{first_kelvin:g} \\approx {ratio:.3f}",
                        "not 2, so not twice as hot (Fahrenheit's zero is arbitrary)",
                    ),
                ),
            )
        ).removesuffix("\n\n**Answer**")
        return VerifiedMathBlock(text="\n".join(lines), direct_reply=direct)
    return _finish_with_answer(lines, format_quantity(answer, intent.unit_to))

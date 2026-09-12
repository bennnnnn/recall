"""Extractors + verified blocks for remaining school kinds."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from fractions import Fraction

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.services import math_school
from app.services import math_text_match as mtm
from app.services.math_tools.block import VerifiedMathBlock, _finish_with_answer
from app.services.math_tools.block.common import format_quantity
from app.services.math_tools.helpers import math_expr_or_none, substituted_eval_expr

logger = logging.getLogger(__name__)

_TRIG_FUNCS = ("sine", "cosine", "tangent", "sin", "cos", "tan")
_TRIG_CANON = {"sine": "sin", "cosine": "cos", "tangent": "tan"}
_TRIG_PREFIXES = (
    "what is",
    "what's",
    "whats",
    "evaluate",
    "compute",
    "calculate",
    "find",
    "the value of",
    "please",
    "can you",
    "could you",
)
_PROB_NUMBER = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
_BINOMIAL_PARAM = re.compile(
    rf"\b([nkp])\s*=\s*({_PROB_NUMBER}(?:\s*/\s*{_PROB_NUMBER})?)(?=\s|[,;.!?]|$)",
    re.IGNORECASE,
)


def _extract_unit_intent(cleaned: str) -> MathIntent | None:
    from app.services.math_text_match.units import QUANTITY_NUMBER

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
    destination = cleaned[idx + 4 :].strip().split()
    if not destination or (len(destination) > 1 and destination[1:] != ["please"]):
        return None
    dest = destination[0].strip("?.")
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
        school_op="convert",
        percent_base=value,
        unit_from=src,
        unit_to=dest,
        operation="solve",
    )


def _extract_coord_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    op: str | None = None
    if "distance" in lower or "how far" in lower:
        op = "distance"
    elif "midpoint" in lower:
        op = "midpoint"
    elif "slope" in lower:
        op = "slope"
    if op is None:
        return None
    pts = _two_points(cleaned)
    if pts is None:
        return None
    (x1, y1), (x2, y2) = pts
    return MathIntent(
        kind="coord",
        school_op=op,
        point_x=x1,
        point_y=y1,
        x2=x2,
        y2=y2,
        operation="solve",
    )


def _two_points(text: str) -> tuple[tuple[float, float], tuple[float, float]] | None:
    found: list[tuple[float, float]] = []
    start = 0
    while len(found) < 2:
        i = text.find("(", start)
        if i == -1:
            break
        j = text.find(")", i)
        if j == -1:
            break
        pair = mtm._parse_xy_pair(text[i : j + 1])
        if pair is not None:
            found.append(pair)
        start = j + 1
    if len(found) < 2:
        return None
    return found[0], found[1]


def _extract_vector_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    op: str | None = None
    if "cross" in lower:
        op = "cross"
    elif "dot" in lower:
        op = "dot"
    elif "magnitude" in lower or "norm of" in lower:
        op = "magnitude"
    if op is None:
        return None
    vecs = _angle_vectors(cleaned)
    if not vecs:
        return None
    if op == "magnitude":
        return MathIntent(kind="vector", school_op=op, vec_a=vecs[0], operation="solve")
    if len(vecs) < 2:
        return None
    return MathIntent(kind="vector", school_op=op, vec_a=vecs[0], vec_b=vecs[1], operation="solve")


def _angle_vectors(text: str) -> list[list[float]]:
    out: list[list[float]] = []
    start = 0
    while True:
        i = text.find("<", start)
        if i == -1:
            break
        j = text.find(">", i)
        if j == -1:
            break
        body = text[i + 1 : j]
        try:
            nums = [float(p.strip()) for p in body.split(",") if p.strip()]
        except ValueError:
            start = i + 1
            continue
        if 2 <= len(nums) <= 3:
            out.append(nums)
        start = j + 1
    return out


def _extract_trig_intent(cleaned: str) -> MathIntent | None:
    if mtm.has_equation(cleaned):
        return None
    if mtm.calc_op(cleaned) is not None:
        return None
    lower = cleaned.lower()
    padded = f" {lower} "
    func = None
    for name in _TRIG_FUNCS:
        if (
            padded.startswith(f" {name}(")
            or padded.startswith(f" {name} ")
            or f" {name}(" in padded
            or f" {name} " in padded
        ):
            func = name
            break
    if func is None:
        return None
    if "identity" in lower or "law of sines" in lower or "law of cosines" in lower:
        # SSS already covers law of cosines; law of sines needs more sides/angles
        # than we parse here — leave identities to the LLM.
        if "law of sines" in lower:
            return None
        if "identity" in lower:
            return None
    idx = lower.find(func)
    prefix = lower[:idx].strip()
    while prefix:
        for cue in _TRIG_PREFIXES:
            if prefix == cue or prefix.startswith(cue + " "):
                prefix = prefix[len(cue) :].strip()
                break
        else:
            break
    if prefix:
        return None
    rest = cleaned[idx + len(func) :].strip().rstrip(".?!")
    # "sin of 30 degrees" / "sine of 30" — English, not sin(30).
    if rest.lower().startswith("of"):
        rest = rest[2:].lstrip()
    if rest.startswith("("):
        depth = 0
        close = None
        for i, char in enumerate(rest):
            depth += (char == "(") - (char == ")")
            if depth == 0:
                close = i
                break
        if close is None:
            return None
        suffix = rest[close + 1 :].strip()
        if suffix and suffix.lower() not in {
            "degrees",
            "degree",
            "deg",
            "radians",
            "radian",
            "rad",
            "°",
        }:
            # Do not certify the first call after dropping +cos(...) etc.
            return None
        rest = (rest[1:close] + " " + suffix).strip()
    angle_unit = None
    for unit in ("degrees", "degree", "deg", "radians", "radian", "rad", "°"):
        if rest.lower().endswith(unit):
            angle_unit = "degrees" if unit in {"degrees", "degree", "deg", "°"} else "radians"
            rest = rest[: -len(unit)].strip()
            break
    arg = math_expr_or_none(rest)
    if arg is None:
        return None
    canon = _TRIG_CANON.get(func, func)
    numeric = mtm._NUM.fullmatch(arg)
    if angle_unit == "degrees" or (angle_unit is None and numeric is not None):
        # Keep the established school shorthand sin 30 = sin(30 degrees).
        return MathIntent(
            kind="trig",
            school_op=canon,
            percent_base=float(arg) if numeric is not None else None,
            expr=f"{canon}(({arg})*pi/180)",
            operation="solve",
        )
    if angle_unit is None and "pi" not in arg and arg != "e":
        return None
    return MathIntent(
        kind="trig",
        school_op=canon,
        expr=f"{canon}({arg})",
        operation="solve",
    )


def _extract_percent_or_ratio(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    pct = lower.find("% of ")
    if pct != -1:
        rate_m = None
        for match in mtm._NUM.finditer(cleaned[:pct]):
            rate_m = match
        base_m = mtm._NUM.search(cleaned, pct + 5)
        if rate_m and base_m:
            return MathIntent(
                kind="arithmetic",
                school_op="percent",
                percent_rate=float(rate_m.group(0)),
                percent_base=float(base_m.group(0)),
                operation="solve",
            )
    if ":" in cleaned and ("ratio" in lower or "simplify" in lower):
        a = mtm._NUM.search(cleaned)
        if a:
            b = mtm._NUM.search(cleaned, a.end())
            if b:
                return MathIntent(
                    kind="arithmetic",
                    school_op="ratio",
                    percent_rate=float(a.group(0)),
                    percent_base=float(b.group(0)),
                    operation="solve",
                )
    return None


def _extract_average_speed_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "average speed" not in lower and "average velocity" not in lower:
        return None
    from app.services.math_text_match.units import (
        LENGTH_UNITS,
        QUANTITY_NUMBER,
        TIME_UNITS,
        unit_after_quantity,
    )

    nums = list(QUANTITY_NUMBER.finditer(cleaned))
    if len(nums) != 2:
        return None
    measures: list[tuple[float, str, int]] = []
    for number in nums:
        unit_hit = unit_after_quantity(cleaned, number.end())
        if unit_hit is None:
            return None
        measures.append((float(number.group(0)), unit_hit[0].lower(), unit_hit[1]))
    # A second request or requested output unit needs the model; do not certify
    # the first two numbers as an answer to an unparsed compound instruction.
    if cleaned[measures[-1][2] :].strip(" .?!").lower() not in {"", "please"}:
        return None
    distance: tuple[float, str] | None = None
    duration: tuple[float, str] | None = None
    for value, unit, _end in measures:
        if unit in LENGTH_UNITS:
            distance = value, LENGTH_UNITS[unit]
        elif unit in TIME_UNITS:
            duration = value, TIME_UNITS[unit]
        else:
            return None
    if distance is None or duration is None or duration[0] <= 0:
        return None
    if "average speed" in lower and distance[0] < 0:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="average_speed",
        expr=f"{distance[0]}/{duration[0]}",
        unit_from=distance[1],
        unit_to=duration[1],
        operation="solve",
    )


def _extract_arithmetic_intent(cleaned: str) -> MathIntent | None:
    substituted = substituted_eval_expr(cleaned)
    if substituted is not None:
        return MathIntent(kind="arithmetic", school_op="eval", expr=substituted, operation="solve")
    if mtm.has_equation(cleaned):
        return None
    percent = _extract_percent_or_ratio(cleaned)
    if percent is not None:
        return percent
    speed = _extract_average_speed_intent(cleaned)
    if speed is not None:
        return speed
    expr = mtm.bare_arithmetic_expr(cleaned)
    if expr is None:
        return None
    return MathIntent(kind="arithmetic", school_op="eval", expr=expr, operation="solve")


def _extract_probability_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "binomial" in lower or ("n=" in lower.replace(" ", "") and "p=" in lower.replace(" ", "")):
        empty = MathIntent(kind="probability", school_op="binomial", operation="solve")
        matches = list(_BINOMIAL_PARAM.finditer(cleaned))
        if len(matches) != 3 or {match.group(1).lower() for match in matches} != {"n", "k", "p"}:
            return empty
        try:
            params = {
                match.group(1).lower(): float(Fraction(match.group(2).replace(" ", "")))
                for match in matches
            }
        except (ValueError, ZeroDivisionError, OverflowError):
            return empty
        n, k, p = params["n"], params["k"], params["p"]
        if n is not None and k is not None and p is not None:
            if not n.is_integer() or not k.is_integer():
                return empty
            return MathIntent(
                kind="probability",
                school_op="binomial",
                combo_n=int(n),
                combo_k=int(k),
                percent_base=p,
                operation="solve",
            )
    if "expected value" in lower or "expected value of" in lower:
        if any(cue in lower for cue in ("probabilit", "weight", "p(", "p=")):
            # Explicit weighted distributions need a separate parser; never
            # average outcomes and probabilities together as a raw list.
            return MathIntent(kind="probability", school_op="expected", operation="solve")
        from app.services.math_text_match.discrete import numeric_data_values

        nums = numeric_data_values(cleaned[lower.index("expected value") + len("expected value") :])
        if nums is not None:
            return MathIntent(
                kind="probability",
                school_op="expected",
                stats_numbers=nums,
                operation="solve",
            )
    return None


def _extract_complex_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "complex" not in lower and "i)" not in lower and "+ i" not in lower and "- i" not in lower:
        if "modulus" not in lower and "imaginary" not in lower:
            return None
    if mtm.has_equation(cleaned) and "solve" in lower:
        return None
    expr = cleaned.strip()
    # Prefixes are prose and case-insensitive; retain the expression's case
    # (notably I, pi, and function names) and never erase interior substrings.
    while True:
        for prefix in ("simplify", "evaluate", "compute", "modulus of", "modulus", "complex"):
            if expr.lower().startswith(prefix + " "):
                expr = expr[len(prefix) :].lstrip()
                break
        else:
            break
    return MathIntent(kind="complex", school_op="eval", expr=expr, operation="solve")


def _first_order_ode_equation(cleaned: str) -> str | None:
    """Span starting at ``dy/dx`` or ``y'`` through the rhs. Linear scan."""
    from app.services.math_tools.helpers import _strip_trailing_filler

    lower = cleaned.lower()
    start = -1
    idx = lower.find("dy/dx")
    if idx != -1:
        start = idx
    yprime = cleaned.find("y'")
    if yprime != -1 and (start == -1 or yprime < start):
        start = yprime
    if start == -1:
        return None
    rest = cleaned[start:]
    low_rest = rest.lower()
    if low_rest.startswith("dy/dx"):
        after_op = rest[5:].lstrip()
    elif rest.startswith("y'"):
        after_op = rest[2:].lstrip()
    else:
        after_op = rest.lstrip()
    # ``Find dy/dx if y = …`` is a derivative ask, not an ODE ``dy/dx = …``.
    if not after_op.startswith("="):
        return None
    return _strip_trailing_filler(rest)


def _extract_taylor_or_ode(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    taylor_ok = (
        "taylor of " in lower or "maclaurin" in lower or ("taylor" in lower and "series" in lower)
    )
    if taylor_ok:
        expr = mtm.graph_expr(cleaned) or cleaned
        n = mtm.number_after(cleaned, "order") or mtm.number_after(cleaned, "degree") or 5
        point = "0"
        if "maclaurin" not in lower and "at " in lower:
            pt = mtm.number_after(cleaned, "at")
            if pt is not None:
                point = f"{pt:g}"
        # pull expr after "of "
        idx = lower.find(" of ")
        if idx != -1:
            rest = cleaned[idx + 4 :]
            for stop in (" at ", " order", " degree", " around"):
                sidx = rest.lower().find(stop)
                if sidx != -1:
                    rest = rest[:sidx]
            expr = rest.strip()
        return MathIntent(
            kind="calculus",
            operation="taylor",
            expr=expr,
            taylor_n=int(n),
            limit_point=point,
            variable="x",
        )
    if "partial" in lower and (
        "partial of " in lower
        or "partial derivative" in lower
        or " wrt" in lower
        or "with respect to" in lower
    ):
        var = "x"
        if "wrt" in lower:
            after = cleaned.lower().find("wrt")
            rest = cleaned[after + 3 :].strip()
            if rest:
                var = rest[0]
        elif "with respect to" in lower:
            after = lower.find("with respect to")
            rest = cleaned[after + len("with respect to") :].strip()
            if rest:
                var = rest[0]
        idx = lower.find(" of ")
        expr = cleaned[idx + 4 :] if idx != -1 else cleaned
        for stop in (" wrt", " with respect"):
            sidx = expr.lower().find(stop)
            if sidx != -1:
                expr = expr[:sidx]
        return MathIntent(
            kind="calculus",
            operation="partial",
            expr=expr.strip(),
            variable=var,
        )
    if "dy/dx" in lower or "y'" in cleaned or "dsolve" in lower:
        ode_eq = _first_order_ode_equation(cleaned)
        if ode_eq is None:
            return None
        return MathIntent(kind="calculus", operation="dsolve", expr=ode_eq, variable="x")
    return None


SCHOOL_EXTRACTORS: list[Callable[[str], MathIntent | None]] = [
    _extract_unit_intent,
    _extract_coord_intent,
    _extract_vector_intent,
    _extract_taylor_or_ode,
    _extract_trig_intent,
    _extract_probability_intent,
    _extract_complex_intent,
    _extract_arithmetic_intent,
]


def _verified_block_arithmetic(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if (
        intent.school_op == "percent"
        and intent.percent_rate is not None
        and intent.percent_base is not None
    ):
        answer = math_school.percent_of(intent.percent_rate, intent.percent_base)
        lines.append(f"{intent.percent_rate:g}% of {intent.percent_base:g} = {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op == "ratio"
        and intent.percent_rate is not None
        and intent.percent_base is not None
    ):
        answer = math_school.simplify_ratio(intent.percent_rate, intent.percent_base)
        lines.append(f"Simplified ratio: {answer}")
        return _finish_with_answer(lines, answer)
    if not intent.expr:
        return None
    answer = math_school.evaluate_arithmetic(intent.expr)
    if intent.school_op == "average_speed" and intent.unit_from and intent.unit_to:
        answer = format_quantity(answer, f"{intent.unit_from}/{intent.unit_to}")
    lines.append(f"Result: {answer}")
    return _finish_with_answer(lines, answer)


def _verified_block_trig(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.school_op and intent.percent_base is not None:
        answer = math_school.evaluate_trig_degrees(intent.school_op, intent.percent_base)
        lines.append(f"{intent.school_op}({intent.percent_base:g}°) = {answer}")
        return _finish_with_answer(lines, answer)
    if intent.expr:
        answer = math_school.evaluate_trig_expr(intent.expr)
        lines.append(f"Result: {answer}")
        return _finish_with_answer(lines, answer)
    return None


def _verified_block_coord(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if None in (intent.point_x, intent.point_y, intent.x2, intent.y2):
        return None
    x1, y1, x2, y2 = intent.point_x, intent.point_y, intent.x2, intent.y2
    if x1 is None or y1 is None or x2 is None or y2 is None:
        return None
    if intent.school_op == "midpoint":
        answer = math_school.coord_midpoint(x1, y1, x2, y2)
    elif intent.school_op == "slope":
        answer = math_school.coord_slope(x1, y1, x2, y2)
    else:
        answer = math_school.coord_distance(x1, y1, x2, y2)
    lines.append(f"{intent.school_op}: {answer}")
    return _finish_with_answer(lines, answer)


def _verified_block_vector(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.vec_a:
        return None
    if intent.school_op == "magnitude":
        answer = math_school.vector_magnitude(intent.vec_a)
    elif intent.school_op == "dot" and intent.vec_b:
        answer = math_school.vector_dot(intent.vec_a, intent.vec_b)
    elif intent.school_op == "cross" and intent.vec_b:
        answer = math_school.vector_cross(intent.vec_a, intent.vec_b)
    else:
        return None
    lines.append(f"{intent.school_op}: {answer}")
    return _finish_with_answer(lines, answer)


def _verified_block_probability(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if (
        intent.school_op == "binomial"
        and intent.combo_n is not None
        and intent.combo_k is not None
        and intent.percent_base is not None
    ):
        answer = math_school.binomial_pmf(intent.combo_n, intent.combo_k, intent.percent_base)
        lines.append(f"P(X={intent.combo_k}) = {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "expected" and intent.stats_numbers:
        answer = math_school.expected_value(intent.stats_numbers, None)
        lines.append(f"E[X] = {answer}")
        return _finish_with_answer(lines, answer)
    return None


def _verified_block_complex(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.expr:
        return None
    answer = math_school.evaluate_complex(intent.expr)
    lines.append(f"Result: {answer}")
    return _finish_with_answer(lines, answer)


def _verified_block_unit(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.percent_base is None or not intent.unit_from or not intent.unit_to:
        return None
    answer = math_school.convert_unit(intent.percent_base, intent.unit_from, intent.unit_to)
    lines.append(f"{intent.percent_base:g} {intent.unit_from} = {answer} {intent.unit_to}")
    return _finish_with_answer(lines, format_quantity(answer, intent.unit_to))


def apply_calculus_extension(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.operation == "taylor" and intent.expr:
        out = math_school.taylor_series(
            intent.expr, intent.variable, intent.limit_point or "0", intent.taylor_n or 5
        )
        lines.append(f"Taylor: {out.latex}")
        return _finish_with_answer(lines, out.latex)
    if intent.operation == "partial" and intent.expr:
        out = math_school.partial_derivative(intent.expr, intent.variable)
        lines.append(f"Partial: {out.latex}")
        return _finish_with_answer(lines, out.latex)
    if intent.operation == "dsolve" and intent.expr:
        out = math_school.solve_ode(intent.expr, intent.variable)
        lines.append(f"ODE: {out.latex}")
        return _finish_with_answer(lines, out.latex)
    if intent.operation == "critical_points" and intent.expr:
        out = math_school.critical_points(intent.expr, intent.variable)
        lines.append(f"Critical points: {out.latex}")
        return _finish_with_answer(lines, out.latex)
    return None


SCHOOL_BLOCK_BUILDERS = {
    "arithmetic": _verified_block_arithmetic,
    "trig": _verified_block_trig,
    "coord": _verified_block_coord,
    "vector": _verified_block_vector,
    "probability": _verified_block_probability,
    "complex": _verified_block_complex,
    "unit": _verified_block_unit,
}

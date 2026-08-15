"""Extractors + verified blocks for remaining school kinds."""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.core.config import Settings
from app.models.math_schemas import MathIntent
from app.services import math_school
from app.services import math_text_match as mtm
from app.services.math_tools.block import VerifiedMathBlock, _finish_with_answer

logger = logging.getLogger(__name__)

_TRIG_FUNCS = ("sin", "cos", "tan")


def _extract_unit_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "convert" not in lower and " to " not in lower:
        return None
    if "convert" not in lower:
        return None
    value = mtm._first_positive_number(cleaned)
    if value is None:
        return None
    idx = lower.find(" to ")
    if idx == -1:
        return None
    dest = cleaned[idx + 4 :].strip().split()[0].strip("?.")
    # source unit: word immediately after the number
    after = mtm._NUM.search(cleaned)
    if after is None:
        return None
    rest = cleaned[after.end() :].strip()
    src = rest.split()[0] if rest else ""
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
    rest = cleaned[idx + len(func) :].lstrip()
    if rest.startswith("("):
        rest = rest[1:].lstrip()
    if not rest or not rest[0].isdigit():
        return None
    num = mtm._NUM.search(cleaned, idx)
    if num is None:
        return None
    degrees = float(num.group(0))
    return MathIntent(
        kind="trig",
        school_op=func,
        percent_base=degrees,
        expr=f"{func}({degrees}*pi/180)",
        operation="solve",
    )


def _extract_percent_or_ratio(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    pct = lower.find("% of ")
    if pct != -1:
        rate_m = mtm._NUM.search(cleaned[:pct])
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


def _extract_arithmetic_intent(cleaned: str) -> MathIntent | None:
    if mtm.has_equation(cleaned):
        return None
    percent = _extract_percent_or_ratio(cleaned)
    if percent is not None:
        return percent
    lower = cleaned.lower()
    if not any(cue in lower for cue in ("what is", "calculate", "compute", "evaluate", "what's")):
        return None
    cues = (
        "what is",
        "what's",
        "calculate",
        "compute",
        "evaluate",
        "the value of",
        "please",
        "?",
    )
    stripped = lower
    for w in cues:
        stripped = stripped.replace(w, " ")
    if any(ch.isalpha() for ch in stripped):
        return None
    if not any(ch.isdigit() for ch in stripped):
        return None
    times, divide = "\u00d7", "\u00f7"
    if not any(op in stripped for op in ("+", "-", "*", "/", times, divide, "^")):
        return None
    expr = stripped.replace(times, "*").replace(divide, "/").strip()
    return MathIntent(kind="arithmetic", school_op="eval", expr=expr, operation="solve")


def _extract_probability_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "binomial" in lower or ("n=" in lower.replace(" ", "") and "p=" in lower.replace(" ", "")):
        n = mtm.number_after(cleaned, "n")
        k = mtm.number_after(cleaned, "k")
        p = mtm.number_after(cleaned, "p")
        if n is not None and k is not None and p is not None:
            return MathIntent(
                kind="probability",
                school_op="binomial",
                combo_n=int(n),
                combo_k=int(k),
                percent_base=p,
                operation="solve",
            )
    if "expected value" in lower or "expected value of" in lower:
        nums = [float(m.group(0)) for m in mtm._NUM.finditer(cleaned)]
        if len(nums) >= 2:
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
    expr = cleaned
    for w in ("simplify", "evaluate", "compute", "modulus of", "modulus", "complex"):
        expr = expr.replace(w, " ")
    return MathIntent(kind="complex", school_op="eval", expr=expr.strip(), operation="solve")


def _extract_taylor_or_ode(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "taylor" in lower:
        expr = mtm.graph_expr(cleaned) or cleaned
        n = mtm.number_after(cleaned, "order") or mtm.number_after(cleaned, "degree") or 5
        point = "0"
        if "at " in lower:
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
    if "partial" in lower:
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
        expr = cleaned
        for w in ("solve", "dsolve", "the ode", "ode"):
            expr = expr.replace(w, " ")
        return MathIntent(kind="calculus", operation="dsolve", expr=expr.strip(), variable="x")
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
        answer = math_school.simplify_ratio(int(intent.percent_rate), int(intent.percent_base))
        lines.append(f"Simplified ratio: {answer}")
        return _finish_with_answer(lines, answer)
    if not intent.expr:
        return None
    answer = math_school.evaluate_arithmetic(intent.expr)
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
    return _finish_with_answer(lines, answer)


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

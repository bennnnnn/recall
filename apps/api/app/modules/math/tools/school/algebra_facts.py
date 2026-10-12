"""Completing the square, and the cosine rule for two sides and the angle between them.

``complete the square x^2 + 6x + 5`` -> ``(x + 3)^{2} - 4``;
``in triangle ABC, a = 7, b = 9, C = 60 degrees, find c`` -> ``\\sqrt{67}``.
"""

from __future__ import annotations

import math
import re
from dataclasses import replace
from typing import Any

from app.modules.math.schemas import MathIntent
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.services.workout import Workout, math_line, render_workout

ALGEBRA_FACT_OPS = frozenset({"complete_square", "cosine_rule"})

_COMPLETE_SQUARE = re.compile(
    r"(?:(?:please\s+)?(?:complete|completing)\s+the\s+square\s+(?:for|of|on|in)?\s*)(?P<expr>.+)"
    r"|(?P<expr2>.+?)\s*,?\s+(?:by\s+)?(?:completing|complete)\s+the\s+square",
    re.IGNORECASE,
)
_NUMBER = r"(\d+(?:\.\d+)?)"
_SIDE = rf"\b([a-c])\s*=\s*{_NUMBER}"
_ANGLE = rf"\b([A-C])\s*=\s*{_NUMBER}\s*(?:°|degrees?|deg)?"
_FIND_SIDE = re.compile(
    r"\b(?:find|calculate|what\s+is|work\s+out)\s+(?:the\s+(?:length\s+of\s+)?)?"
    r"(?:side\s+)?([a-c])\b"
)


def extract_algebra_fact_intent(cleaned: str) -> MathIntent | None:
    body = " ".join(cleaned.split()).strip().rstrip("?.!")
    if not body or len(body) > 200:
        return None
    square = _COMPLETE_SQUARE.fullmatch(body)
    if square is not None:
        from app.modules.math.tools.helpers import math_expr_or_none

        raw = (square["expr"] or square["expr2"] or "").strip(" :")
        raw = re.sub(r"\s*=\s*0$", "", raw)
        expr = math_expr_or_none(raw)
        if expr is None or "=" in expr:
            return None
        return MathIntent(
            kind="arithmetic", school_op="complete_square", expr=expr, operation="solve"
        )
    return _cosine_rule_intent(body)


def _cosine_rule_intent(body: str) -> MathIntent | None:
    """Two sides, the angle between them, and the third side asked for."""
    sides = {match.group(1): float(match.group(2)) for match in re.finditer(_SIDE, body)}
    angles = {match.group(1): float(match.group(2)) for match in re.finditer(_ANGLE, body)}
    find = _FIND_SIDE.search(body)
    if find is None or len(sides) != 2 or len(angles) != 1:
        return None
    target = find.group(1)
    angle_name, angle = next(iter(angles.items()))
    # The included angle is opposite the side asked for: a, b and C give c.
    if angle_name.lower() != target or target in sides or not 0 < angle < 180:
        return None
    (first_name, first), (second_name, second) = sorted(sides.items())
    return MathIntent(
        kind="arithmetic",
        school_op="cosine_rule",
        tri_a=first,
        tri_b=second,
        sector_angle_deg=angle,
        expr=f"{first_name},{second_name},{angle_name},{target}",
        operation="solve",
    )


def algebra_fact_block(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    if intent.school_op == "complete_square":
        return _complete_square(intent, lines)
    return _cosine_rule(intent, lines)


def _complete_square(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    from sympy import Poly, Rational, Symbol, latex, nsimplify

    from app.modules.math import solve as math_solve

    x = Symbol("x")
    try:
        parsed = math_solve._parse_expression(intent.expr or "", ["x"])
        poly = Poly(parsed, x)
    except Exception:
        return None
    if poly.degree() != 2 or poly.free_symbols - {x}:
        return None
    a, b, c = (nsimplify(coefficient) for coefficient in poly.all_coeffs())
    half = Rational(b) / (2 * a)
    shift = c - a * half**2
    inside = latex(x + half)
    squared = rf"\left({inside}\right)^{{2}}"
    lead = "" if a == 1 else ("-" if a == -1 else latex(a))
    answer = f"{lead}{squared}"
    if shift != 0:
        answer += f" {'-' if shift < 0 else '+'} {latex(abs(shift))}"
    rows: list[str] = []
    if a != 1:
        factored = latex(x**2 + (b / a) * x)
        rows.append(
            math_line(
                rf"{latex(parsed)} = {lead}\left({factored}\right) + {latex(c)}",
                f"take out {latex(a)}",
            )
        )
    correction = a * half**2
    removed = f"{lead}{squared} - {latex(correction)} + {latex(c)}".replace("+ -", "- ")
    rows.append(
        math_line(
            removed,
            rf"half of ${latex(Rational(b) / a)}$ is ${latex(half)}$; take away its square",
        )
    )
    lines.append(f"Completed square: {answer}")
    block = _finish_with_answer(lines, answer)
    working = render_workout(Workout(given=(math_line(latex(parsed)),), steps=tuple(rows)), answer)
    return replace(block, worked_reply=working)


def _cosine_rule(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    a, b, angle = intent.tri_a, intent.tri_b, intent.sector_angle_deg
    names = (intent.expr or "").split(",")
    if a is None or b is None or angle is None or len(names) != 4:
        return None
    first, second, angle_name, target = names
    cosine = math.cos(math.radians(angle))
    nice = {60.0: 0.5, 120.0: -0.5, 90.0: 0.0}
    exact_cos = nice.get(angle)
    square = a * a + b * b - 2 * a * b * (exact_cos if exact_cos is not None else cosine)
    if square <= 0:
        return None
    side = math.sqrt(square)
    answer = _side_answer(square, side, exact=exact_cos is not None)
    n = _number
    rows = [
        math_line(
            rf"{target}^2 = {n(a)}^2 + {n(b)}^2 - 2({n(a)})({n(b)})\cos {n(angle)}^\circ",
        ),
        math_line(
            rf"{target}^2 = {n(a * a)} + {n(b * b)} - {n(2 * a * b * (exact_cos or cosine))}"
            rf" = {n(round(square, 4))}"
        ),
    ]
    lines.append(f"{target}^2 = {square:.6g}; {target} = {side:.6g}")
    block = _finish_with_answer(lines, answer)
    working = render_workout(
        Workout(
            given=(
                math_line(f"{first} = {n(a)}"),
                math_line(f"{second} = {n(b)}"),
                math_line(f"{angle_name} = {n(angle)}^\\circ", "the angle between them"),
            ),
            find=(math_line(target),),
            formula=(
                math_line(
                    rf"{target}^2 = {first}^2 + {second}^2 - 2{first}{second}\cos {angle_name}",
                    "Cosine rule",
                ),
            ),
            substitution=tuple(rows),
        ),
        answer,
    )
    return replace(block, worked_reply=working)


def _number(value: Any) -> str:
    return f"{float(value):g}"


def _side_answer(square: float, side: float, *, exact: bool) -> str:
    if abs(side - round(side)) < 1e-9:
        return str(round(side))
    if exact and abs(square - round(square)) < 1e-9:
        return rf"\sqrt{{{round(square)}}} \approx {side:.4g}"
    return f"{side:.4g}"

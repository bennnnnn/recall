"""Coordinate geometry extractor and verified block."""

from __future__ import annotations

import re
from dataclasses import replace

from app.core.config import Settings
from app.modules.math import school as math_school
from app.modules.math.match.coordinate_vector import literal_math_tuples
from app.modules.math.schemas import MathIntent
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.services.workout import Workout, math_line, render_workout


def _extract_coord_intent(cleaned: str) -> MathIntent | None:
    from app.modules.math.tools.extractors.formulas import extract_coord_formulas

    extra = extract_coord_formulas(cleaned)
    if extra is not None:
        return extra
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
    # Literal pairs use Euclidean geometry; spherical/geodesic requests
    # require domain information that these operands do not contain.
    if op == "distance" and re.search(r"\b(?:sphere|spherical|geodesic)\b", lower):
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
    found = literal_math_tuples(text, "(", ")")
    if found is None or len(found) != 2 or any(len(point) != 2 for point in found):
        return None
    return (found[0][0], found[0][1]), (found[1][0], found[1][1])


def _verified_block_coord(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    from app.modules.math import formulas as math_formulas

    if (
        intent.school_op == "point_to_line"
        and intent.point_x is not None
        and intent.point_y is not None
        and intent.vec_a
        and len(intent.vec_a) == 3
    ):
        answer = math_formulas.point_to_line(
            intent.point_x, intent.point_y, intent.vec_a[0], intent.vec_a[1], intent.vec_a[2]
        )
        lines.append(f"point_to_line: {answer}")
        return _finish_with_answer(lines, answer)
    if None in (intent.point_x, intent.point_y, intent.x2, intent.y2):
        return None
    x1, y1, x2, y2 = intent.point_x, intent.point_y, intent.x2, intent.y2
    if x1 is None or y1 is None or x2 is None or y2 is None:
        return None
    if intent.school_op == "line":
        answer = math_formulas.line_through(x1, y1, x2, y2)
    elif intent.school_op == "midpoint":
        answer = math_school.coord_midpoint(x1, y1, x2, y2)
    elif intent.school_op == "slope":
        answer = math_school.coord_slope(x1, y1, x2, y2)
    else:
        answer = math_school.coord_distance(x1, y1, x2, y2)
    lines.append(f"{intent.school_op}: {answer}")
    block = _finish_with_answer(lines, answer)
    working = _coordinate_working(intent.school_op or "distance", (x1, y1), (x2, y2), answer)
    return replace(block, worked_reply=working) if working else block


def _coordinate_working(
    op: str, first: tuple[float, float], second: tuple[float, float], answer: str
) -> str | None:
    """The formula, then the two points put into it, for distance, slope and midpoint."""
    from sympy import latex, nsimplify, sqrt

    a, b = (nsimplify(value) for value in first)
    c, d = (nsimplify(value) for value in second)

    def term(value: object) -> str:
        """A negative coordinate is bracketed where it is subtracted or added."""
        tex = str(latex(value))
        return f"\\left({tex}\\right)" if tex.startswith("-") else tex

    given = (
        math_line(f"\\left({latex(a)}, {latex(b)}\\right)", "first point"),
        math_line(f"\\left({latex(c)}, {latex(d)}\\right)", "second point"),
    )
    if op == "distance":
        dx, dy = c - a, d - b
        squares = dx**2 + dy**2
        value = sqrt(squares)
        root = rf"\sqrt{{{latex(squares)}}}"
        # ``\sqrt{25} = 5``; ``\sqrt{34} \approx 5.831`` (no ``\sqrt{34} = \sqrt{34}``).
        exact = "" if latex(value) == root else f" = {latex(value)}"
        shown = exact if value.is_Integer else f"{exact} \\approx {float(value):.4g}"
        formula = math_line(r"d = \sqrt{(x_2 - x_1)^2 + (y_2 - y_1)^2}", "Distance formula")
        substitution: tuple[str, ...] = (
            math_line(
                rf"d = \sqrt{{\left({latex(c)} - {term(a)}\right)^2 + "
                rf"\left({latex(d)} - {term(b)}\right)^2}}"
            ),
            math_line(rf"= \sqrt{{{term(dx)}^2 + {term(dy)}^2}} = {root}{shown}"),
        )
        find = math_line("d", "distance")
    elif op == "slope":
        if c == a:
            return None
        value = (d - b) / (c - a)
        formula = math_line(r"m = \frac{y_2 - y_1}{x_2 - x_1}", "Slope formula")
        ratio = rf"\frac{{{latex(d - b)}}}{{{latex(c - a)}}}"
        reduced = "" if latex(value) == ratio else f" = {latex(value)}"
        substitution = (
            math_line(
                rf"m = \frac{{{latex(d)} - {term(b)}}}{{{latex(c)} - {term(a)}}} = {ratio}{reduced}"
            ),
        )
        find = math_line("m", "slope")
    elif op == "midpoint":
        mx, my = (a + c) / 2, (b + d) / 2
        value = None
        formula = math_line(
            r"M = \left(\frac{x_1 + x_2}{2}, \frac{y_1 + y_2}{2}\right)", "Midpoint formula"
        )
        substitution = (
            math_line(
                rf"M = \left(\frac{{{latex(a)} + {term(c)}}}{{2}}, "
                rf"\frac{{{latex(b)} + {term(d)}}}{{2}}\right) = "
                rf"\left({latex(mx)}, {latex(my)}\right)"
            ),
        )
        find = math_line("M", "midpoint")
        if f"({float(mx):g}, {float(my):g})" != answer:
            return None
    else:
        return None
    if value is not None and f"{float(value):g}" != answer:
        return None
    return render_workout(
        Workout(given=given, find=(find,), formula=(formula,), substitution=substitution),
        answer,
    )

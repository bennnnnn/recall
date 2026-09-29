"""Coordinate geometry extractor and verified block."""

from __future__ import annotations

import re

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.modules.math import school as math_school
from app.modules.math.match.coordinate_vector import literal_math_tuples
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer


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
    return _finish_with_answer(lines, answer)

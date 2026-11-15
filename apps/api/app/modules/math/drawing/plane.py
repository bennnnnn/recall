"""A polygon at the coordinates the question gives, on its x- and y-axes.

"The triangle whose vertices are (-4, -1), (0, 0) and (5, 4)" is drawn there, never as a
default triangle in its place (round 3, 2026-11-14): every corner is a pair the question
writes, and each is lettered with its own coordinates.
"""

from __future__ import annotations

from fractions import Fraction

from app.modules.math.drawing.arrows import axis
from app.modules.math.drawing.question import Question
from app.modules.math.drawing.vocabulary import ShapePart
from app.modules.math.figure.drawing import Drawing, number_text

_PAST = 0.2
_ARROW = 0.04
_NAME_CHARS = 8


def _coordinates(x: float, y: float) -> str:
    return f"({number_text(x)},{number_text(y)})".replace("-", "\u2212")


def polygon_at(part: ShapePart, question: Question) -> Drawing | None:
    corners = [
        (Fraction(p.at[0]).limit_denominator(10_000), Fraction(p.at[1]).limit_denominator(10_000))
        for p in part.vertices
    ]
    if len(corners) < 3 or len(set(corners)) != len(corners):
        return None
    if not all(corner in question.pairs for corner in corners):
        return None
    twice_area = sum(
        a[0] * b[1] - b[0] * a[1] for a, b in zip(corners, corners[1:] + corners[:1], strict=True)
    )
    if twice_area == 0:
        return None  # corners on one line make no polygon
    drawing = Drawing("polygon")
    xs = [float(x) for x, _ in corners]
    ys = [float(y) for _, y in corners]
    reach = max(max(abs(v) for v in xs), max(abs(v) for v in ys), 1.0)
    size = _ARROW * reach * 2
    for index, (low, high) in enumerate(
        ((min([*xs, 0.0]), max([*xs, 0.0])), (min([*ys, 0.0]), max([*ys, 0.0])))
    ):
        start = [0.0, 0.0]
        end = [0.0, 0.0]
        start[index], end[index] = low - _PAST * reach, high + _PAST * reach
        axis(drawing, (start[0], start[1]), (end[0], end[1]), "xy"[index], size)
    names: list[str] = []
    for given, (x, y) in zip(part.vertices, corners, strict=True):
        written = _coordinates(float(x), float(y))
        name = given.name if given.name and given.name in question.letters else ""
        label = name or (written if len(written) <= _NAME_CHARS else "")
        names.append(drawing.point((float(x), float(y)), label, show=bool(label), dot=True))
    drawing.outline(names)
    return drawing

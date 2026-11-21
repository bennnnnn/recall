"""Angles a question writes with a letter, drawn at their sizes and labelled as written.

"Three angles at a point are x, 2x and 150°" decides x: the angles about a point make 360°,
so x = 70 and the figure's angles are 70°, 140° and 150°. Where the angles' sum decides the
letter exactly (on a straight line 180°, about a point 360°, a right angle 90°, a
triangle's 180°, a quadrilateral's 360°) the server solves it with SymPy and draws every
angle at its size; each one the question writes with the letter is labelled as written
("2x"), never with the size worked out, which is the student's to find. A sum that leaves
the letter open, two letters, a term that is no line in one letter, or an angle that comes
out at 0° or less, or at 180° or more, draws nothing.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from sympy import Rational

from app.modules.math.figure.drawing import angle_label
from app.modules.math.figure.request import ANGLE_WHATS, FigureRequest, Measure
from app.modules.math.schemas.figure import FigureSpec
from app.modules.math.tool_check import parse_formula

# What the angles at one place add up to, by the figure's shape.
WHOLES: dict[str, float] = {
    "angles_on_line": 180.0,
    "supplementary_angles": 180.0,
    "angles_at_point": 360.0,
    "complementary_angles": 90.0,
    "triangle": 180.0,
    "quadrilateral": 360.0,
}
_MINUSES = str.maketrans({"\u2212": "-", "\u2013": "-"})
_DEGREE = re.compile(r"\s*(?:°|º|degrees?)\s*$")


@dataclass(frozen=True)
class Sized:
    """One angle of the figure: its size, its label and the letters naming it ("" for none)."""

    size: float
    label: str
    name: str


def compact(text: str) -> str:
    """A text without spaces, its minus signs one kind, its case one: the form a copied term
    is matched in."""
    return re.sub(r"\s+", "", text.translate(_MINUSES).lower())


def terms_written(request: FigureRequest, texts: Sequence[str]) -> bool:
    """Every term the reading holds is one the question writes, letter and all."""
    written = [compact(text) for text in texts]
    for item in request.angle_terms:
        term = compact(_DEGREE.sub("", item.term))
        if not re.search(r"[a-z]", term) or not any(term in text for text in written):
            return False
    return True


def sized_angles(request: FigureRequest, whole: float) -> list[Sized] | None:
    """The stated angles and the lettered ones at their sizes, solved so they make
    ``whole``; None when the terms do not decide one size for each."""
    stated = [m for m in request.measures if m.what in ANGLE_WHATS]
    if len(stated) != len(request.measures):
        return None
    exprs = []
    for item in request.angle_terms:
        parsed = parse_formula(_DEGREE.sub("", item.term).translate(_MINUSES))
        if parsed is None:
            return None
        exprs.append(parsed)
    letters = {symbol for expr in exprs for symbol in expr.free_symbols}
    if len(letters) != 1:
        return None
    letter = letters.pop()
    total = sum(exprs) + sum(Rational(str(m.value)) for m in stated)
    slope = total.diff(letter)
    if not slope.is_number or slope == 0 or total.diff(letter, 2) != 0:
        return None
    root = (Rational(str(whole)) - total.subs(letter, 0)) / slope
    sizes = [expr.subs(letter, root) for expr in exprs]
    if not all(size.is_number and size.is_rational for size in sizes):
        return None
    found = [
        Sized(float(size), item.term.strip(), item.name.strip())
        for size, item in zip(sizes, request.angle_terms, strict=True)
    ]
    found += [Sized(m.value, "", m.name.strip()) for m in stated]
    return found if all(0 < angle.size < 180 for angle in found) else None


def term_labels(request: FigureRequest) -> frozenset[str]:
    """The labels a figure of lettered angles carries that measure nothing themselves."""
    return frozenset(item.term.strip() for item in request.angle_terms)


def build_lettered_triangle(request: FigureRequest) -> FigureSpec | None:
    """A triangle whose angles the question writes with a letter ("x, 2x and 3x"), drawn at
    the sizes their 180° decides, each labelled as written."""
    from app.modules.math.figure.triangles import build_triangle

    sized = sized_angles(request, 180.0)
    letters = request.vertices.strip()
    lettered = len(letters) == 3 and len(set(letters)) == 3 and letters.isalpha()
    names = list(letters) if lettered else ["A", "B", "C"]
    if sized is None or len(sized) != 3:
        return None
    placed: dict[str, Sized] = {}
    for angle in [a for a in sized if a.name] + [a for a in sized if not a.name]:
        vertex = angle.name[1] if len(angle.name) == 3 else angle.name[:1]
        if not vertex:
            vertex = next((n for n in names if n not in placed), "")
        if vertex not in names or vertex in placed:
            return None
        placed[vertex] = angle
    measures = [
        Measure(what="angle", name=vertex, value=angle.size) for vertex, angle in placed.items()
    ]
    spec = build_triangle(
        request.model_copy(
            update={"vertices": "".join(names), "measures": measures, "angle_terms": []}
        )
    )
    if spec is None:
        return None
    for mark in spec.angles:
        if mark.at in placed:
            mark.label = placed[mark.at].label or angle_label(placed[mark.at].size)
    for point in spec.points:
        point.show = point.show and lettered
    return spec

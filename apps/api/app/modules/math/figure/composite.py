"""A plane shape made of two: a rectangle (or a square) with a second shape joined to a side.

A semicircle on a side (or cut out of it), a triangle on its top (a house's gable), a second
rectangle or square beside it (an L-shape). The reading names the main ``shape``, the
``attached`` one, and which part each value is ``of``. Each part is drawn to its stated
sizes, the line where the two meet dashed, and only stated values are labelled, once each:
the side a semicircle sits on is its diameter, so "a rectangle 10 cm by 6 cm with a
semicircle on a 6 cm side" labels the 6 once. Sizes that cannot meet (a semicircle wider
than every side, a gable whose slanting sides are too short to meet over the top, a second
rectangle too wide for every side) draw nothing.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

from app.modules.math.figure.drawing import Drawing, length_label, polar
from app.modules.math.figure.request import FigureRequest, Measure
from app.modules.math.schemas.figure import FigureSpec

_MAINS = frozenset({"rectangle", "square"})
_TRIANGLES = frozenset({"triangle", "isosceles_triangle", "equilateral_triangle"})
ATTACHED = frozenset({"semicircle", *_TRIANGLES, "rectangle", "square"})
# The words that name each attached part in a question.
_NAMED_BY: dict[str, tuple[str, ...]] = {
    "semicircle": ("semicirc", "semi-circ", "half circle", "half-circle", "half a circle"),
    "triangle": ("triang", "gable", "roof"),
    "rectangle": ("rectang", "l-shape", "l shape", "oblong"),
    "square": ("square",),
}
_TRIANGLE_ROLES = frozenset({"equal_side", "slant_height", "leg", "hypotenuse", "apex_angle"})
_ONLY_ATTACHED = {
    "semicircle": frozenset({"radius", "diameter"}),
    **dict.fromkeys(_TRIANGLES, _TRIANGLE_ROLES),
}
_SECOND = frozenset({"second", "attached", "other", "smaller", "small", "top"})
_TOLERANCE = 1e-6
# What a gable leaves open: its height against its base.
_GABLE = 0.45
# A radius drawn from the centre of a semicircle, at this angle from its diameter.
_RADIUS_TURN = 60.0
_CUT = frozenset({"cut", "cut_out", "removed", "hole"})


def names_part(texts: Iterable[str], attached: str) -> bool:
    """The question names the attached part ("semicircle", "triangle"): a reading's second
    shape the question never mentions is none of its figure."""
    stems = _NAMED_BY["triangle"] if attached in _TRIANGLES else _NAMED_BY.get(attached)
    words = " ".join(texts).lower()
    return stems is not None and any(re.search(rf"\b{re.escape(s)}", words) for s in stems)


def _split(request: FigureRequest) -> tuple[list[Measure], list[Measure]]:
    """The main shape's measures and the attached one's, by what each is ``of``."""
    attached = request.attached
    own = {attached, attached.removeprefix("isosceles_").removeprefix("equilateral_")}
    main: list[Measure] = []
    part: list[Measure] = []
    for m in request.measures:
        theirs = m.of in _SECOND or (m.of in own and attached != request.shape)
        # A size only the attached part has is its own, whatever the reading says it is of.
        theirs = theirs or m.what in _ONLY_ATTACHED.get(attached, frozenset())
        (part if theirs else main).append(m)
    if attached == request.shape and not part and len(main) == 4:
        return main[:2], main[2:]  # "6 m by 4 m joined to 3 m by 2 m": in the order written
    return main, part


def _box(measures: list[Measure], square: bool) -> tuple[float | None, float | None] | None:
    """A rectangle's stated length (along its base) and width, or a square's side twice."""
    by: dict[str, float] = {m.what: m.value for m in measures}
    if len(by) != len(measures):
        return None
    if square:
        side = by.get("side", by.get("length", by.get("edge")))
        return (side, side) if len(measures) <= 1 else None
    plain = [m.value for m in measures if m.what == "side"]
    if "height" in by:
        # "8 m wide and 4 m high": the width (or length) runs along, the height up.
        across = [by[what] for what in ("length", "base", "width", "breadth") if what in by]
        if len(across) > 1 or plain:
            return None
        return (across[0] if across else None), by["height"]
    length = by.get("length", by.get("base"))
    width = by.get("width", by.get("breadth"))
    if plain:
        if length is not None or width is not None or len(plain) > 2:
            return None
        return (plain[0], plain[1] if len(plain) == 2 else None)
    return length, width


def build_composite(request: FigureRequest) -> FigureSpec | None:
    if request.shape not in _MAINS or request.attached not in ATTACHED:
        return None
    main, part = _split(request)
    box = _box(main, request.shape == "square")
    if box is None:
        return None
    if request.attached == "semicircle":
        return _semicircle(request, box, part)
    if request.attached in _TRIANGLES:
        return _gable(request, box, part)
    other = _box(part, request.attached == "square")
    return None if other is None else _second_box(request, box, other)


def _semicircle_sides(
    box: tuple[float | None, float | None], across: float | None
) -> tuple[float, float | None, float | None, float | None] | None:
    """The side the semicircle stands on and the other one, and the stated value of each
    (None where the question states none): a stated diameter picks the side as long."""
    length, width = box
    if across is None:
        sides = sorted(size for size in box if size is not None)
        if not sides:
            return 4.0, None, None, None
        rest = sides[1] if len(sides) == 2 else None
        return sides[0], rest, sides[0], rest
    for side, other in ((length, width), (width, length)):
        if side is not None and abs(side - across) < _TOLERANCE:
            return side, other, side, other
    if length is not None and width is not None:
        return None  # the semicircle fits neither side
    rest = length if length is not None else width
    return across, rest, None, rest


def _semicircle(
    request: FigureRequest, box: tuple[float | None, float | None], part: list[Measure]
) -> FigureSpec | None:
    """The semicircle stands on the side as long as its diameter, drawn as the top; one cut
    out of the shape bites into it instead."""
    if len(part) > 1:
        return None
    radius = next((m.value for m in part if m.what == "radius"), None)
    diameter = next((m.value for m in part if m.what == "diameter"), None)
    across = diameter if diameter is not None else 2 * radius if radius is not None else None
    sides = _semicircle_sides(box, across)
    if sides is None:
        return None
    top, up, top_stated, up_stated = sides
    square = request.shape == "square"
    if square:
        up, up_stated = top, None
    height = up if up is not None else top * 0.8
    cut = any(item in _CUT for item in request.parts)
    if cut and top / 2 >= height:
        return None
    unit = request.unit
    drawing = Drawing("rectangle_semicircle_cut" if cut else "rectangle_semicircle")
    a, b = drawing.point((0.0, 0.0)), drawing.point((top, 0.0))
    c, d = drawing.point((top, height)), drawing.point((0.0, height))
    shown = top_stated if top_stated is not None else diameter
    ticks = 1 if square else 0
    drawing.line(a, b, length_label(shown, unit) if shown is not None else None, ticks=ticks)
    drawing.line(b, c, ticks=ticks)
    side = length_label(up_stated, unit) if up_stated is not None else None
    drawing.line(d, a, side, ticks=ticks)
    drawing.line(c, d, dashed=True)
    centre = drawing.point((top / 2, height), dot=radius is not None)
    drawing.arc(centre, top / 2, start=180 if cut else 0, end=360 if cut else 180)
    if radius is not None:
        turn = -_RADIUS_TURN if cut else _RADIUS_TURN
        edge = drawing.point(polar(top / 2, turn, (top / 2, height)))
        drawing.line(centre, edge, length_label(radius, unit), dashed=True)
    if not cut:
        drawing.faces.append([a, b, c, d])
    drawing.angle(a, b, d, right=True)
    drawing.angle(b, c, a, right=True)
    return drawing.spec()


def _gable(
    request: FigureRequest, box: tuple[float | None, float | None], part: list[Measure]
) -> FigureSpec | None:
    """A triangle on the rectangle's top, its apex over the top's middle: its height, its
    slanting sides or (equilateral) the top itself decide where."""
    length, width = box
    base = length or 6.0
    height = width or base * 0.6
    gable_height = next((m.value for m in part if m.what == "height"), None)
    slant = next(
        (m.value for m in part if m.what in {"side", "equal_side", "length", "slant_height"}),
        None,
    )
    if len(part) > 1 + (gable_height is not None and slant is not None):
        return None
    equilateral = request.attached == "equilateral_triangle"
    if equilateral:
        if slant is not None and abs(slant - base) > _TOLERANCE:
            return None
        rise = base * math.sqrt(3) / 2
    elif slant is not None:
        if slant <= base / 2:
            return None
        rise = math.sqrt(slant * slant - base * base / 4)
    else:
        rise = gable_height if gable_height is not None else base * _GABLE
    if gable_height is not None and abs(gable_height - rise) > 1e-4 * rise:
        return None
    unit = request.unit
    drawing = Drawing("rectangle_triangle")
    a, b = drawing.point((0.0, 0.0)), drawing.point((base, 0.0))
    c, d = drawing.point((base, height)), drawing.point((0.0, height))
    apex = drawing.point((base / 2, height + rise))
    drawing.line(a, b, length_label(length, unit) if length is not None else None)
    square = request.shape == "square"
    side = length_label(width, unit) if width is not None and not square else None
    drawing.line(b, c, side, ticks=1 if square else 0)
    drawing.line(d, a, ticks=1 if square else 0)
    drawing.line(c, d, dashed=True)
    ticks = 1 if equilateral or slant is not None or gable_height is None else 0
    drawing.line(c, apex, length_label(slant, unit) if slant is not None else None, ticks=ticks)
    drawing.line(apex, d, ticks=ticks)
    if gable_height is not None:
        middle = drawing.point((base / 2, height))
        drawing.line(apex, middle, length_label(gable_height, unit), dashed=True)
        drawing.angle(middle, c, apex, right=True)
    drawing.faces.append([a, b, c, apex, d])
    drawing.angle(a, b, d, right=True)
    drawing.angle(b, c, a, right=True)
    return drawing.spec()


def _second_box(
    request: FigureRequest,
    box: tuple[float | None, float | None],
    other: tuple[float | None, float | None],
) -> FigureSpec | None:
    """An L-shape: the second rectangle on the first's top, flush with its left side, the
    way round that fits."""
    if None in box or None in other:
        return None
    length, width = float(box[0] or 0), float(box[1] or 0)
    first, second = float(other[0] or 0), float(other[1] or 0)
    fits = [(a, u) for a, u in ((first, second), (second, first)) if a <= length + _TOLERANCE]
    if not fits:
        return None
    along, up = fits[0]
    unit = request.unit
    drawing = Drawing("l_shape")
    p0, p1 = drawing.point((0.0, 0.0)), drawing.point((length, 0.0))
    p2 = drawing.point((length, width))
    p3 = p2 if abs(along - length) < _TOLERANCE else drawing.point((along, width))
    p4, p5 = drawing.point((along, width + up)), drawing.point((0.0, width + up))
    join = drawing.point((0.0, width))
    # A square's side is stated once: labelled once.
    main_side = None if request.shape == "square" else length_label(width, unit)
    second_side = None if request.attached == "square" else length_label(up, unit)
    drawing.line(p0, p1, length_label(length, unit))
    drawing.line(p1, p2, main_side)
    if p3 != p2:
        drawing.line(p2, p3)
    drawing.line(p3, p4, second_side)
    drawing.line(p4, p5, length_label(along, unit))
    drawing.line(p5, join)
    drawing.line(join, p0)
    drawing.line(join, p3, dashed=True)
    outline = [p0, p1, p2] + ([p3] if p3 != p2 else []) + [p4, p5]
    drawing.faces.append(outline)
    return drawing.spec()

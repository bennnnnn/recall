"""Similar triangles: two lettered triangles drawn side by side to one scale, and the shadow
problem's upright objects beside their shadows.

"Triangles ABC and DEF are similar" pairs A with D, B with E and C with F. A side stated in
both triangles gives the scale (DE / AB); every other stated side or angle of either is
carried over, the first triangle is drawn from them (``triangles``), and the second is the
first at that scale. Two pairs that give different scales, or no pair at all, draw nothing.

Shadows cast at one time are similar right triangles: an object's height over its shadow is
the same for each (the sun's elevation, when the question states it, gives it too). Each
object stands at its own place along the ground, its height up, its shadow along the ground
and the sun's ray dashed from its top to the shadow's end; only stated values are labelled,
a height or a shadow worked out is drawn to size. The objects are told apart by what each
measure is ``of`` ("pole", "tree"); values the reading does not tell apart draw nothing.
"""

from __future__ import annotations

import math

from app.modules.math.figure import triangles
from app.modules.math.figure.drawing import Drawing, Point, angle_label, length_label
from app.modules.math.figure.request import ANGLE_WHATS, FigureRequest, Measure
from app.modules.math.schemas.figure import FigureSpec

_TOLERANCE = 1e-4
# The space between two drawn parts, as a share of the larger one's width.
_GAP = 0.35
_MAX_OBJECTS = 3


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= _TOLERANCE * max(1.0, abs(b))


def _vertex(name: str) -> str:
    return name[1] if len(name) == 3 else name[:1]


def _scale(request: FigureRequest, first: str, second: str) -> float | None:
    """DE / AB from a side the question states in both triangles; None when none or two
    disagree."""
    pairing = dict(zip(second, first, strict=True))
    sides: dict[frozenset[str], float] = {}
    for m in request.measures:
        name = m.name.strip()
        if m.what not in ANGLE_WHATS and len(name) == 2 and set(name) <= set(first):
            sides[frozenset(name)] = m.value
    found: list[float] = []
    for m in request.measures:
        name = m.name.strip()
        if m.what not in ANGLE_WHATS and len(name) == 2 and set(name) <= set(second):
            match = sides.get(frozenset(pairing[letter] for letter in name))
            if match is not None:
                found.append(m.value / match)
    if not found or any(not _close(k, found[0]) for k in found):
        return None
    return found[0]


def _first_triangle(request: FigureRequest, first: str, second: str, k: float) -> FigureRequest:
    """The first triangle's reading: its own values, and the second's carried over at 1/k."""
    pairing = dict(zip(second, first, strict=True))
    measures: dict[str, Measure] = {}
    for m in request.measures:
        name = m.name.strip()
        if m.what in ANGLE_WHATS:
            letter = _vertex(name)
            vertex = pairing.get(letter, letter)
            angle = Measure(what="angle", name=vertex, value=m.value)
            measures.setdefault(f"angle {vertex}", angle)
        else:
            own = "".join(pairing.get(letter, letter) for letter in name)
            value = m.value if set(name) <= set(first) else m.value / k
            side = Measure(what="side", name=own, value=value)
            measures.setdefault(f"side {''.join(sorted(own))}", side)
    return request.model_copy(
        update={"shape": "triangle", "vertices": first, "measures": list(measures.values())}
    )


def build_similar(request: FigureRequest) -> FigureSpec | None:
    letters = request.vertices.strip()
    if len(letters) != 6 or len(set(letters)) != 6 or not letters.isalpha():
        return None
    first, second = letters[:3], letters[3:]
    for m in request.measures:
        name = m.name.strip()
        named = len(name) == 2 if m.what not in ANGLE_WHATS else len(name) in {1, 3}
        if not named or not (set(name) <= set(first) or set(name) <= set(second)):
            return None
    k = _scale(request, first, second)
    if k is None:
        return None
    base = triangles.build_triangle(_first_triangle(request, first, second, k))
    if base is None:
        return None
    at = {p.name: (p.x, p.y) for p in base.points if p.name in first}
    if len(at) != 3:
        return None
    corners = [at[letter] for letter in first]
    left = min(x for x, _ in corners)
    width = max(x for x, _ in corners) - left
    shift = width + _GAP * width * max(1.0, k)
    drawing = Drawing("similar_triangles")
    for names, scale, offset in ((first, 1.0, 0.0), (second, k, shift)):
        for letter, (x, y) in zip(names, corners, strict=True):
            drawing.point((offset + (x - left) * scale, y * scale), letter, show=True)
        drawing.outline(list(names))
    _label(drawing, request)
    return drawing.spec()


def _label(drawing: Drawing, request: FigureRequest) -> None:
    for m in request.measures:
        name = m.name.strip()
        if m.what in ANGLE_WHATS:
            letter = _vertex(name)
            ends = [s.b if s.a == letter else s.a for s in drawing.segments if letter in {s.a, s.b}]
            drawing.angle(letter, ends[0], ends[1], angle_label(m.value))
        else:
            drawing.label_side(name[0], name[1], length_label(m.value, request.unit))


def build_shadows(request: FigureRequest) -> FigureSpec | None:
    objects = _objects(request)
    if objects is None:
        return None
    sun = request.first("angle")
    ratios = [h / s for h, s in objects if h is not None and s is not None]
    if sun is not None:
        if not 0 < sun < 90:
            return None
        ratios.append(math.tan(math.radians(sun)))
    if not ratios or any(not _close(r, ratios[0]) for r in ratios):
        return None
    ratio = ratios[0]
    sizes = [_sized(h, s, ratio) for h, s in objects]
    return _draw_shadows(request, objects, sizes, sun)


def _sized(height: float | None, shadow: float | None, ratio: float) -> tuple[float, float]:
    """An object's height and shadow, the one left open from the other at the sun's ratio."""
    if height is None:
        return float(shadow or 0) * ratio, float(shadow or 0)
    return height, shadow if shadow is not None else height / ratio


def _objects(request: FigureRequest) -> list[tuple[float | None, float | None]] | None:
    """Each object's stated height and shadow, in the order the reading names them."""
    order: list[str] = []
    found: dict[str, list[float | None]] = {}
    for m in request.measures:
        if m.what == "angle":
            continue
        if m.what not in {"height", "shadow"}:
            return None
        # The object a value is of, or the word the reading named it by ("pole").
        owner = m.of or (m.name.strip().lower() if len(m.name.strip()) > 1 else "")
        if owner not in found:
            order.append(owner)
            found[owner] = [None, None]
        slot = 0 if m.what == "height" else 1
        if found[owner][slot] is not None:
            return None  # two heights of one object: the reading does not tell them apart
        found[owner][slot] = m.value
    if not 1 <= len(order) <= _MAX_OBJECTS or ("" in found and len(order) > 1):
        return None
    return [(found[name][0], found[name][1]) for name in order]


def _draw_shadows(
    request: FigureRequest,
    objects: list[tuple[float | None, float | None]],
    sizes: list[tuple[float, float]],
    sun: float | None,
) -> FigureSpec:
    unit = request.unit
    drawing = Drawing("shadows")
    gap = _GAP * max(s for _, s in sizes)
    x = 0.0
    sun_labelled = False
    for (stated_h, stated_s), (h, s) in zip(objects, sizes, strict=True):
        foot: Point = (x, 0.0)
        base = drawing.point(foot)
        top = drawing.point((x, h))
        tip = drawing.point((x + s, 0.0))
        drawing.line(base, top, length_label(stated_h, unit) if stated_h is not None else None)
        drawing.line(base, tip, length_label(stated_s, unit) if stated_s is not None else None)
        drawing.line(top, tip, dashed=True)
        drawing.angle(base, tip, top, right=True)
        label = angle_label(sun) if sun is not None and not sun_labelled else None
        sun_labelled = sun_labelled or label is not None
        drawing.angle(tip, base, top, label)
        x += s + gap
    return drawing.spec()

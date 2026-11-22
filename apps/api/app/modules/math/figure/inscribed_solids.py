"""A sphere inside a cylinder or a cube, drawn true to the sizes the question states.

A sphere that fits exactly inside a cylinder has the cylinder's radius, and the cylinder is
its diameter tall; inside a cube, the cube's edge is its diameter. So one stated size (the
sphere's radius, the cylinder's height, the cube's edge) draws the whole figure, and the
sizes worked from it are drawn unlabelled. A sphere the question makes smaller (a ball of
radius 3 in a cylinder of radius 5) rests on the bottom, in the middle. Sizes that cannot
hold (a sphere wider or taller than what holds it) draw nothing.

The read names the sphere ``inscribed`` in the solid, or ``attached`` to it as a solid made
of two: the question's words ("fits exactly inside", "inscribed in") say it is inside, never
on top (2026-11-21: "a sphere of radius 5 cm fits exactly inside a cylinder" drew nothing).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.modules.math.figure.drawing import Drawing, length_label
from app.modules.math.figure.projection import TEXTBOOK, box_drawing
from app.modules.math.figure.request import FigureRequest, Measure
from app.modules.math.figure.solids import cylinder_drawing, round_base
from app.modules.math.schemas.figure import FigureSpec

_OUTERS = frozenset({"cylinder", "cube"})
_SPHERES = frozenset({"sphere", "ball"})
_INSIDE = re.compile(
    r"\b(?:inside|inscribed|fits?|fitted|fitting|within|enclosed|contained|encloses|holds?)\b"
    r"|\bin(?:to)? (?:a|an|the) (?:[a-z]+ ){0,3}(?:cylind|cub)"
)
_SPHERE_WORD = re.compile(r"\b(?:spher|ball)")
_TOLERANCE = 1e-4
_RADIUS = 2.0
# A solid's own sizes, besides its radius: a cylinder's height, a cube's edge.
_SIZE_WHATS = frozenset({"height", "edge", "side", "length", "width"})


def as_said(request: FigureRequest, texts: Sequence[str]) -> FigureRequest | None:
    """A sphere the question puts inside a cylinder or a cube, read as inside it: shape the
    holder, ``inscribed`` the sphere. A sphere read as joined to one is inside it only where
    the question says so, and is left as read where it does not. A sphere read as inside
    that the question does not put inside ("a hemisphere fits inside", "a cone fits inside",
    "sits on top of") draws nothing: no sphere is drawn into it (review, #2522)."""
    if request.kind != "solid":
        return request
    pair = {request.shape, request.attached}
    inside = request.inscribed in _SPHERES and request.shape in _OUTERS
    if not inside and not (pair & _SPHERES and pair & _OUTERS and len(pair) == 2):
        return request
    words = " ".join(texts).lower()
    if not (_INSIDE.search(words) and _SPHERE_WORD.search(words)) or "hemispher" in words:
        return None if inside else request
    outer = next(iter(pair & _OUTERS))
    return request.model_copy(update={"shape": outer, "attached": "", "inscribed": "sphere"})


def holds_sphere(request: FigureRequest) -> bool:
    """The reading is a sphere inside a cylinder or a cube."""
    return request.inscribed in _SPHERES and request.shape in _OUTERS


def _radius_of(m: Measure) -> float:
    return m.value / 2 if m.what == "diameter" else m.value


def _whose(m: Measure) -> str:
    """Whose size a measure is: the sphere's, the holder's, or "" when the read says not."""
    if m.of in _SPHERES:
        return "sphere"
    return "outer" if m.of in _OUTERS or m.of in {"box", "container", "can", "tin"} else ""


def _sizes(request: FigureRequest) -> tuple[list[float], list[float], list[float]] | None:
    """The radii stated of the sphere, of the holder and of neither; None for a value of no
    part of the figure (a sphere's height, an angle)."""
    sphere: list[float] = []
    outer: list[float] = []
    loose: list[float] = []
    for m in request.measures:
        whose = _whose(m)
        if m.what in {"radius", "diameter"}:
            {"sphere": sphere, "outer": outer, "": loose}[whose].append(_radius_of(m))
        elif m.what not in _SIZE_WHATS or whose == "sphere":
            return None
    return sphere, outer, loose


def _agree(values: list[float]) -> float | None:
    """The one value a list states (several must agree), or None for none; raises on two."""
    if any(abs(v - values[0]) > _TOLERANCE * values[0] for v in values):
        raise ValueError("two different sizes for one part")
    return values[0] if values else None


def _own_size(request: FigureRequest) -> float | None:
    """The holder's height (a cylinder's) or edge (a cube's), as stated."""
    return _agree([m.value for m in request.measures if m.what in _SIZE_WHATS])


def _radii(request: FigureRequest) -> tuple[float, float, float] | None:
    """The sphere's radius, the holder's (half the cube's edge), and its height (the cube's
    edge): what each states, the rest as a sphere that fits exactly."""
    found = _sizes(request)
    if found is None:
        return None
    sphere_r, outer_r, loose = found
    try:
        if len(set(loose)) == 2 and not sphere_r and not outer_r:
            sphere_r, outer_r = [min(loose)], [max(loose)]  # the smaller fits in the larger
        elif loose:
            if sphere_r:
                outer_r = [*outer_r, *loose]
            else:
                sphere_r = list(loose)
        s, big, tall = _agree(sphere_r), _agree(outer_r), _own_size(request)
    except ValueError:
        return None
    if request.shape == "cube":
        if big is not None:
            return None  # a cube has no radius
        big = tall / 2 if tall is not None else None
    s = s if s is not None else big if big is not None else tall / 2 if tall else _RADIUS
    big = big if big is not None else s
    tall = tall if tall is not None else 2 * big
    if s > big * (1 + _TOLERANCE) or 2 * s > tall * (1 + _TOLERANCE):
        return None  # a sphere wider or taller than what holds it
    return s, big, tall


def _placed(request: FigureRequest, s: float, big: float) -> tuple[Measure | None, Measure | None]:
    """The stated size labelled on the sphere and the one on its holder (a cylinder's radius
    that differs from the sphere's, or one the read gives the cylinder); a size stated twice
    is labelled once. Raises on a size with no place."""
    on_sphere: Measure | None = None
    on_holder: Measure | None = None
    for m in (m for m in request.measures if m.what in {"radius", "diameter"}):
        r, whose = _radius_of(m), _whose(m)
        fits_sphere = whose != "outer" and abs(r - s) <= _TOLERANCE * s
        fits_holder = whose != "sphere" and abs(r - big) <= _TOLERANCE * big
        if on_sphere is None and fits_sphere:
            on_sphere = m
        elif (
            on_holder is None
            and fits_holder
            and request.shape == "cylinder"
            and (whose == "outer" or not _same(m, on_sphere, request.unit))
        ):
            on_holder = m
        elif not any(_same(m, other, request.unit) for other in (on_sphere, on_holder)):
            raise ValueError("a size the figure has no place for")
    return on_sphere, on_holder


def _same(m: Measure, other: Measure | None, unit: str) -> bool:
    return other is not None and length_label(m.value, unit) == length_label(other.value, unit)


def build_inscribed(request: FigureRequest) -> FigureSpec | None:
    found = _radii(request)
    if found is None:
        return None
    s, big, tall = found
    try:
        on_sphere, on_holder = _placed(request, s, big)
        own = _own_size(request)
    except ValueError:
        return None
    unit = request.unit
    own_label = length_label(own, unit) if own is not None else None
    if request.shape == "cube":
        labels = {1: own_label} if own_label else {}
        drawing = box_drawing("sphere_in_cube", (tall, tall, tall), labels)
        centre_xy = TEXTBOOK((tall / 2, tall / 2, tall / 2))
    else:
        label = length_label(on_holder.value, unit) if on_holder is not None else None
        across = on_holder is not None and on_holder.what == "diameter"
        drawing = cylinder_drawing(
            big,
            tall,
            height=own_label,
            radius=None if across else label,
            diameter=label if across else None,
            shape="sphere_in_cylinder",
        )
        centre_xy = (0.0, s)
    _sphere(drawing, centre_xy, s, on_sphere, unit)
    return drawing.spec()


def _sphere(
    drawing: Drawing, centre_xy: tuple[float, float], s: float, size: Measure | None, unit: str
) -> None:
    """The sphere: its outline, its equator (the back half dashed), its stated size."""
    centre = drawing.point(centre_xy, dot=True)
    drawing.arc(centre, s)
    round_base(drawing, centre, s)
    cx, cy = centre_xy
    edge = drawing.point((cx + s, cy))
    label = length_label(size.value, unit) if size is not None else None
    if size is not None and size.what == "diameter":
        drawing.line(drawing.point((cx - s, cy)), edge, label, dashed=True, label_at=0.75)
    else:
        drawing.line(centre, edge, label)

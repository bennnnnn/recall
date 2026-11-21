"""A solid made of round solids stacked on one axis: a cone on a hemisphere (a toy), a
hemisphere on a cone (an ice cream), a cone or a hemisphere on a cylinder, a cylinder with a
hemisphere at each end (a capsule), a cylinder standing in a hemisphere.

The reading's ``shape`` is the part named first and ``attached`` the part joined to it; each
measure says which part it is ``of``. Every part shares one radius (the circle where they
meet): two radii stated must agree. A part's height is its own: a cone's along its axis, a
cylinder's along its side; a hemisphere's is its radius. A height the reading does not tie
to a part is the one part's that has a height of its own, or nothing is drawn. The solid is
drawn upright as the round solids are (``solids``), each stated size on its own part, true
to scale; one left open is drawn in proportion, unlabelled.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.modules.math.figure.drawing import Drawing, length_label
from app.modules.math.figure.projection import ELLIPSE
from app.modules.math.figure.request import FigureRequest, Measure
from app.modules.math.figure.solids import round_base
from app.modules.math.schemas.figure import FigureSpec

# Each reading's parts, bottom to top: a "bowl" is a hemisphere with its flat face up, a
# "dome" one with it down; a cone points up or down.
_STACKS: dict[tuple[str, str], tuple[str, ...]] = {
    ("hemisphere", "cone"): ("bowl", "cone_up"),
    ("cone", "hemisphere"): ("cone_down", "dome"),
    ("cylinder", "hemisphere"): ("cylinder", "dome"),
    ("cylinder", "cone"): ("cylinder", "cone_up"),
    ("hemisphere", "cylinder"): ("bowl", "cylinder"),
    ("cone", "cylinder"): ("cone_down", "cylinder"),
    ("cylinder", "hemispheres"): ("bowl", "cylinder", "dome"),
    ("cylinder", "two_hemispheres"): ("bowl", "cylinder", "dome"),
}
_SOLID_OF = {"bowl": "hemisphere", "dome": "hemisphere", "cone_up": "cone", "cone_down": "cone"}
_TOLERANCE = 1e-4
_RADIUS = 2.0
# What a part leaves open, against the radius: a cone's height, a cylinder's.
_CONE, _CYLINDER = 1.6, 1.5


def stacks(request: FigureRequest) -> bool:
    return (request.shape, request.attached) in _STACKS


@dataclass
class _Part:
    kind: str
    height: float | None = None
    slant: float | None = None


def _owner(m: Measure, parts: list[_Part]) -> list[_Part]:
    solid = m.of.removesuffix("s")
    return [p for p in parts if _SOLID_OF.get(p.kind, p.kind) == solid]


def _read(request: FigureRequest, parts: list[_Part]) -> float | bool | None:
    """The shared radius (None when none is stated), each part's height and slant set;
    False when the values do not fit the parts."""
    radii: list[float] = []
    loose: list[Measure] = []
    for m in request.measures:
        if m.what == "radius":
            radii.append(m.value)
        elif m.what == "diameter":
            radii.append(m.value / 2)
        elif m.what in {"height", "slant_height"}:
            owners = [p for p in _owner(m, parts) if p.kind not in {"bowl", "dome"}]
            if m.of and not owners:
                return False
            if not m.of:
                loose.append(m)
                continue
            if not _set(owners[0], m):
                return False
        else:
            return False
    for m in loose:
        tall = [p for p in parts if p.kind not in {"bowl", "dome"}]
        open_parts = [p for p in tall if (p.height if m.what == "height" else p.slant) is None]
        if len(tall) != 1 and len(open_parts) != 1:
            return False
        if not _set((open_parts or tall)[0], m):
            return False
    if any(abs(r - radii[0]) > _TOLERANCE * radii[0] for r in radii):
        return False
    return radii[0] if radii else None


def _set(part: _Part, m: Measure) -> bool:
    if m.what == "slant_height":
        if part.slant is not None or not part.kind.startswith("cone"):
            return False
        part.slant = m.value
    else:
        if part.height is not None:
            return False
        part.height = m.value
    return True


def _sizes(parts: list[_Part], r: float) -> list[float] | None:
    """Each part's height along the axis; a cone's from its slant when only that is given."""
    found: list[float] = []
    for part in parts:
        if part.kind in {"bowl", "dome"}:
            found.append(r)
            continue
        h = part.height
        if part.slant is not None:
            if part.slant <= r:
                return None
            rise = math.sqrt(part.slant**2 - r * r)
            if h is not None and abs(rise - h) > _TOLERANCE * h:
                return None
            h = rise
        found.append(h if h is not None else r * (_CYLINDER if part.kind == "cylinder" else _CONE))
    return found


def build_stacked(request: FigureRequest) -> FigureSpec | None:
    kinds = _STACKS.get((request.shape, request.attached))
    if kinds is None:
        return None
    parts = [_Part(kind) for kind in kinds]
    radius = _read(request, parts)
    if radius is False:
        return None
    r = float(radius) if isinstance(radius, float) else _RADIUS
    sizes = _sizes(parts, r)
    if sizes is None:
        return None
    unit = request.unit
    drawing = Drawing(f"{request.shape}_{request.attached}")
    y = 0.0
    tops: list[str] = []
    for index, (part, size) in enumerate(zip(parts, sizes, strict=True)):
        ends = (index == 0, index == len(parts) - 1)
        tops.append(_draw_part(drawing, part, (y, y + size), r, unit, ends))
        y += size
    # The radius on the circle where the first two parts meet, from its centre.
    joint = next(p for p in drawing.points if p.name == tops[0])
    joint.dot = True
    edge = drawing.point((r, joint.y))
    label = length_label(radius, unit) if isinstance(radius, float) else None
    drawing.line(joint.name, edge, label, dashed=True)
    return drawing.spec()


def _draw_part(
    drawing: Drawing,
    part: _Part,
    span: tuple[float, float],
    r: float,
    unit: str,
    ends: tuple[bool, bool],
) -> str:
    """One part from height ``span[0]`` to ``span[1]``, its circles as ellipses (a circle
    two parts share drawn once, by the lower); returns the centre of its top circle.
    ``ends``: the part is the lowest, the highest."""
    y, top = span
    low, high = drawing.point((0.0, y)), drawing.point((0.0, top))
    height = length_label(part.height, unit) if part.height is not None else None
    slant = length_label(part.slant, unit) if part.slant is not None else None
    if part.kind == "bowl":
        drawing.arc(high, r, start=180, end=360)
        round_base(drawing, high, r)
    elif part.kind == "dome":
        drawing.arc(low, r, start=0, end=180)
    elif part.kind == "cylinder":
        drawing.line(drawing.point((-r, y)), drawing.point((-r, top)))
        drawing.line(drawing.point((r, y)), drawing.point((r, top)), height)
        if ends[0]:
            round_base(drawing, low, r)
        if ends[1]:
            drawing.arc(high, r, r * ELLIPSE)
        else:
            round_base(drawing, high, r)
    elif part.kind == "cone_up":
        drawing.line(drawing.point((-r, y)), high)
        drawing.line(drawing.point((r, y)), high, slant)
        drawing.line(high, low, height, dashed=True)
    else:  # cone_down: its point at the bottom, its rim on top
        drawing.line(low, drawing.point((-r, top)))
        drawing.line(low, drawing.point((r, top)), slant)
        drawing.line(high, low, height, dashed=True)
        round_base(drawing, high, r)
    return high

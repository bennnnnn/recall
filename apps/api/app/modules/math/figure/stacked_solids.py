"""A solid made of round solids stacked on one axis: a cone on a hemisphere (a toy), a
hemisphere on a cone (an ice cream), a cone or a hemisphere on a cylinder, a cylinder with a
hemisphere at each end (a capsule), a cylinder standing in a hemisphere.

The reading's ``shape`` is the part named first and ``attached`` the part joined to it; each
measure says which part it is ``of``. Every part shares one radius (the circle where they
meet): two radii stated must agree. A part's height is its own: a cone's along its axis, a
cylinder's along its side; a hemisphere's is its radius. The whole solid's height (``of``
"total", or the question's "total height", "15.5 cm tall altogether") is all the parts'
together: the one part with a height left open takes what the rest leave, drawn
unlabelled beside the whole's, labelled. A height the reading ties to no part is the one
the question writes it with ("a cone of height 8 cm"), or nothing is drawn: "the total
height of the toy is 15.5 cm" was drawn as a 15.5 cm cone on its hemisphere (2026-11-21).
The solid is drawn upright as the round solids are (``solids``), each stated size on its
own part, true to scale; one left open is drawn in proportion, unlabelled.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
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
# What a reading names the whole solid's height ``of``.
WHOLE = frozenset({"total", "overall", "whole", "entire", "combined"})
# The whole's height drawn beside the solid, this far out against the radius.
_BESIDE = 1.4
# Where a written height is the whole solid's: "the total height ... is 15.5 cm", "a toy of
# overall height 15.5 cm", "15.5 cm tall altogether".
_TOTAL_BEFORE = re.compile(
    r"\b(?:total|overall|whole|entire|combined|complete)\s+(?:height|length)\b[^\d.;]*$"
    r"|\b(?:height|length)\s+of\s+the\s+(?:whole|entire|complete)\b[^\d.;]*$"
)
_TOTAL_AFTER = re.compile(
    r"^\s*(?:[a-z]+\s+)?(?:(?:tall|high|long|in height|in length)\s+)?"
    r"(?:altogether|in all|overall|in total)\b"
)
_SOLID_WORDS = re.compile(r"\b(cones?|cylinders?|hemispheres?)\b")


def stacks(request: FigureRequest) -> bool:
    return (request.shape, request.attached) in _STACKS


@dataclass
class _Part:
    kind: str
    height: float | None = None
    slant: float | None = None


def heights_as_said(request: FigureRequest, texts: Sequence[str]) -> FigureRequest | None:
    """The reading with each height tied to what the question writes it of: the whole solid
    where it says "total height" (``of`` "total"), else the part named before it in its
    sentence ("a cone of height 8 cm": the cone's). The words win over a read that tied it
    to nothing or to no part ("toy"); a read "total" the question writes as a part's height
    is dropped when that part's is read too (one number read twice), and any other
    disagreement draws nothing."""
    if request.kind != "solid" or not stacks(request):
        return request
    words = " ".join(texts).lower()
    parts = {_SOLID_OF.get(kind, kind) for kind in _STACKS[(request.shape, request.attached)]}
    measures: list[Measure] = []
    for m in request.measures:
        said = _written_of(words, m.value) if m.what == "height" else None
        own = m.of.removesuffix("s") in parts
        if said is None or said == m.of.removesuffix("s"):
            measures.append(m)
        elif said == "total" and not own:
            measures.append(m.model_copy(update={"of": "total"}))
        elif said != "total" and m.of in WHOLE and _read_twice(request, m, said):
            continue
        elif said != "total" and not own and m.of not in WHOLE:
            measures.append(m.model_copy(update={"of": said}))
        else:
            return None  # the read and the question give the height to different parts
    return request.model_copy(update={"measures": measures})


def _read_twice(request: FigureRequest, m: Measure, part: str) -> bool:
    """The read gives this value to ``part`` as well: the question's one number read twice."""
    return any(
        other is not m and other.what == m.what and other.value == m.value
        and other.of.removesuffix("s") == part
        for other in request.measures
    )  # fmt: skip


def _written_of(words: str, value: float) -> str | None:
    """What the question writes a height of: "total" (the whole solid's), the solid named
    last before it in its sentence ("cone"), or None when it is not found or names none."""
    found = re.search(rf"(?<![\d.]){re.escape(f'{value:g}')}(?![\d]|\.\d)", words)
    if found is None:
        return None
    sentence = re.split(r"[.;?!](?:\s|$)", words[: found.start()])[-1]
    if _TOTAL_BEFORE.search(sentence) or _TOTAL_AFTER.match(_unit_rest(words, found.end())):
        return "total"
    named = _SOLID_WORDS.findall(sentence)
    return named[-1].removesuffix("s") if named else None


def _unit_rest(words: str, end: int) -> str:
    """The words after a number, its unit skipped ("15.5 cm tall": " tall")."""
    rest = words[end:]
    unit = re.match(r"\s*(?:mm|cm|m|km|in|ft|millimetres?|centimetres?|metres?)\b", rest)
    return rest[unit.end() :] if unit else rest


def _owner(m: Measure, parts: list[_Part]) -> list[_Part]:
    solid = m.of.removesuffix("s")
    return [p for p in parts if _SOLID_OF.get(p.kind, p.kind) == solid]


@dataclass
class _Read:
    """The shared radius (None when none is stated) and the whole solid's height."""

    radius: float | None
    total: float | None


def _read(request: FigureRequest, parts: list[_Part]) -> _Read | None:
    """The shared radius and the whole's height, each part's height and slant set; None
    when the values do not fit the parts. A height tied to no part draws nothing: the
    whole's and a part's are both written "height"."""
    radii: list[float] = []
    totals: list[float] = []
    for m in request.measures:
        if m.what == "radius":
            radii.append(m.value)
        elif m.what == "diameter":
            radii.append(m.value / 2)
        elif m.what in {"height", "length"} and m.of in WHOLE:
            totals.append(m.value)
        elif m.what in {"height", "slant_height"}:
            owners = [p for p in _owner(m, parts) if p.kind not in {"bowl", "dome"}]
            loose_slant = not m.of and m.what == "slant_height"
            if loose_slant:
                owners = [p for p in parts if p.kind.startswith("cone")]
            if len(owners) != 1 or not _set(owners[0], m):
                return None
        else:
            return None
    if len(totals) > 1 or any(abs(r - radii[0]) > _TOLERANCE * radii[0] for r in radii):
        return None
    return _Read(radii[0] if radii else None, totals[0] if totals else None)


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


def _sizes(parts: list[_Part], r: float, total: float | None) -> list[float] | None:
    """Each part's height along the axis; a cone's from its slant when only that is given,
    and the one part left open takes what the whole's height leaves (the rest must fit)."""
    found: list[float | None] = []
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
        found.append(h)
    open_parts = [i for i, size in enumerate(found) if size is None]
    if total is not None:
        known = sum(size for size in found if size is not None)
        if not open_parts:
            if abs(known - total) > _TOLERANCE * total:
                return None
        elif len(open_parts) > 1 or total - known <= _TOLERANCE * total:
            return None
        else:
            found[open_parts[0]] = total - known
    return [
        size if size is not None else r * (_CYLINDER if part.kind == "cylinder" else _CONE)
        for part, size in zip(parts, found, strict=True)
    ]


def build_stacked(request: FigureRequest) -> FigureSpec | None:
    kinds = _STACKS.get((request.shape, request.attached))
    if kinds is None:
        return None
    parts = [_Part(kind) for kind in kinds]
    read = _read(request, parts)
    if read is None:
        return None
    radius = read.radius
    # Unstated, the radius is the picture's choice: small enough to leave the whole's
    # height room for its open part.
    r = radius if radius is not None else min(_RADIUS, (read.total or 4 * _RADIUS) / 4)
    sizes = _sizes(parts, r, read.total)
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
    label = length_label(radius, unit) if radius is not None else None
    drawing.line(joint.name, edge, label, dashed=True)
    if read.total is not None:
        # The whole's height beside the solid, from its lowest point to its highest.
        side = -_BESIDE * r
        bottom, top = drawing.point((side, 0.0)), drawing.point((side, y))
        drawing.line(bottom, top, length_label(read.total, unit), dashed=True)
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

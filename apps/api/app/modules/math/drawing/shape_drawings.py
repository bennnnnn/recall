"""Each word-problem shape drawn from its sizes, its parts labelled where they are.

The solids are ``figure.solids``' own drawers: a round solid seen from a little above, its
circles ellipses with their back halves dashed; a box in the one projection every solid
keeps (``figure.projection``). A labelled part is
drawn at its true length on the flat drawing (a radius across, a height upright), so a
stated value sits on a part of that length (``figure.honest`` checks it). A size the
question leaves open is drawn in proportion and carries its letter only.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from app.modules.math.figure.drawing import Drawing, polar
from app.modules.math.figure.projection import ELLIPSE, box_drawing
from app.modules.math.figure.solids import (
    cone_drawing,
    cylinder_drawing,
    round_base,
    sphere_drawing,
)

Shown = dict[str, str]
# A dimension line stands this far beside its shape, as a share of the shape's width.
_BESIDE = 0.3
# The short marks closing each end of a dimension line, as a share of its length.
_END = 0.06


def _dimension(
    drawing: Drawing, a: tuple[float, float], b: tuple[float, float], label: str
) -> None:
    """A length shown beside a shape: a line its true length, closed by a mark at each end."""
    start, end = drawing.point(a), drawing.point(b)
    drawing.line(start, end, label)
    # Across the line, a share of its length each way.
    across = (-(b[1] - a[1]) * _END, (b[0] - a[0]) * _END)
    for x, y in (a, b):
        drawing.line(
            drawing.point((x - across[0], y - across[1])),
            drawing.point((x + across[0], y + across[1])),
        )


def window(sizes: Sequence[float], shown: Shown) -> Drawing:
    r, h = sizes
    d = Drawing("window")
    corners = [d.point(p) for p in ((-r, 0.0), (r, 0.0), (r, h), (-r, h))]
    centre = d.point((0.0, h))
    d.line(corners[0], corners[1], shown.get("width"))
    d.line(corners[1], corners[2], shown.get("height"))
    d.line(corners[3], corners[0])
    # The semicircle's diameter, where it meets the rectangle.
    d.line(corners[3], corners[2], dashed=True)
    d.arc(centre, r, start=0, end=180)
    d.line(centre, d.point(polar(r, 50, (0.0, h))), shown.get("radius"), dashed=True)
    d.faces = [corners]
    return d


def rectangle(sizes: Sequence[float], shown: Shown) -> Drawing:
    w, h = sizes
    d = Drawing("rectangle")
    corners = [d.point(p) for p in ((0.0, 0.0), (w, 0.0), (w, h), (0.0, h))]
    d.outline(corners)
    d.label_side(corners[0], corners[1], shown.get("width"))
    d.label_side(corners[1], corners[2], shown.get("height"))
    return d


def square(sizes: Sequence[float], shown: Shown) -> Drawing:
    (s,) = sizes
    d = Drawing("square")
    corners = [d.point(p) for p in ((0.0, 0.0), (s, 0.0), (s, s), (0.0, s))]
    d.outline(corners)
    for i, corner in enumerate(corners):
        d.label_side(corner, corners[(i + 1) % 4], None, ticks=1)
    d.label_side(corners[0], corners[1], shown.get("side"))
    return d


def circle(sizes: Sequence[float], shown: Shown) -> Drawing:
    (r,) = sizes
    d = Drawing("circle")
    centre = d.point((0.0, 0.0), dot=True)
    d.arc(centre, r)
    across = "diameter" in shown
    d.line(centre, d.point(polar(r, 45 if across else 0)), shown.get("radius"))
    if across:
        d.line(d.point((-r, 0.0)), d.point((r, 0.0)), shown["diameter"], dashed=True, label_at=0.75)
    return d


def cylinder(sizes: Sequence[float], shown: Shown) -> Drawing:
    r, h = sizes
    return cylinder_drawing(
        r, h, height=shown.get("height"), radius=shown.get("radius"), diameter=shown.get("diameter")
    )


def cone(sizes: Sequence[float], shown: Shown) -> Drawing:
    r, h = sizes
    return cone_drawing(
        r,
        h,
        height=shown.get("height"),
        radius=shown.get("radius"),
        diameter=shown.get("diameter"),
        slant=shown.get("slant"),
    )


def sphere(sizes: Sequence[float], shown: Shown) -> Drawing:
    (r,) = sizes
    return sphere_drawing(r, radius=shown.get("radius"), diameter=shown.get("diameter"))


def frustum(sizes: Sequence[float], shown: Shown) -> Drawing:
    r, big, h = sizes
    d = Drawing("frustum")
    bottom, top = d.point((0.0, 0.0), dot=True), d.point((0.0, h), dot=True)
    round_base(d, bottom, big)
    d.arc(top, r, r * ELLIPSE)
    d.line(d.point((-big, 0.0)), d.point((-r, h)))
    d.line(d.point((big, 0.0)), d.point((r, h)))
    d.line(bottom, top, shown.get("height"), dashed=True)
    d.line(bottom, d.point((big, 0.0)), shown.get("bottom_radius"), dashed=True)
    d.line(top, d.point((r, h)), shown.get("top_radius"))
    return d


def box(sizes: Sequence[float], shown: Shown, *, lid: bool = True) -> Drawing:
    long, w, h = sizes
    # Its width going back, its length across, its height up (``figure.projection``).
    labels = {
        axis: shown[part] for axis, part in ((1, "length"), (2, "height"), (0, "width"))
        if part in shown
    }  # fmt: skip
    return box_drawing("box" if lid else "open_box", (w, long, h), labels, lid=lid)


def sheet(sizes: Sequence[float], shown: Shown) -> Drawing:
    """The sheet with a square cut from each corner, then the open box it folds into."""
    long, w, x = sizes
    d = Drawing("sheet")
    corners = [d.point(p) for p in ((0.0, 0.0), (long, 0.0), (long, w), (0.0, w))]
    d.outline(corners)
    d.label_side(corners[0], corners[1], shown.get("length"))
    d.label_side(corners[3], corners[0], shown.get("width"))
    inner = [(x, x), (long - x, x), (long - x, w - x), (x, w - x)]
    edges = [((x, 0.0), (x, x)), ((0.0, x), (x, x))]
    for cx, cy in inner[1:]:
        ex = cx + (x if cx > x else -x)
        ey = cy + (x if cy > x else -x)
        edges += [((cx, ey), (cx, cy)), ((ex, cy), (cx, cy))]
    for i, (a, b) in enumerate(edges):
        d.line(d.point(a), d.point(b), shown.get("cut") if i == 0 else None)
    folds = [d.point(p) for p in inner]
    for i, name in enumerate(folds):
        d.line(name, folds[(i + 1) % 4], dashed=True)
    folded = box(
        (long - 2 * x, w - 2 * x, x), {"height": shown["cut"]} if "cut" in shown else {}, lid=False
    )
    return beside([d, folded], "sheet")


def ladder(sizes: Sequence[float], shown: Shown) -> Drawing:
    a, b = sizes
    d = Drawing("ladder")
    corner, top, foot = d.point((0.0, 0.0)), d.point((0.0, b)), d.point((a, 0.0))
    d.line(corner, top, shown.get("top"))
    d.line(top, d.point((0.0, b * 1.2)))
    d.line(corner, foot, shown.get("foot"))
    d.line(foot, d.point((a + 0.25 * max(a, b), 0.0)))
    d.line(foot, top, shown.get("length"))
    d.angle(corner, foot, top, right=True)
    return d


def cone_tank(sizes: Sequence[float], shown: Shown) -> Drawing:
    """A conical tank point down, the water at depth d and its surface's radius."""
    big, h, depth = sizes
    surface = big * depth / h
    d = Drawing("tank")
    apex, rim, water = d.point((0.0, 0.0)), d.point((0.0, h)), d.point((0.0, depth))
    d.arc(rim, big, big * ELLIPSE)
    d.arc(water, surface, surface * ELLIPSE)
    d.line(apex, d.point((-big, h)))
    d.line(apex, d.point((big, h)))
    d.line(apex, water, shown.get("depth"), dashed=True)
    d.line(water, rim, dashed=True)
    d.line(rim, d.point((big, h)), shown.get("radius"), dashed=True)
    d.line(water, d.point((surface, depth)), shown.get("surface"))
    if "height" in shown:
        side = big * (1 + _BESIDE)
        _dimension(d, (side, 0.0), (side, h), shown["height"])
    return d


def cylinder_tank(sizes: Sequence[float], shown: Shown) -> Drawing:
    big, h, depth = sizes
    d = cylinder_drawing(
        big, h, height=shown.get("height"), radius=shown.get("radius"), shape="tank"
    )
    d.arc(d.point((0.0, depth)), big, big * ELLIPSE)
    if "depth" in shown:
        side = -big * (1 + _BESIDE)
        _dimension(d, (side, 0.0), (side, depth), shown["depth"])
    return d


def cylinder_in_cone(sizes: Sequence[float], shown: Shown) -> Drawing:
    big, tall, r = sizes
    h = tall * (1 - r / big)
    d = Drawing("cylinder_in_cone")
    centre, apex = d.point((0.0, 0.0), dot=True), d.point((0.0, tall))
    round_base(d, centre, big)
    d.line(d.point((-big, 0.0)), apex)
    d.line(d.point((big, 0.0)), apex)
    d.line(centre, apex, dashed=True)
    round_base(d, centre, r)
    top = d.point((0.0, h))
    d.arc(top, r, r * ELLIPSE)
    d.line(d.point((-r, 0.0)), d.point((-r, h)))
    d.line(d.point((r, 0.0)), d.point((r, h)), shown.get("height"))
    d.line(top, d.point((r, h)), shown.get("radius"))
    d.line(centre, d.point((big, 0.0)), shown.get("outer_radius"), dashed=True, label_at=0.8)
    if "outer_height" in shown:
        side = big * (1 + _BESIDE)
        _dimension(d, (side, 0.0), (side, tall), shown["outer_height"])
    return d


def cylinder_in_sphere(sizes: Sequence[float], shown: Shown) -> Drawing:
    big, r = sizes
    k = math.sqrt(big * big - r * r)
    d = Drawing("cylinder_in_sphere")
    centre = d.point((0.0, 0.0), dot=True)
    d.arc(centre, big)
    low, high = d.point((0.0, -k)), d.point((0.0, k))
    round_base(d, low, r)
    d.arc(high, r, r * ELLIPSE)
    d.line(d.point((-r, -k)), d.point((-r, k)))
    rim = d.point((r, k))
    d.line(d.point((r, -k)), rim, shown.get("height"))
    d.line(high, rim, shown.get("radius"))
    # The sphere's radius to the cylinder's rim, as the textbook draws it.
    d.line(centre, rim, shown.get("outer_radius"), dashed=True)
    return d


DRAWERS: dict[str, Callable[[Sequence[float], Shown], Drawing]] = {
    "window": window,
    "rectangle": rectangle,
    "square": square,
    "circle": circle,
    "cylinder": cylinder,
    "cone": cone,
    "sphere": sphere,
    "frustum": frustum,
    "box": box,
    "sheet": sheet,
    "ladder": ladder,
    "tank:cone": cone_tank,
    "tank:cylinder": cylinder_tank,
    "inscribed:cone": cylinder_in_cone,
    "inscribed:sphere": cylinder_in_sphere,
}


def _extent(drawing: Drawing) -> tuple[float, float, float, float]:
    xs = [p.x for p in drawing.points] + [
        drawing.at(arc.center)[0] + s * arc.rx for arc in drawing.arcs for s in (-1, 1)
    ]
    ys = [p.y for p in drawing.points] + [
        drawing.at(arc.center)[1] + s * arc.ry for arc in drawing.arcs for s in (-1, 1)
    ]
    return min(xs), max(xs), min(ys), max(ys)


def beside(drawings: list[Drawing], shape: str) -> Drawing:
    """Several shapes in one figure, left to right on one baseline, each to its own scale
    (the parts of "a square and a circle" are drawn apart, never in proportion)."""
    if len(drawings) == 1:
        drawings[0].shape = shape
        return drawings[0]
    spans = [_extent(drawing) for drawing in drawings]
    height = max(top - low for _, _, low, top in spans)
    merged = Drawing(shape)
    x = 0.0
    for drawing, (left, right, low, top) in zip(drawings, spans, strict=True):
        # Each shape to the figure's height: one drawn small beside a large one is unreadable.
        grow = height / max(top - low, 1e-9) if not _labelled_to_scale(drawing) else 1.0
        rename = {}
        for point in drawing.points:
            rename[point.name] = merged.point(
                ((point.x - left) * grow + x, (point.y - low) * grow),
                point.name if not point.name.startswith("_") else "",
                show=point.show,
                dot=point.dot,
            )
        for seg in drawing.segments:
            merged.line(
                rename[seg.a],
                rename[seg.b],
                seg.label,
                dashed=seg.dashed,
                ticks=seg.ticks,
                arrows=seg.arrows,
                label_at=seg.label_at,
            )
        for arc in drawing.arcs:
            merged.arc(
                rename[arc.center],
                arc.rx * grow,
                arc.ry * grow,
                start=arc.start,
                end=arc.end,
                dashed=arc.dashed,
            )
        for mark in drawing.angles:
            merged.angle(
                rename[mark.at], rename[mark.a], rename[mark.b], mark.label, right=mark.right
            )
        merged.faces += [[rename[name] for name in face] for face in drawing.faces]
        x += (right - left) * grow + 0.35 * height
    return merged


def _labelled_to_scale(drawing: Drawing) -> bool:
    """A shape carrying a stated value keeps its own scale, so the value stays true."""
    return any(seg.label and seg.label[0].isdigit() for seg in drawing.segments)

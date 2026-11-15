"""A checked scene in space, drawn as the phone's flat ```geometry ``figure``.

Seen from ``view.clearest_view``: axes with their arrowheads and letters, each point the
question places with its name, a guided point's box from the origin with its coordinates
on the axes, a box's hidden edges dashed and each stated size on an edge in sight, a
sphere's outline and its equator (back half dashed), arrows, segments, faces and angle
marks.
"""

from __future__ import annotations

import math

from app.modules.math.drawing.arrows import arrowhead, axis
from app.modules.math.drawing.scene import BOX_FACES, ORIGIN, Box, Scene
from app.modules.math.drawing.view import NAME_AT, View, axis_ends, clearest_view, floats, span
from app.modules.math.figure.drawing import Drawing, number_text
from app.modules.math.figure.solids import ELLIPSE
from app.modules.math.schemas.figure import FigureSpec

_ARROW = 0.04
# An axis runs past the farthest point by this share, and at least this share of the
# scene's reach; it starts a little behind the origin.
_AXES = ("x", "y", "z")
_MINUS = "\u2212"


def _axes(drawing: Drawing, scene: Scene, view: View, size: float) -> None:
    taken = set(scene.points)
    for name, (start, end) in zip(_AXES, axis_ends(scene), strict=True):
        # Dashed: the phone's thinner, muted stroke, so arrows and segments stand off them.
        axis(drawing, view(start), view(end), name if name not in taken else "", size, dashed=True)


def _coordinate(value: float) -> str:
    return number_text(value).replace("-", _MINUS)


def _guides(drawing: Drawing, scene: Scene, view: View, names: dict[str, str]) -> None:
    """A guided point's box from the origin, its edges dashed and its feet on the axes marked
    with the point's own coordinates; with several guided points, each one's drop to the
    xy-plane only (three boxes crowd out the points they locate)."""
    used = {point.name for point in drawing.points}
    for guided in scene.guides:
        x, y, z = floats(scene.points[guided])
        if len(scene.guides) > 1:
            if z:
                drawing.line(names[guided], drawing.point(view((x, y, 0.0)), dot=True), dashed=True)
            continue
        corners = {
            "x": (x, 0.0, 0.0), "y": (0.0, y, 0.0), "z": (0.0, 0.0, z),
            "xy": (x, y, 0.0), "xz": (x, 0.0, z), "yz": (0.0, y, z),
        }  # fmt: skip
        at: dict[str, str] = {"": names[ORIGIN], "xyz": names[guided]}
        for key, xyz in corners.items():
            tick = _coordinate(xyz["xyz".index(key)]) if len(key) == 1 and any(xyz) else ""
            name = tick if tick and tick not in used and len(tick) <= 8 else ""
            used.add(name)
            at[key] = drawing.point(view(xyz), name, show=bool(name), dot=bool(name))
        for low, high in _GUIDE_EDGES:
            if drawing.at(at[low]) != drawing.at(at[high]):
                drawing.line(at[low], at[high], dashed=True)


# A guided point's box: its edges off the axes, by the corners they join.
_GUIDE_EDGES = (
    ("x", "xy"), ("y", "xy"), ("x", "xz"), ("z", "xz"), ("y", "yz"), ("z", "yz"),
    ("xy", "xyz"), ("xz", "xyz"), ("yz", "xyz"),
)  # fmt: skip


# A box's edges along x, y and z, by its corners (``scene._CORNERS``): a stated size is
# labelled on one of its four edges the reader sees, the lowest (an upright one, the
# rightmost).
_PARALLEL = (
    ((0, 1), (3, 2), (4, 5), (7, 6)),
    ((1, 2), (0, 3), (5, 6), (4, 7)),
    ((0, 4), (1, 5), (2, 6), (3, 7)),
)


def _seen(box: Box, scene: Scene, view: View) -> list[bool]:
    """Which of the box's faces the reader sees."""
    corners = [floats(scene.points[name]) for name in box.corners]
    middle = [sum(c[k] for c in corners) / 8 for k in range(3)]
    seen = []
    for face in BOX_FACES:
        centre = [sum(corners[i][k] for i in face) / 4 for k in range(3)]
        outward = [centre[k] - middle[k] for k in range(3)]
        seen.append(sum(o * t for o, t in zip(outward, view.toward, strict=True)) > 1e-9)
    return seen


def _hidden(scene: Scene, view: View, a: str, b: str) -> bool:
    """A line between two corners of a box that lies across no face the reader sees: through
    the box, or across a face behind it, it is dashed like a hidden edge."""
    for box in scene.boxes:
        if a in box.corners and b in box.corners:
            i, j = box.corners.index(a), box.corners.index(b)
            faces = zip(BOX_FACES, _seen(box, scene, view), strict=True)
            return not any(visible and i in face and j in face for face, visible in faces)
    return False


def _boxes(drawing: Drawing, scene: Scene, view: View, names: dict[str, str]) -> None:
    for box in scene.boxes:
        corners = [floats(scene.points[name]) for name in box.corners]
        seen = _seen(box, scene, view)
        edges: dict[tuple[int, int], bool] = {}
        for face, visible in zip(BOX_FACES, seen, strict=True):
            for i, a in enumerate(face):
                b = face[(i + 1) % 4]
                key = (min(a, b), max(a, b))
                edges[key] = edges.get(key, False) or visible
        labels: dict[tuple[int, int], str] = {}
        for along, parallel in enumerate(_PARALLEL):
            label = box.labels.get(parallel[0])
            in_sight = [edge for edge in parallel if edges[(min(edge), max(edge))]]
            if label is None or not in_sight:
                continue
            flat = {edge: [view(corners[i]) for i in edge] for edge in in_sight}
            if along == 2:
                edge = max(in_sight, key=lambda e: flat[e][0][0])
            else:
                edge = min(in_sight, key=lambda e: flat[e][0][1] + flat[e][1][1])
            labels[(min(edge), max(edge))] = label
        for (a, b), visible in edges.items():
            drawing.line(
                names[box.corners[a]], names[box.corners[b]], labels.get((a, b)), dashed=not visible
            )
        for a, b in box.diagonals:
            hidden = _hidden(scene, view, box.corners[a], box.corners[b])
            drawing.line(names[box.corners[a]], names[box.corners[b]], dashed=hidden)
        drawing.faces += [
            [names[box.corners[i]] for i in face]
            for face, v in zip(BOX_FACES, seen, strict=True)
            if v
        ]


def _spheres(drawing: Drawing, scene: Scene, names: dict[str, str]) -> None:
    for sphere in scene.spheres:
        r = math.sqrt(float(sphere.radius_squared))
        centre = names[sphere.centre]
        drawing.arc(centre, r)
        drawing.arc(centre, r, r * ELLIPSE, start=180, end=360)
        drawing.arc(centre, r, r * ELLIPSE, start=0, end=180, dashed=True)
        cx, cy = drawing.at(centre)
        drawing.line(centre, drawing.point((cx + r, cy)), sphere.label)


def _drawn(drawing: Drawing, a: str, b: str) -> bool:
    return drawing.side_of(a, b) is not None


def draw_scene(scene: Scene) -> FigureSpec | None:
    view = clearest_view(scene)
    if view is None:
        return None
    drawing = Drawing("space")
    size = _ARROW * span(scene, view)
    names: dict[str, str] = {}
    for name, xyz in scene.points.items():
        shown = name in scene.shown or (name == ORIGIN and scene.axes)
        names[name] = drawing.point(view(floats(xyz)), name, show=shown, dot=name in scene.dots)
    if scene.axes:
        _axes(drawing, scene, view, size)
    _guides(drawing, scene, view, names)
    _boxes(drawing, scene, view, names)
    _spheres(drawing, scene, names)
    for start, tip, label in scene.arrows:
        # The arrow's name beside its head.
        drawing.line(names[start], names[tip], label, label_at=NAME_AT)
        arrowhead(drawing, drawing.at(names[start]), drawing.at(names[tip]), size, names[tip])
    for a, b, label in scene.segments:
        drawn = drawing.side_of(names[a], names[b])
        if drawn is None:
            drawing.line(names[a], names[b], label, dashed=_hidden(scene, view, a, b))
        elif label:
            drawn.label = label
    for face in scene.faces:
        corners = [names[name] for name in face]
        for i, corner in enumerate(corners):
            if not _drawn(drawing, corner, corners[(i + 1) % len(corners)]):
                drawing.line(corner, corners[(i + 1) % len(corners)])
        drawing.faces.append(corners)
    for at, a, b, label, right in scene.angles:
        drawing.angle(names[at], names[a], names[b], label, right=right)
    return drawing.spec()

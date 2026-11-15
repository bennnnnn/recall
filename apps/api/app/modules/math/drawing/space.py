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
from app.modules.math.drawing.scene import ORIGIN, Box, Scene
from app.modules.math.drawing.view import NAME_AT, axis_ends, clearest_view, floats, span
from app.modules.math.figure.drawing import Drawing, number_text
from app.modules.math.figure.projection import BOX_FACES, View, draw_faces, faces_seen
from app.modules.math.figure.solids import round_base
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


def _seen(box: Box, scene: Scene, view: View) -> list[bool]:
    """Which of the box's faces the reader sees."""
    return faces_seen([floats(scene.points[name]) for name in box.corners], BOX_FACES, view)


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
        own = [names[name] for name in box.corners]
        draw_faces(drawing, own, corners, BOX_FACES, box.labels, view)
        for a, b in box.diagonals:
            hidden = _hidden(scene, view, box.corners[a], box.corners[b])
            drawing.line(own[a], own[b], dashed=hidden)


def _spheres(drawing: Drawing, scene: Scene, names: dict[str, str]) -> None:
    for sphere in scene.spheres:
        r = math.sqrt(float(sphere.radius_squared))
        centre = names[sphere.centre]
        drawing.arc(centre, r)
        round_base(drawing, centre, r)
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

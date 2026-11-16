"""How a solid in three dimensions is drawn flat: one projection for every figure.

A solid is seen in true (orthographic) projection with z up, from as far above as a circle
lying flat is drawn an ellipse 0.3 as tall as it is wide (``ELLIPSE``: the round solids'
ellipses), turned about z. The textbook's view has the x-axis coming toward the reader, down
and to the left, and y going across to the right. A polyhedron's edges are dashed where no
face that meets them faces the reader, and a stated size sits on an edge in sight: the one
it names when that is in sight, else the lowest in sight of the edges parallel to it and as
long (an upright one, the rightmost). The figure read's boxes, prisms and pyramids, a word
problem's box and a scene in space (``math.drawing``) are all drawn this one way.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from app.modules.math.figure.drawing import Drawing, Point

Point3 = tuple[float, float, float]

# A circle seen from the solids' height: its ellipse's height against its width.
ELLIPSE = 0.3
ELEVATION = math.asin(ELLIPSE)
# The textbook's turn about z: the x-axis toward the reader, down and to the left.
TEXTBOOK_AZIMUTH = 30.0
# A box's corners by which of its sizes each is at, (x, y, z) each 0 or 1: the bottom four
# from the origin round, then the top four above them; and its faces by those corners.
BOX_CORNERS = (
    (0, 0, 0),
    (1, 0, 0),
    (1, 1, 0),
    (0, 1, 0),
    (0, 0, 1),
    (1, 0, 1),
    (1, 1, 1),
    (0, 1, 1),
)
BOX_FACES = ([0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [3, 2, 6, 7], [0, 3, 7, 4], [1, 2, 6, 5])
# A box's top face, and its edge at the corner farthest from the reader.
BOX_TOP = 1
BOX_BACK_EDGE = (0, 4)
_TOLERANCE = 1e-9


class View:
    """Orthographic projection seen from ``azimuth`` degrees round from the x-axis, from
    ``elevation`` above (the solids' own height by default)."""

    def __init__(self, azimuth: float = TEXTBOOK_AZIMUTH, elevation: float = ELEVATION) -> None:
        turn = math.radians(azimuth)
        self._sin, self._cos = math.sin(turn), math.cos(turn)
        self._up, self._flat = math.sin(elevation), math.cos(elevation)
        # Toward the reader.
        self.toward = (self._flat * self._cos, self._flat * self._sin, self._up)

    def __call__(self, xyz: Iterable[float]) -> Point:
        x, y, z = xyz
        across = -x * self._sin + y * self._cos
        up = -(x * self._cos + y * self._sin) * self._up + z * self._flat
        return (across, up)


TEXTBOOK = View()


def box_corners(size: Sequence[float]) -> list[Point3]:
    """A box's corners at the origin, ``size`` its extent along x, y and z."""
    return [(size[0] * i, size[1] * j, size[2] * k) for i, j, k in BOX_CORNERS]


def _middle(points: Sequence[Point3]) -> list[float]:
    return [sum(p[k] for p in points) / len(points) for k in range(3)]


def faces_seen(vertices: Sequence[Point3], faces: Sequence[list[int]], view: View) -> list[bool]:
    """Which faces of a convex solid the reader sees: those whose outward side looks back."""
    middle = _middle(vertices)
    seen = []
    for face in faces:
        a, b, c = (vertices[i] for i in face[:3])
        u = [b[k] - a[k] for k in range(3)]
        v = [c[k] - a[k] for k in range(3)]
        normal = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        centre = _middle([vertices[i] for i in face])
        if sum(n * (c_ - m) for n, c_, m in zip(normal, centre, middle, strict=True)) < 0:
            normal = [-n for n in normal]
        seen.append(sum(n * t for n, t in zip(normal, view.toward, strict=True)) > _TOLERANCE)
    return seen


def _edges(faces: Sequence[list[int]], seen: Sequence[bool]) -> dict[tuple[int, int], bool]:
    """Each edge, and whether a face the reader sees meets it."""
    edges: dict[tuple[int, int], bool] = {}
    for face, visible in zip(faces, seen, strict=True):
        for i, a in enumerate(face):
            b = face[(i + 1) % len(face)]
            key = (min(a, b), max(a, b))
            edges[key] = edges.get(key, False) or visible
    return edges


def _way(vertices: Sequence[Point3], edge: tuple[int, int]) -> Point3:
    a, b = vertices[edge[0]], vertices[edge[1]]
    return (b[0] - a[0], b[1] - a[1], b[2] - a[2])


def _parallel(u: Point3, v: Point3) -> bool:
    return all(abs(x - y) <= 1e-9 * max(1.0, abs(x)) for x, y in zip(u, v, strict=True)) or all(
        abs(x + y) <= 1e-9 * max(1.0, abs(x)) for x, y in zip(u, v, strict=True)
    )


def _label_edges(
    vertices: Sequence[Point3],
    edges: dict[tuple[int, int], bool],
    labels: dict[tuple[int, int], str],
    view: View,
) -> dict[tuple[int, int], str]:
    """Each label on an edge in sight: its own, else the lowest of the edges in sight parallel
    to it and as long (an upright one, the rightmost); its own when none is in sight."""
    placed: dict[tuple[int, int], str] = {}
    for edge, label in labels.items():
        own = (min(edge), max(edge))
        way = _way(vertices, own)
        twins = [e for e, seen in edges.items() if seen and _parallel(_way(vertices, e), way)]
        if edges.get(own) or not twins:
            placed[own] = label
            continue
        flat = {e: [view(vertices[i]) for i in e] for e in twins}
        upright = abs(view(way)[0]) < 1e-9 * max(1.0, abs(view(way)[1]))
        if upright:
            best = max(twins, key=lambda e: flat[e][0][0])
        else:
            best = min(twins, key=lambda e: flat[e][0][1] + flat[e][1][1])
        placed[best] = label
    return placed


def draw_faces(
    drawing: Drawing,
    names: Sequence[str],
    vertices: Sequence[Point3],
    faces: Sequence[list[int]],
    labels: dict[tuple[int, int], str],
    view: View,
) -> dict[tuple[int, int], bool]:
    """A convex solid's edges on ``drawing`` between its corners' ``names``, hidden ones
    dashed, each label on an edge in sight, and the faces the reader sees lightly filled.
    Returns each edge and whether it is in sight."""
    seen = faces_seen(vertices, faces, view)
    edges = _edges(faces, seen)
    placed = _label_edges(vertices, edges, labels, view)
    for (a, b), visible in edges.items():
        drawing.line(names[a], names[b], placed.get((a, b)), dashed=not visible)
    drawing.faces += [
        [names[i] for i in face] for face, visible in zip(faces, seen, strict=True) if visible
    ]
    return edges


def draw_polyhedron(
    shape: str,
    vertices: Sequence[Point3],
    faces: Sequence[list[int]],
    labels: dict[tuple[int, int], str],
    view: View = TEXTBOOK,
) -> Drawing:
    drawing = Drawing(shape)
    names = [drawing.point(view(vertex)) for vertex in vertices]
    draw_faces(drawing, names, vertices, faces, labels, view)
    return drawing


def box_drawing(
    shape: str,
    size: Sequence[float],
    labels: dict[int, str],
    *,
    lid: bool = True,
    view: View = TEXTBOOK,
) -> Drawing:
    """A box ``size`` along x, y and z, each size's label (by its axis, 0 to 2) on an edge in
    sight. With no lid its rim is all in sight, and so is its back edge inside it, down from
    the rim; no face covers the opening."""
    vertices = box_corners(size)
    along = {0: (0, 1), 1: (0, 3), 2: (0, 4)}
    edges = {along[axis]: label for axis, label in labels.items()}
    drawing = draw_polyhedron(shape, vertices, BOX_FACES, edges, view)
    if not lid:
        rim = [drawing.points[i].name for i in BOX_FACES[BOX_TOP]]
        for i, name in enumerate(rim):
            edge = drawing.side_of(name, rim[(i + 1) % 4])
            if edge is not None:
                edge.dashed = False
        back = drawing.side_of(*(drawing.points[i].name for i in BOX_BACK_EDGE))
        if back is not None:
            back.dashed = False
        drawing.faces = [face for face in drawing.faces if set(face) != set(rim)]
    return drawing

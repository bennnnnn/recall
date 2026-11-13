"""A polygon's letters where the question's named values put them.

A builder draws a shape in its own order (a kite's short sides on top, a parallelogram's
given angle bottom left) and letters the corners in the question's order. "Kite ABCD with
AB = AD = 5 cm and CB = CD = 8 cm" puts A where the two short sides meet, which that
order need not. So the letters go round the corners once more, every way they can (each
starting corner, either direction), and the first way that makes every named side and
angle true is kept. No way does: the picture would show values that are not the
question's, and nothing is drawn.
"""

from __future__ import annotations

from app.modules.math.figure.drawing import angle_at, distance
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec

_LENGTH_TOLERANCE = 1e-3
_ANGLE_TOLERANCE = 0.05
_ANGLES = frozenset({"angle", "apex_angle", "base_angle"})


def _orders(letters: list[str]) -> list[list[str]]:
    """Every lettering that keeps the letters going round in order."""
    rounds = [letters[k:] + letters[:k] for k in range(len(letters))]
    return rounds + [list(reversed(order)) for order in rounds]


def _vertex(name: str) -> str:
    return name[1] if len(name) == 3 else name


def _holds(
    order: list[str],
    corners: dict[str, tuple[float, float]],
    request: FigureRequest,
    drawn: list[str],
) -> bool:
    """Every named value is true with ``order``'s letter at each drawn corner."""
    at = {letter: corners[drawn[i]] for i, letter in enumerate(order)}
    count = len(order)
    for measure in request.measures:
        name = measure.name.strip()
        if measure.what in _ANGLES and _vertex(name) in at:
            index = order.index(_vertex(name))
            before, after = at[order[index - 1]], at[order[(index + 1) % count]]
            if len(name) == 3 and set(name) <= set(at):
                # "ACB" is the angle at C between CA and CB, which may be a diagonal.
                before, after = at[name[0]], at[name[2]]
            if abs(angle_at(at[order[index]], before, after) - measure.value) > _ANGLE_TOLERANCE:
                return False
        elif len(name) == 2 and set(name) <= set(at) and measure.what not in _ANGLES:
            length = distance(at[name[0]], at[name[1]])
            if abs(length - measure.value) > _LENGTH_TOLERANCE * max(1.0, measure.value):
                return False
    return True


def lettered(spec: FigureSpec, request: FigureRequest) -> FigureSpec | None:
    """``spec`` with its corners lettered so the named values hold, or None when no
    lettering makes them hold."""
    # The polygon's own corners, in order round its outline (not a centre it letters).
    shown = {point.name for point in spec.points if point.show}
    drawn = [name for name in (spec.faces[0] if spec.faces else []) if name in shown]
    if len(drawn) < 3 or not any(len(m.name.strip()) in {1, 2, 3} for m in request.measures):
        return spec
    corners = {point.name: (point.x, point.y) for point in spec.points}
    for order in _orders(drawn):
        if not _holds(order, corners, request, drawn):
            continue
        if order == drawn:
            return spec
        rename = dict(zip(drawn, order, strict=True))
        return _renamed(spec, rename)
    return None


def _renamed(spec: FigureSpec, rename: dict[str, str]) -> FigureSpec:
    def name(old: str) -> str:
        return rename.get(old, old)

    data = spec.model_dump()
    for point in data["points"]:
        point["name"] = name(point["name"])
    for segment in data["segments"]:
        segment["a"], segment["b"] = name(segment["a"]), name(segment["b"])
    for arc in data["arcs"]:
        arc["center"] = name(arc["center"])
    for angle in data["angles"]:
        angle["at"], angle["a"], angle["b"] = name(angle["at"]), name(angle["a"]), name(angle["b"])
    data["faces"] = [[name(n) for n in face] for face in data["faces"]]
    return FigureSpec.model_validate(data)

"""A general quadrilateral ABCD drawn with the angles a question gives it, true to size.

Three angles decide the fourth (the four make 360°), and four must make 360°; written with a
letter ("x, 2x, 3x and 4x") they are solved where the sum decides them (``angle_terms``).
Each angle must be under 180° (the shape is drawn convex). With its angles fixed, walking
round the outline turns by 180° less each one, so the sides' directions are known and
only their lengths are open: two of them close the outline once the others are chosen.
The sides the question states are kept, the rest chosen so the shape is not thin, and the
two that close it must come out longer than nothing; otherwise nothing is drawn. A stated
angle is labelled at its corner; the one the question asks for is marked, unlabelled.
"""

from __future__ import annotations

import itertools
import math

from app.modules.math.figure.angle_terms import sized_angles
from app.modules.math.figure.drawing import Drawing, angle_label, length_label
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec

SHAPES = frozenset({"quadrilateral", "irregular_quadrilateral", "general_quadrilateral"})
_TOLERANCE = 1e-6
# Lengths tried for the sides the question leaves open, and how thin a shape may be.
_TRIES = (6.0, 5.0, 4.0, 7.0, 3.0, 8.0, 2.5)
_MAX_RATIO = 4.0


def _letters(request: FigureRequest) -> tuple[list[str], bool]:
    letters = request.vertices.strip()
    if len(letters) == 4 and len(set(letters)) == 4 and letters.isalpha():
        return list(letters), True
    return list("ABCD"), False


def _angles(request: FigureRequest, names: list[str]) -> tuple[list[float], dict[int, str]] | None:
    """The four angles in order round ABCD, and the labels of those stated."""
    sized = (
        sized_angles(request.model_copy(update={"measures": request.given("angle")}), 360.0)
        if request.angle_terms
        else None
    )
    if request.angle_terms and sized is None:
        return None
    entries = (
        [(a.name, a.size, a.label or angle_label(a.size)) for a in sized]
        if sized is not None
        else [(m.name.strip(), m.value, angle_label(m.value)) for m in request.given("angle")]
    )
    found: dict[int, float] = {}
    labels: dict[int, str] = {}
    unnamed: list[tuple[float, str]] = []
    for name, value, label in entries:
        vertex = name[1] if len(name) == 3 else name[:1]
        if vertex in names and names.index(vertex) not in found:
            found[names.index(vertex)] = value
            labels[names.index(vertex)] = label
        elif vertex:
            return None
        else:
            unnamed.append((value, label))
    for value, label in unnamed:
        free = next((i for i in range(4) if i not in found), None)
        if free is None:
            return None
        found[free], labels[free] = value, label
    if len(found) == 3:
        missing = next(i for i in range(4) if i not in found)
        found[missing] = 360.0 - sum(found.values())
    if len(found) != 4 or abs(sum(found.values()) - 360) > 1e-6:
        return None
    angles = [found[i] for i in range(4)]
    return (angles, labels) if all(0 < a < 180 for a in angles) else None


def _sides(request: FigureRequest, names: list[str]) -> dict[int, float] | None:
    """Side i joins corner i to corner i + 1: "BC" is side 1."""
    found: dict[int, float] = {}
    for m in request.measures:
        if m.what in {"angle", "perimeter"}:
            continue
        pair = m.name.strip()
        if m.what not in {"side", "length"} or len(pair) != 2 or not set(pair) <= set(names):
            return None
        i, j = names.index(pair[0]), names.index(pair[1])
        index = i if (i + 1) % 4 == j else j if (j + 1) % 4 == i else None
        if index is None or index in found:
            return None
        found[index] = m.value
    return found


def _close(directions: list[tuple[float, float]], lengths: dict[int, float]) -> list[float] | None:
    """The two open sides' lengths that close the outline, given the others."""
    open_sides = [i for i in range(4) if i not in lengths]
    if len(open_sides) != 2:
        return None
    rest_x = -sum(lengths[i] * directions[i][0] for i in lengths)
    rest_y = -sum(lengths[i] * directions[i][1] for i in lengths)
    (ax, ay), (bx, by) = directions[open_sides[0]], directions[open_sides[1]]
    det = ax * by - ay * bx
    if abs(det) < 1e-9:
        return None
    first = (rest_x * by - rest_y * bx) / det
    second = (ax * rest_y - ay * rest_x) / det
    if first <= _TOLERANCE or second <= _TOLERANCE:
        return None
    full = dict(lengths) | {open_sides[0]: first, open_sides[1]: second}
    return [full[i] for i in range(4)]


def build_quadrilateral(request: FigureRequest) -> FigureSpec | None:
    names, lettered = _letters(request)
    read = _angles(request, names)
    stated = _sides(request, names)
    if read is None or stated is None:
        return None
    angles, labels = read
    # Walking A to B to C to D, each turn is 180° less the corner's angle.
    headings = [0.0, 180 - angles[1], 360 - angles[1] - angles[2], 180 + angles[0]]
    directions = [(math.cos(math.radians(h)), math.sin(math.radians(h))) for h in headings]
    free = [i for i in range(4) if i not in stated]
    best: list[float] | None = None
    for chosen in itertools.product(_TRIES, repeat=max(0, len(free) - 2)):
        for pair in itertools.combinations(free, 2):
            fixed = [i for i in free if i not in pair]
            lengths = stated | dict(zip(fixed, chosen, strict=True))
            sides = _close(directions, lengths)
            if sides is not None and max(sides) / min(sides) <= _MAX_RATIO:
                best = sides
                break
        if best is not None:
            break
    if best is None:
        return None
    return _draw(request, names, lettered, best, directions, labels, stated)


def _draw(
    request: FigureRequest,
    names: list[str],
    lettered: bool,
    sides: list[float],
    directions: list[tuple[float, float]],
    labels: dict[int, str],
    stated: dict[int, float],
) -> FigureSpec:
    drawing = Drawing("quadrilateral")
    x, y = 0.0, 0.0
    for index, name in enumerate(names):
        drawing.point((x, y), name, show=lettered)
        x += sides[index] * directions[index][0]
        y += sides[index] * directions[index][1]
    drawing.outline(names)
    for index, value in stated.items():
        drawing.label_side(names[index], names[(index + 1) % 4], length_label(value, request.unit))
    for index in range(4):
        before, after = names[index - 1], names[(index + 1) % 4]
        drawing.angle(names[index], after, before, labels.get(index))
    return drawing.spec()

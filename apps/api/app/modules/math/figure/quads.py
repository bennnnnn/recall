"""Four-sided shapes and regular polygons from the values a question states.

Each shape keeps its properties whatever is left open (a parallelogram's opposite sides
parallel, a rhombus's equal sides, a kite's two pairs), takes the question's lengths and
angles where it names them, and labels only those: a length the question asks for is drawn
to its size, unlabelled. Vertices run counterclockwise from the bottom left, so ABCD has AB
along the bottom.
"""

from __future__ import annotations

import math

from app.modules.math.figure.drawing import Drawing, Point, angle_label, length_label, polar
from app.modules.math.figure.request import FigureRequest
from app.modules.math.schemas.figure import FigureSpec

# Proportions for what a question leaves open: a 6 by 4 shape leaning 65°, a trapezium's
# height and top against its base, where a kite's diagonals cross.
_BASE, _SIDE, _LEAN = 6.0, 4.0, 65.0
_TRAPEZIUM_HEIGHT = 0.55
_TRAPEZIUM_TOP = 0.6
_TRAPEZIUM_LEFT = 1 / 3
_KITE_SPLIT = 0.35
_KITE_WIDTH = 0.7
_REGULAR_SIDE = 3.0
# Two diagonals cross at their middles: each label sits three quarters along its own.
_DIAGONAL_LABEL_AT = 0.75
_ROLE_LENGTHS = frozenset({"side", "length", "base", "width", "edge", "equal_side"})
# Sides a polygon's name gives it ("hexagon"), for a regular polygon read by name.
POLYGON_SIDES = {
    "triangle": 3,
    "square": 4,
    "pentagon": 5,
    "hexagon": 6,
    "heptagon": 7,
    "octagon": 8,
    "nonagon": 9,
    "decagon": 10,
    "dodecagon": 12,
}


def _letters(request: FigureRequest, count: int) -> tuple[list[str], bool]:
    letters = request.vertices.strip()
    if len(letters) == count and len(set(letters)) == count and letters.isalpha():
        return list(letters), True
    return [chr(ord("A") + i) for i in range(count)], False


def _side_index(name: str, names: list[str]) -> int | None:
    """Side i joins vertex i and i + 1; "BC" is side 1 of ABCD."""
    letters = name.strip()
    if len(letters) != 2 or not set(letters) <= set(names):
        return None
    i, j = names.index(letters[0]), names.index(letters[1])
    if (i + 1) % len(names) == j:
        return i
    if (j + 1) % len(names) == i:
        return j
    return None


def _vertex(name: str) -> str:
    letters = name.strip()
    return letters[1] if len(letters) == 3 else letters[:1]


class _Values:
    """A shape's stated values: named sides and angles placed, the rest by role."""

    def __init__(self, request: FigureRequest, names: list[str]) -> None:
        self.unit = request.unit
        self.sides: dict[int, float] = {}
        self.angles: dict[int, float] = {}
        self.unnamed: list[tuple[str, float]] = []
        self.unnamed_angles: list[float] = []
        # A trapezium's parallel sides and height, once its builder reads them.
        self.bottom, self.top = 0.0, 0.0
        self.height: float | None = None
        for measure in request.measures:
            if measure.what == "angle":
                vertex = _vertex(measure.name)
                if vertex and vertex in names:
                    self.angles[names.index(vertex)] = measure.value
                else:
                    self.unnamed_angles.append(measure.value)
                continue
            index = _side_index(measure.name, names) if measure.what in _ROLE_LENGTHS else None
            if index is not None:
                self.sides[index] = measure.value
            else:
                self.unnamed.append((measure.what, measure.value))

    def take(self, *whats: str) -> float | None:
        """The first unnamed value of one of these roles, used once."""
        for what in whats:
            for i, (role, value) in enumerate(self.unnamed):
                if role == what:
                    del self.unnamed[i]
                    return value
        return None

    def side(self, *indexes: int) -> float | None:
        for index in indexes:
            if index in self.sides:
                return self.sides[index]
        return None

    def label(self, value: float | None) -> str | None:
        return None if value is None else length_label(value, self.unit)


def _drawing(
    request: FigureRequest, corners: list[Point], names: list[str], lettered: bool
) -> Drawing:
    drawing = Drawing(request.shape)
    for name, corner in zip(names, corners, strict=True):
        drawing.point(corner, name, show=lettered)
    drawing.outline(names)
    return drawing


def _mark_angles(drawing: Drawing, names: list[str], angles: dict[int, float]) -> None:
    count = len(names)
    for index, value in sorted(angles.items()):
        before, after = names[(index - 1) % count], names[(index + 1) % count]
        if abs(value - 90) < 1e-6:
            drawing.angle(names[index], after, before, right=True)
        else:
            drawing.angle(names[index], after, before, angle_label(value))


def _diagonals(drawing: Drawing, request: FigureRequest, names: list[str], *, right: bool) -> None:
    a, b, c, d = names
    drawing.line(a, c, dashed=True)
    drawing.line(b, d, dashed=True)
    (ax, ay), (cx, cy) = drawing.at(a), drawing.at(c)
    letter = request.center.strip()[:1]
    name = letter if letter.isalpha() and letter not in names else ""
    middle = drawing.point(((ax + cx) / 2, (ay + cy) / 2), name, show=bool(name), dot=bool(name))
    if right:
        drawing.angle(middle, c, d, right=True)


def _diagonal_ends(request: FigureRequest, names: list[str]) -> tuple[str, str]:
    """The diagonal the question names ("BD"), or AC."""
    for measure in request.given("diagonal"):
        letters = measure.name.strip()
        if len(letters) == 2 and set(letters) <= set(names) and _side_index(letters, names) is None:
            return letters[0], letters[1]
    return names[0], names[2]


def _parallel_marks(drawing: Drawing, names: list[str], pairs: int) -> None:
    """Arrowheads on parallel sides: one on the first pair, two on the second."""
    a, b, c, d = names
    for side in ((a, b), (d, c)):
        segment = drawing.side_of(*side)
        if segment is not None:
            segment.arrows = 1
    if pairs == 2:
        for side in ((b, c), (a, d)):
            segment = drawing.side_of(*side)
            if segment is not None:
                segment.arrows = 2


def build_square(request: FigureRequest) -> FigureSpec | None:
    names, lettered = _letters(request, 4)
    values = _Values(request, names)
    side = values.side(0, 1, 2, 3) or values.take("side", "edge", "length", "base")
    diagonal = values.take("diagonal")
    perimeter = values.take("perimeter")
    if side is None and diagonal is not None:
        side_size = diagonal / math.sqrt(2)
    elif side is None and perimeter is not None:
        side_size = perimeter / 4
    else:
        side_size = side or _SIDE
    corners = [(0.0, 0.0), (side_size, 0.0), (side_size, side_size), (0.0, side_size)]
    drawing = _drawing(request, corners, names, lettered)
    for index in range(4):
        label = values.label(side) if index == 0 else None
        drawing.label_side(names[index], names[(index + 1) % 4], label, ticks=1)
    _mark_angles(drawing, names, dict.fromkeys(range(4), 90.0))
    if diagonal is not None:
        drawing.line(*_diagonal_ends(request, names), values.label(diagonal))
    elif request.has_part("diagonal"):
        _diagonals(drawing, request, names, right=True)
    return drawing.spec()


def build_rectangle(request: FigureRequest) -> FigureSpec | None:
    names, lettered = _letters(request, 4)
    values = _Values(request, names)
    length = values.side(0, 2) or values.take("length", "base", "side")
    width = values.side(1, 3) or values.take("width", "height", "side")
    diagonal = values.take("diagonal")
    perimeter = values.take("perimeter")
    stated_length, stated_width = length, width
    if perimeter is not None and (length is None) != (width is None):
        other = perimeter / 2 - float(length if length is not None else width or 0)
        if other <= 0:
            return None
        length, width = (length, other) if length is not None else (other, width)
    if diagonal is not None and (length is None) != (width is None):
        known = float(length if length is not None else width or 0)
        if diagonal <= known:
            return None
        other = math.sqrt(diagonal * diagonal - known * known)
        length, width = (known, other) if length is not None else (other, known)
    w, h = length or _BASE, width or _SIDE
    drawing = _drawing(request, [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)], names, lettered)
    drawing.label_side(names[0], names[1], values.label(stated_length))
    drawing.label_side(names[1], names[2], values.label(stated_width))
    _mark_angles(drawing, names, dict.fromkeys(range(4), 90.0))
    if diagonal is not None:
        drawing.line(*_diagonal_ends(request, names), values.label(diagonal))
    elif request.has_part("diagonal"):
        _diagonals(drawing, request, names, right=False)
    return drawing.spec()


def _lean(values: _Values) -> float | None:
    """The angle at the bottom left vertex, from the angle the question gives anywhere."""
    for index, value in values.angles.items():
        if not 0 < value < 180:
            return None
        return value if index % 2 == 0 else 180.0 - value
    if values.unnamed_angles:
        value = values.unnamed_angles[0]
        return value if 0 < value < 180 else None
    return None


def build_parallelogram(request: FigureRequest, *, rhombus: bool = False) -> FigureSpec | None:
    names, lettered = _letters(request, 4)
    values = _Values(request, names)
    base = values.side(0, 2) or values.take("base", "length", "side")
    stated_side = values.side(1, 3) or (None if rhombus else values.take("side", "width", "length"))
    side = stated_side or (base if rhombus else None)
    height = values.take("height")
    lean = _lean(values)
    if values.angles and lean is None:
        return None
    if height is not None:
        if lean is None and side is not None:
            if height > side:
                return None
            lean = math.degrees(math.asin(height / side))
        lean = lean or _LEAN
        if side is None:
            side = height / math.sin(math.radians(lean))
        elif abs(side * math.sin(math.radians(lean)) - height) > 1e-4 * max(1.0, height):
            return None
    b = base or side or _BASE
    s = side or (b if rhombus else _SIDE)
    turn = math.radians(lean or _LEAN)
    top = (s * math.cos(turn), s * math.sin(turn))
    corners = [(0.0, 0.0), (b, 0.0), (b + top[0], top[1]), top]
    drawing = _drawing(request, corners, names, lettered)
    drawing.shape = "rhombus" if rhombus else "parallelogram"
    # Each value on the side the question names, or the bottom and the left.
    along = (names[2], names[3]) if 2 in values.sides and 0 not in values.sides else names[:2]
    up = (names[1], names[2]) if 1 in values.sides and 3 not in values.sides else names[::3]
    drawing.label_side(along[0], along[1], values.label(base))
    drawing.label_side(up[0], up[1], values.label(stated_side))
    if rhombus:
        for index in range(4):
            drawing.label_side(names[index], names[(index + 1) % 4], None, ticks=1)
    _parallel_marks(drawing, names, 2)
    stated = dict(values.angles) or ({0: values.unnamed_angles[0]} if values.unnamed_angles else {})
    _mark_angles(drawing, names, stated)
    if height is not None:
        foot = drawing.point((top[0], 0.0))
        drawing.line(names[3], foot, values.label(height), dashed=True)
        drawing.angle(foot, names[1], names[3], right=True)
    return drawing.spec()


def build_rhombus(request: FigureRequest) -> FigureSpec | None:
    diagonals = [m.value for m in request.given("diagonal")]
    names, lettered = _letters(request, 4)
    side = request.first("side", "edge", "length")
    if len(diagonals) == 1 and side is not None and diagonals[0] < 2 * side:
        diagonals.append(2 * math.sqrt(side * side - (diagonals[0] / 2) ** 2))
    if len(diagonals) < 2:
        return build_parallelogram(request, rhombus=True)
    across, up = sorted(diagonals[:2], reverse=True)
    corners = [(-across / 2, 0.0), (0.0, -up / 2), (across / 2, 0.0), (0.0, up / 2)]
    drawing = _drawing(request, corners, names, lettered)
    for index in range(4):
        drawing.label_side(names[index], names[(index + 1) % 4], None, ticks=1)
    stated = {round(m.value, 9) for m in request.given("diagonal")}
    unit = request.unit
    across_label = length_label(across, unit) if round(across, 9) in stated else None
    up_label = length_label(up, unit) if round(up, 9) in stated else None
    drawing.line(names[0], names[2], across_label, label_at=_DIAGONAL_LABEL_AT)
    drawing.line(names[1], names[3], up_label, label_at=_DIAGONAL_LABEL_AT)
    letter = request.center.strip()[:1]
    name = letter if letter.isalpha() and letter not in names else ""
    middle = drawing.point((0.0, 0.0), name, show=bool(name), dot=bool(name))
    drawing.angle(middle, names[2], names[3], right=True)
    if side is not None:
        drawing.label_side(names[0], names[1], length_label(side, unit), ticks=1)
    return drawing.spec()


def _trapezium_frame(values: _Values, isosceles: bool) -> tuple[float, float] | None:
    """Where the top's left end stands over the bottom's: (its run along, its height), from
    what the question states: a height, a leg or two, a base angle. What it leaves open is
    chosen, never an equal pair of legs it did not state."""
    bottom, top = values.bottom, values.top
    gap = bottom - top
    a, b = values.angles.get(0), values.angles.get(1)
    a = a if a is not None else (180 - values.angles[3] if 3 in values.angles else None)
    b = b if b is not None else (180 - values.angles[2] if 2 in values.angles else None)
    left, right, height = values.side(3), values.side(1), values.height
    if isosceles:
        left = right = left or right
    if height is None and left is not None and a is not None:
        height = left * math.sin(math.radians(a))
    if height is None and right is not None and b is not None:
        height = right * math.sin(math.radians(b))
    if height is None and left is not None and right is not None and abs(gap) > 1e-9:
        run = (left * left - right * right + gap * gap) / (2 * gap)
        return (run, math.sqrt(left * left - run * run)) if left > abs(run) else None
    if height is None:
        lean = left or right
        height = lean * math.sin(math.radians(70)) if lean else bottom * _TRAPEZIUM_HEIGHT
    if a is not None:
        return height / math.tan(math.radians(a)), height
    if b is not None:
        return gap - height / math.tan(math.radians(b)), height
    if isosceles:
        return gap / 2, height
    if left is not None:
        return (math.sqrt(left * left - height * height), height) if left > height else None
    if right is not None:
        return (
            (gap - math.sqrt(right * right - height * height), height) if right > height else None
        )
    return gap * _TRAPEZIUM_LEFT, height


def build_trapezium(request: FigureRequest) -> FigureSpec | None:
    names, lettered = _letters(request, 4)
    values = _Values(request, names)
    parallel = sorted(
        (v for role, v in values.unnamed if role in {"parallel_side", "base"}), reverse=True
    )
    values.unnamed = [(r, v) for r, v in values.unnamed if r not in {"parallel_side", "base"}]
    bottom, top = values.side(0), values.side(2)
    if bottom is None and parallel:
        bottom = parallel.pop(0)
    if top is None and parallel:
        top = parallel.pop(0)
    if parallel or values.unnamed_angles[1:]:
        return None
    if values.unnamed_angles:
        values.angles.setdefault(0, values.unnamed_angles[0])
    if top is not None and bottom is not None and abs(top - bottom) < 1e-9:
        return None  # equal parallel sides make a parallelogram, not a trapezium
    isosceles = request.shape.startswith("isosceles")
    legs = [v for role, v in values.unnamed if role in {"leg", "side"}]
    if len(legs) > (1 if isosceles else 2) or (len(legs) == 2 and 1 in values.sides):
        return None
    for index, leg in zip((3, 1), legs, strict=False):
        values.sides.setdefault(index, leg)
    values.height = values.take("height")
    values.bottom = bottom or _BASE
    values.top = top or values.bottom * _TRAPEZIUM_TOP
    frame = _trapezium_frame(values, isosceles)
    if frame is None:
        return None
    run, height = frame
    b, t = values.bottom, values.top
    corners = [(0.0, 0.0), (b, 0.0), (run + t, height), (run, height)]
    drawing = _drawing(request, corners, names, lettered)
    drawing.label_side(names[0], names[1], values.label(bottom))
    drawing.label_side(names[3], names[2], values.label(top))
    ticks = 1 if isosceles else 0
    drawing.label_side(names[0], names[3], values.label(values.sides.get(3)), ticks=ticks)
    drawing.label_side(names[1], names[2], values.label(values.sides.get(1)), ticks=ticks)
    _parallel_marks(drawing, names, 1)
    _mark_angles(drawing, names, values.angles)
    if values.height is not None:
        foot = drawing.point((run, 0.0))
        drawing.line(names[3], foot, values.label(values.height), dashed=True)
        drawing.angle(foot, names[1], names[3], right=True)
    return drawing.spec()


def build_kite(request: FigureRequest) -> FigureSpec | None:
    """A kite's axis joins the corners where its two pairs of equal sides meet, which only
    named equal sides fix: a lettered kite without them, or with its diagonals named ("AC =
    10, BD = 16" with AB = AD, the shorter one its axis), draws nothing rather than put
    the equal marks on sides the question did not call equal."""
    names, lettered = _letters(request, 4)
    named = [m for m in request.measures if len(m.name.strip()) == 2]
    if any(m.what == "diagonal" for m in named):
        return None
    if lettered and not any(m.what in {"side", "length", "equal_side"} for m in named):
        return None
    diagonals = sorted((m.value for m in request.given("diagonal")), reverse=True)
    lengths = sorted(
        m.value for m in request.measures if m.what in {"side", "length", "equal_side"}
    )
    if len(diagonals) >= 2:
        axis, across = diagonals[0], diagonals[1]
        top_rise, bottom_drop, half = axis * _KITE_SPLIT, axis * (1 - _KITE_SPLIT), across / 2
    else:
        short, long = (lengths[0], lengths[-1]) if len(lengths) >= 2 else (3.0, 5.0)
        if short == long:
            return None
        half = short * _KITE_WIDTH
        top_rise, bottom_drop = math.sqrt(short**2 - half**2), math.sqrt(long**2 - half**2)
    corners = [(0.0, -bottom_drop), (half, 0.0), (0.0, top_rise), (-half, 0.0)]
    drawing = _drawing(request, corners, names, lettered)
    unit = request.unit
    shown = len(diagonals) < 2 and len(lengths) >= 2
    drawing.label_side(
        names[1], names[2], length_label(lengths[0], unit) if shown else None, ticks=1
    )
    drawing.label_side(names[2], names[3], None, ticks=1)
    drawing.label_side(names[3], names[0], None, ticks=2)
    drawing.label_side(
        names[0], names[1], length_label(lengths[-1], unit) if shown else None, ticks=2
    )
    if len(diagonals) >= 2:
        axis_label = length_label(diagonals[0], unit)
        across_label = length_label(diagonals[1], unit)
        drawing.line(names[0], names[2], axis_label, dashed=True, label_at=_DIAGONAL_LABEL_AT)
        drawing.line(names[1], names[3], across_label, dashed=True, label_at=_DIAGONAL_LABEL_AT)
        middle = drawing.point((0.0, 0.0))
        drawing.angle(middle, names[1], names[2], right=True)
    return drawing.spec()


def build_regular_polygon(request: FigureRequest) -> FigureSpec | None:
    """A regular polygon: its name and its number of sides agree, and a polygon the question
    does not call regular is not drawn as one."""
    named = POLYGON_SIDES.get(request.shape.removeprefix("regular_"))
    if not request.shape.startswith("regular"):
        return None
    if named is not None and request.sides is not None and named != request.sides:
        return None
    count = request.sides or named
    if count is None or not 3 <= count <= 12:
        return None
    names, lettered = _letters(request, count)
    side = request.first("side", "edge", "length")
    size = side or _REGULAR_SIDE
    radius = size / (2 * math.sin(math.pi / count))
    corners = [polar(radius, 270 - 180 / count + i * 360 / count) for i in range(count)]
    drawing = _drawing(request, corners, names, lettered)
    drawing.shape = f"regular_polygon_{count}"
    for index in range(count):
        label = length_label(side, request.unit) if side is not None and index == 0 else None
        drawing.label_side(names[index], names[(index + 1) % count], label, ticks=1)
    values = _Values(request, names)
    unnamed = values.unnamed_angles[:1]
    _mark_angles(drawing, names, values.angles or dict(zip([1], unnamed, strict=False)))
    return drawing.spec()

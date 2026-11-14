"""A drawn figure says what the question states, all of it, and nothing more.

The last check on every figure, whatever builder drew it. Every label is one of the
question's values (a length the question asks for is never labelled), no value is labelled
more often than it is stated, and every stated value is shown. A flat figure is drawn to
scale, so on one each label is also true where it sits: a labelled side has its length, a
labelled angle its size, a right-angle box a right angle, sides marked equal are equal, a
side or an angle the question names by its letters carries its value there (or, for a side,
an equal mark matching one that does), and a stated perimeter is the outline's. A builder
that met the question passes; one that fell back on a shape the question did not describe
("AB = 13" on a leg, a 40° apex drawn as a base angle, a diameter written on a radius)
draws nothing.

A solid drawn in oblique projection has edges going back drawn short, so it is held to its
labels alone; its builder places each size on its own edge.
"""

from __future__ import annotations

import re
from collections import Counter

from app.modules.math.figure.drawing import Point, angle_at, angle_label, distance, length_label
from app.modules.math.figure.request import FigureRequest, Measure
from app.modules.math.schemas.figure import FigureSpec

# Solids whose receding edges are drawn at half scale.
_OBLIQUE = frozenset({"cube", "cuboid", "triangular_prism", "square_pyramid"})
# Values a figure honours without a label of their own.
_UNLABELLED = frozenset({"perimeter"})
# A solid's height has no edge in its net: the net's faces are sized by it, unlabelled.
_FOLDED = {"square_pyramid_net": frozenset({"height"}), "cone_net": frozenset({"height"})}
_LENGTH_TOLERANCE = 1e-3
_ANGLE_WHATS = frozenset({"angle", "apex_angle", "base_angle"})
_ANGLE_TOLERANCE = 0.05
_LEADING_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def measure_label(measure: Measure, unit: str) -> str | None:
    """The label a stated value is drawn with, or None for one drawn without a label."""
    if measure.what in _UNLABELLED:
        return None
    if measure.what in {"angle", "apex_angle", "base_angle"}:
        return angle_label(measure.value)
    return length_label(measure.value, unit)


def _value(label: str) -> float | None:
    found = _LEADING_NUMBER.match(label)
    return float(found.group()) if found else None


def _close(drawn: float, stated: float, tolerance: float) -> bool:
    return abs(drawn - stated) <= tolerance * max(1.0, abs(stated))


def _labels_hold(spec: FigureSpec, request: FigureRequest) -> bool:
    folded = _FOLDED.get(spec.shape, frozenset())
    stated = Counter(
        label
        for m in request.measures
        if (label := measure_label(m, request.unit)) is not None and m.what not in folded
    )
    drawn = Counter(
        [s.label for s in spec.segments if s.label] + [a.label for a in spec.angles if a.label]
    )
    # A right angle the question states is shown by its box.
    boxed = angle_label(90) if any(mark.right for mark in spec.angles) else None
    return all(count <= stated[label] for label, count in drawn.items()) and all(
        label in drawn or label == boxed for label in stated
    )


def _to_scale(spec: FigureSpec, at: dict[str, Point]) -> bool:
    for segment in spec.segments:
        value = _value(segment.label) if segment.label else None
        length = distance(at[segment.a], at[segment.b])
        if value is not None and not _close(length, value, _LENGTH_TOLERANCE):
            return False
    for mark in spec.angles:
        size = angle_at(at[mark.at], at[mark.a], at[mark.b])
        if mark.right and abs(size - 90) > _ANGLE_TOLERANCE:
            return False
        value = _value(mark.label) if mark.label else None
        if value is not None and abs(size - value) > _ANGLE_TOLERANCE:
            return False
    for ticks in {s.ticks for s in spec.segments if s.ticks}:
        lengths = [distance(at[s.a], at[s.b]) for s in spec.segments if s.ticks == ticks]
        if not all(_close(length, lengths[0], _LENGTH_TOLERANCE) for length in lengths):
            return False
    return True


def _named_holds(spec: FigureSpec, request: FigureRequest, at: dict[str, Point]) -> bool:
    """A value named by letters the figure shows sits on those letters."""
    shown = {point.name for point in spec.points if point.show}
    for measure in request.measures:
        name = measure.name.strip()
        label = measure_label(measure, request.unit)
        if label is None or not name or not set(name) <= shown:
            continue
        if measure.what in {"angle", "apex_angle", "base_angle"}:
            if not _angle_named(spec, name, measure.value, at):
                return False
        elif len(name) == 2 and not _side_named(spec, set(name), label):
            return False
    return True


def _side_named(spec: FigureSpec, ends: set[str], label: str) -> bool:
    """The side carries its value, or is marked equal to one that does ("AB = AD = 5 cm":
    one label, and AD's tick matches AB's)."""
    side = next((s for s in spec.segments if {s.a, s.b} == ends), None)
    if side is None:
        return False
    if side.label == label:
        return True
    return (
        side.label is None
        and bool(side.ticks)
        and any(other.ticks == side.ticks and other.label == label for other in spec.segments)
    )


def _angle_named(spec: FigureSpec, name: str, value: float, at: dict[str, Point]) -> bool:
    """Angle "B" or "ABC": a mark at B carrying the value, between A and C when named."""
    if len(name) not in {1, 3}:
        return False
    vertex = name[1] if len(name) == 3 else name
    if len(name) == 3 and abs(angle_at(at[vertex], at[name[0]], at[name[2]]) - value) > (
        _ANGLE_TOLERANCE
    ):
        return False
    for mark in spec.angles:
        if mark.at != vertex or (len(name) == 3 and {mark.a, mark.b} != {name[0], name[2]}):
            continue
        if mark.label == angle_label(value) or (mark.right and abs(value - 90) < 1e-9):
            return True
    return False


def _ticks_hold(spec: FigureSpec, request: FigureRequest) -> bool:
    """Equal marks agree with the sides the question states: two named sides it gives the
    same length carry the same mark when both are marked, and two it gives different
    lengths never share one."""
    shown = {point.name for point in spec.points if point.show}
    marks: list[tuple[int, float]] = []
    for measure in request.measures:
        name = measure.name.strip()
        if measure.what in _ANGLE_WHATS or len(name) != 2 or not set(name) <= shown:
            continue
        side = next((s for s in spec.segments if {s.a, s.b} == set(name)), None)
        if side is not None and side.ticks:
            marks.append((side.ticks, measure.value))
    for i, (ticks, value) in enumerate(marks):
        for other_ticks, other_value in marks[i + 1 :]:
            same_value = _close(value, other_value, _LENGTH_TOLERANCE)
            if same_value != (ticks == other_ticks):
                return False
    return True


def _perimeter_holds(spec: FigureSpec, request: FigureRequest, at: dict[str, Point]) -> bool:
    perimeter = request.first("perimeter")
    if perimeter is None:
        return True
    if not spec.faces:
        return False
    outline = spec.faces[0]
    around = sum(
        distance(at[p], at[outline[(i + 1) % len(outline)]]) for i, p in enumerate(outline)
    )
    return _close(around, perimeter, _LENGTH_TOLERANCE)


def honours(spec: FigureSpec, request: FigureRequest) -> bool:
    """``spec`` shows every value ``request`` states, true where it sits, and no other."""
    if not _labels_hold(spec, request):
        return False
    if spec.shape in _OBLIQUE:
        return request.first("perimeter") is None
    at = {point.name: (point.x, point.y) for point in spec.points}
    return (
        _to_scale(spec, at)
        and _named_holds(spec, request, at)
        and _ticks_hold(spec, request)
        and _perimeter_holds(spec, request, at)
    )

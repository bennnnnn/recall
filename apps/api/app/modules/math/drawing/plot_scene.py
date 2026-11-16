"""A checked graph before it is drawn: its curves and what the server found on them.

``plot_check`` fills a ``Scene`` with the items that hold; ``plot_draw`` samples, fits the
window and writes the fence. A ``DrawnCurve`` keeps its places (where it crosses, turns and
breaks), worked out once and shared by every item that asks for them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Literal

from sympy import And, Integer, Piecewise, nan, oo

from app.modules.math.drawing.curve_breaks import Break, breaks_and_ends
from app.modules.math.drawing.curve_features import (
    GRID,
    MOST_FOUND,
    bends,
    bisect,
    continuous_at,
    exact_xs,
    snapped,
    turning_points,
    zeros,
)
from app.modules.math.drawing.plot_pieces import Shape, Span
from app.modules.math.drawing.real_curve import RealFunction, X, defined_at


@dataclass(frozen=True)
class Place:
    """A place the server found, exact when SymPy confirms it; ``y`` is its value."""

    x: Any
    y: Any

    @property
    def at(self) -> tuple[float, float]:
        return float(self.x), float(self.y)


def _sharpened(fn: RealFunction, x: float) -> float:
    """A smooth turning point found to full precision where the slope changes sign: the
    golden section stops near √ε on a flat top, too coarse to confirm x = e."""
    step = 1e-5 * max(1.0, abs(x))
    left, right = fn.at(x - step, 1), fn.at(x + step, 1)
    if math.isfinite(left) and math.isfinite(right) and (left > 0) != (right > 0):
        return bisect(lambda v: fn.values(v, 1), x - step, x + step)
    return x


def _holds(span: Span) -> Any:
    """Where ``span`` holds, as SymPy's condition on x."""
    low = (X >= span.low) if span.low_closed else (X > span.low)
    high = (X <= span.high) if span.high_closed else (X < span.high)
    return And(low if span.low != -oo else True, high if span.high != oo else True)


def _inside(span: Span, low: float, high: float) -> tuple[float, float] | None:
    a = low if span.low == -oo else max(low, float(span.low))
    b = high if span.high == oo else min(high, float(span.high))
    return (a, b) if a < b else None


@dataclass
class DrawnCurve:
    name: str
    label: str
    color: int
    # y = f(x): its spans; x = g(y): ``sideways`` instead, a function of y read in X.
    shape: Shape | None = None
    sideways: RealFunction | None = None
    search: tuple[float, float] = (-10.0, 10.0)
    stated_domain: bool = False
    # A line the server worked out drawn as a curve (a triangle's side through two stated
    # points): its slope and offset, its label shown only when the reply writes that line.
    held: tuple[float, ...] = ()
    # The kinds of place the picture marks on it: "roots", "turns", "inflections".
    marked: set[str] = field(default_factory=set)

    @property
    def single(self) -> RealFunction | None:
        """The formula, when one holds for the whole curve (shading, tangents)."""
        if self.shape is None or len(self.shape.spans) != 1 or self.shape.dots:
            return None
        return self.shape.spans[0].fn

    @cached_property
    def whole(self) -> RealFunction | None:
        """The curve as one formula of x, pieces and all: what a region under it, its
        rectangles and its average are taken from."""
        if self.shape is None or not self.shape.spans:
            return None
        if len(self.shape.spans) == 1:
            return self.shape.spans[0].fn
        cases = [(span.fn.expr, _holds(span)) for span in self.shape.spans]
        return RealFunction(Piecewise(*cases, (nan, True)))

    def _each(self) -> list[tuple[Span, float, float]]:
        if self.shape is None:
            return []
        low, high = self.search
        return [(s, *inside) for s in self.shape.spans if (inside := _inside(s, low, high))]

    def span_at(self, x: float) -> Span | None:
        for span, low, high in self._each():
            if low <= x <= high:
                return span
        return None

    def span_holding(self, x: float) -> Span | None:
        """The piece whose own domain holds ``x``, an end it leaves out excluded (x⁰ has
        no value at 0, though its pieces run up to it)."""
        for span, low, high in self._each():
            inside = low < x < high
            # An end the search cut, not the piece's own, holds x.
            at_low = x == low and (span.low == -oo or float(span.low) != low or span.low_closed)
            at_high = x == high and (
                span.high == oo or float(span.high) != high or span.high_closed
            )
            if inside or at_low or at_high:
                return span
        return None

    def _places(self, finder: Any, order: int) -> list[Place]:
        """Each place ``finder`` finds, its x exact where SymPy confirms it (the formula's
        ``order``-th derivative is zero there, or it is a root of one of its factors)."""
        found: list[Place] = []
        breaks_at = [float(b.x) for b in self.breaks]
        for span, low, high in self._each():
            candidates = exact_xs(span.fn)
            beside = 2 * (high - low) / GRID
            for x in finder(span, low, high):
                if any(abs(x - b) < beside for b in breaks_at):
                    continue  # a pole's run to infinity is no turn and no crossing
                x = _sharpened(span.fn, x) if order == 1 else x
                y = span.fn.at(x)
                if math.isfinite(y):
                    found.append(Place(snapped(x, candidates, span.fn.derivative(order)), y))
        return found

    @cached_property
    def roots(self) -> list[Place]:
        return self._places(lambda s, a, b: zeros(s.fn.values, a, b), 0)

    @cached_property
    def turns(self) -> list[Place]:
        return [
            *self._places(lambda s, a, b: turning_points(s.fn.values, a, b), 1),
            *self._corners(),
        ]

    def _corners(self) -> list[Place]:
        """Where two pieces meet with no gap and the curve turns there: the peak at (2, 3) of
        x + 1 then 5 - x, which no piece holds inside it."""
        whole = self.whole
        if self.shape is None or whole is None or len(self.shape.spans) < 2:
            return []
        found: list[Place] = []
        for span in self.shape.spans:
            if (
                span.high in (-oo, oo)
                or self.search[0] >= float(span.high)
                or float(span.high) >= self.search[1]
            ):
                continue
            x = float(span.high)
            here, step = whole.at(x), 1e-4 * max(1.0, abs(x))
            left, right = whole.at(x - step), whole.at(x + step)
            if not (math.isfinite(here) and math.isfinite(left) and math.isfinite(right)):
                continue
            if not continuous_at(whole, x):
                continue
            if (here > left and here > right) or (here < left and here < right):
                found.append(Place(span.high, here))
        return found

    @property
    def listed(self) -> tuple[float, float] | None:
        """The x's between which every place of each kind the picture marks on the curve was
        found. A curve with more than ``MOST_FOUND`` of one (sin 5x's roots) keeps those
        nearest the middle of its search (``curve_features``); a window wider showed roots
        it did not mark. None when none was left out, or on an interval the question states,
        which the picture shows whole."""
        if self.single is None or self.stated_domain:
            return None
        middle = sum(self.search) / 2
        found = {"roots": self.roots, "turns": self.turns}
        if "inflections" in self.marked:
            found["inflections"] = self.inflections
        reach = math.inf
        for kind, places in found.items():
            if kind not in self.marked or len(places) < MOST_FOUND:
                continue
            # Short of the farthest kept: one of two as far away may be the one left out.
            reach = min(reach, max(abs(float(p.x) - middle) for p in places) * (1 - 1e-3))
        return None if reach == math.inf else (middle - reach, middle + reach)

    @cached_property
    def inflections(self) -> list[Place]:
        return self._places(lambda s, a, b: bends(s.fn, a, b), 2)

    @cached_property
    def _breaks_and_ends(self) -> tuple[list[Break], list[tuple[Any, float]]]:
        found: list[Break] = []
        ends: list[tuple[Any, float]] = []
        for span, low, high in self._each():
            more, more_ends = breaks_and_ends(span.fn, low, high, exact_xs(span.fn))
            found += more
            ends += more_ends
        return found, ends

    @property
    def breaks(self) -> list[Break]:
        return self._breaks_and_ends[0]

    @property
    def domain_ends(self) -> list[tuple[Any, float]]:
        """Where its formula's own domain ends, each with the value it settles on there."""
        return self._breaks_and_ends[1]

    @cached_property
    def y_intercept(self) -> Place | None:
        span = self.span_holding(0.0)
        if span is None or not defined_at(span.fn.expr, Integer(0)):
            return None
        y = span.fn.at(0.0)
        return Place(Integer(0), y) if math.isfinite(y) else None


@dataclass
class DrawnLine:
    """y = slope·x + offset, x = ``vertical``, or (a segment) the line from one end to the
    other."""

    slope: Any = None
    offset: Any = None
    vertical: Any = None
    ends: tuple[tuple[float, float], tuple[float, float]] | None = None
    role: Literal["line", "asymptote", "axis", "segment"] = "line"
    label: str = ""
    color: int = 0
    # The values the server worked out for its label: shown only when the reply agrees.
    held: tuple[float, ...] = ()

    def y_at(self, x: float) -> float:
        return float(self.slope) * x + float(self.offset)


@dataclass
class DrawnPoint:
    x: float
    y: float
    label: str = ""
    open: bool = False
    color: int = 0
    # The values the server worked out for its label: shown only when the reply agrees.
    held: tuple[float, ...] = ()
    # Where two edges meet: beside a region, only the meets that bound it are marked.
    meet: bool = False
    # The kind of place it marks on its curve, when the picture marks every one of a kind:
    # "roots", "turns", "inflections".
    kind: str = ""


@dataclass
class DrawnRegion:
    points: list[tuple[float, float]]
    kind: Literal["shade", "strip", "mirror"] = "shade"
    color: int = 0


@dataclass(frozen=True)
class Shaded:
    """A shaded region's two edges and bounds, along x or y: what a slice is cut from."""

    first: RealFunction
    second: RealFunction
    low: float
    high: float
    wrt: str


@dataclass
class Scene:
    curves: dict[str, DrawnCurve] = field(default_factory=dict)
    lines: dict[str, DrawnLine] = field(default_factory=dict)
    marks: list[DrawnLine] = field(default_factory=list)
    points: list[DrawnPoint] = field(default_factory=list)
    regions: list[DrawnRegion] = field(default_factory=list)
    shaded: list[Shaded] = field(default_factory=list)
    # Places the window must show beyond what is drawn: where the curves cross and turn.
    focus: list[tuple[float, float]] = field(default_factory=list)
    equal: bool = False
    asymptote_sides: set[int] = field(default_factory=set)
    # The values the reply's own working writes: a label the server worked out is shown
    # only when they hold it.
    reply_values: tuple[float, ...] = ()
    # The lines it writes, each (slope, offset), or (None, a) for x = a.
    reply_lines: tuple[tuple[float | None, float], ...] = ()
    # The kinds of place the question asks for ("turning points": "turns"): kept whole when
    # a picture marks more than it can carry.
    asked: tuple[str, ...] = ()
    # What the axes measure: the question's letters ("t", "v"), with units when it gives them.
    x_label: str = "x"
    y_label: str = "y"

    def add_point(self, point: DrawnPoint) -> None:
        for seen in self.points:
            near = 1e-6 * max(1.0, abs(point.x), abs(point.y))
            if abs(seen.x - point.x) < near and abs(seen.y - point.y) < near:
                seen.label = seen.label or point.label
                seen.meet = seen.meet and point.meet
                return
        self.points.append(point)

"""Where a curve breaks, and the lines it runs along: holes, jumps and asymptotes.

A break is a place the formula is undefined or jumps: a place SymPy finds it singular (the
graph sampler's own reading, ``solve.graph_sampling.singular_xs``), the edge of a
logarithm's domain, a place the samples run off to infinity. Each side is read from the
curve itself (it runs off to infinity, settles on a value, or has no values there), so a
removable hole, a jump and a vertical asymptote are told apart without SymPy's limits,
which can stall on |…| and odd roots; each side is read as the graph sampler reads it
(``solve.graph_sampling.side``). A horizontal or oblique asymptote is SymPy's: its
slope and offset are limits at ±∞, taken only when the samples already settle on them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from sympy import Expr, Symbol, limit, oo

from app.modules.math.drawing.curve_features import GRID, MOST_FOUND, bisect_all, snapped
from app.modules.math.drawing.real_curve import RealFunction, X
from app.modules.math.solve.graph_sampling import (
    SIDE_STEPS,
    Side,
    pole_flips,
    side,
    singular_xs,
)

# Where a curve is looked at far out, each a little off a whole number: x^x has a value at
# every negative whole number and at no x between, and settled on 0 at -10⁶ as if it ran
# along y = 0 there (its window ran to -2.7, where it has no curve).
FAR = (1e4 + 0.37, 1e5 + 0.37, 1e6 + 0.37)
_T = Symbol("t", positive=True)


@dataclass(frozen=True)
class Break:
    x: Any
    left: Side
    right: Side
    # The formula's own value at the place, when it has one.
    value: float | None

    @property
    def asymptote(self) -> bool:
        return "infinite" in (self.left.kind, self.right.kind)


def _candidates(fn: RealFunction, low: float, high: float, exact: list[Any]) -> list[Any]:
    """SymPy's singular places and the exact roots of the formula's factors in the window,
    then the places the samples jump across a pole or leave off (a tangent's π/2, the end of
    a domain)."""
    found: list[Any] = []
    for candidate in [*singular_xs(fn.expr, X, low, high), *exact]:
        try:
            at = float(candidate)
            if low < at < high and all(abs(float(seen) - at) > 1e-12 for seen in found):
                found.append(candidate)
        except (TypeError, ValueError):
            continue
    xs = np.linspace(low, high, GRID)
    ys = fn.values(xs)
    gaps = [i for i in range(len(xs) - 1) if np.isfinite(ys[i]) != np.isfinite(ys[i + 1])]
    # The graph sampler's own poles (``graph_sampling.pole_flips``), each at its own place:
    # the sign flips there, and its reciprocal is zero there (tan x's π/2, exactly).
    poles = sorted(set(pole_flips(ys)))
    # Bisected all at once; snapped to an exact place only when they are few: a fast
    # oscillation's hundreds of flips cost a second of SymPy for places no label shows.
    at = bisect_all(fn.values, xs[poles], xs[[i + 1 for i in poles]]) if poles else []
    residual = 1 / fn.expr if len(poles) <= MOST_FOUND else None
    pole_at = {i: snapped(float(x), [], residual) for i, x in zip(poles, at, strict=True)}
    for i in sorted({*gaps, *poles}):
        x = pole_at[i] if i in pole_at else snapped(float((xs[i] + xs[i + 1]) / 2), [], None)
        if all(abs(float(seen) - float(x)) > (xs[1] - xs[0]) for seen in found):
            found.append(x)
    return found


def breaks(fn: RealFunction, low: float, high: float, exact: list[Any]) -> list[Break]:
    return breaks_and_ends(fn, low, high, exact)[0]


def breaks_and_ends(
    fn: RealFunction, low: float, high: float, exact: list[Any]
) -> tuple[list[Break], list[tuple[Any, float]]]:
    """Where the curve breaks (a pole, a jump, a hole), and where its own domain ends inside
    [low, high] with the value it settles on there: ln x/√(x² - 1) starts at (1, 0), where
    it has no value, and the window began at 1.75 without it."""
    found: list[Break] = []
    ends: list[tuple[Any, float]] = []
    for candidate in _candidates(fn, low, high, exact):
        x0 = float(candidate)
        left, right = side(fn.values, x0, -1), side(fn.values, x0, 1)
        here = fn.at(x0)
        sides = (left.kind, right.kind)
        # Beside a pole the formula's value at a decimal place is only a huge number.
        value = here if math.isfinite(here) and "infinite" not in sides else None
        if "infinite" not in sides and "finite" not in sides:
            settled = _domain_end(fn, x0)
            if settled is not None:
                ends.append((candidate, settled))
            continue
        if left.kind == right.kind == "finite" and value is not None:
            near = 1e-4 * (1.0 + abs(value))
            if abs(left.value - value) < near and abs(right.value - value) < near:
                continue  # continuous: a corner or a cusp, no break
        if "none" in sides and "infinite" not in sides:
            # The end of the curve's domain, as √(9 - x²) ends at 3: no break.
            ends.append((candidate, left.value if left.kind == "finite" else right.value))
            continue
        found.append(Break(candidate, left, right, value))
    return sorted(found, key=lambda b: float(b.x)), ends


def _domain_end(fn: RealFunction, x0: float) -> float | None:
    """The value a curve with values on one side of ``x0`` only settles on there, when it
    settles slower than ``side`` waits for: √(x - 1) and ln x/√(x² - 1) at 1, whose steps
    toward 0 shrink by √10 each."""
    scale = max(1.0, abs(x0))
    near = {d: fn.values(np.array([x0 + d * step * scale for step in SIDE_STEPS])) for d in (-1, 1)}
    have = [d for d, values in near.items() if np.all(np.isfinite(values))]
    if len(have) != 1 or np.any(np.isfinite(near[-have[0]])):
        return None
    values = near[have[0]]
    steps = np.abs(np.diff(values))
    return float(values[-1]) if bool(np.all(steps[1:] <= 0.5 * steps[:-1])) else None


def has_pole(fn: RealFunction, low: float, high: float) -> bool:
    """The formula runs off to infinity somewhere on [low, high]: inside it on either side,
    or at an end on the side that faces in (1/x² on [-1, 1], 1/x on [0, 1]). An area, an
    average or a sum of rectangles across one is no number the picture can show."""
    room = 1e-9 * max(1.0, abs(low), abs(high))
    for candidate in _candidates(fn, low - room, high + room, []):
        x0 = float(candidate)
        inward = [d for d in (-1, 1) if ((x0 > low + room) if d < 0 else (x0 < high - room))]
        if any(side(fn.values, x0, d).kind == "infinite" for d in inward):
            return True
    return False


def _numeric_line(fn: RealFunction, direction: int) -> tuple[float, float] | None:
    """The line the samples settle on far out, when they settle: secant slopes that agree,
    and offsets from the last of them that agree."""
    far = [direction * x for x in FAR]
    ys = [fn.at(x) for x in far]
    if not all(math.isfinite(y) for y in ys):
        return None
    slopes = [(ys[i + 1] - ys[i]) / (far[i + 1] - far[i]) for i in range(len(far) - 1)]
    slope = slopes[-1]
    if abs(slopes[0] - slope) > 1e-3 * (1 + abs(slope)):
        return None
    offsets = [y - slope * x for x, y in zip(far[1:], ys[1:], strict=True)]
    if abs(offsets[0] - offsets[1]) > 1e-2 * (1 + abs(offsets[1])):
        return None
    return slope, offsets[1]


def _limit(expr: Any) -> Any | None:
    try:
        value = limit(expr, _T, oo)
    except (NotImplementedError, ValueError, TypeError, ZeroDivisionError, RecursionError):
        return None
    return value if isinstance(value, Expr) and value.is_real and value.is_finite else None


def end_lines(fn: RealFunction) -> list[tuple[Any, Any]]:
    """The horizontal and oblique asymptotes, each (slope, offset) as SymPy's limits give
    them, the same line at both ends counted once."""
    found: list[tuple[Any, Any]] = []
    for direction in (1, -1):
        numeric = _numeric_line(fn, direction)
        if numeric is None:
            continue
        far = fn.expr.subs(X, direction * _T)
        slope = _limit(far / (direction * _T))
        if slope is None or abs(float(slope) - numeric[0]) > 1e-3 * (1 + abs(numeric[0])):
            continue
        offset = _limit(far - slope * direction * _T)
        if offset is None or abs(float(offset) - numeric[1]) > 1e-2 * (1 + abs(numeric[1])):
            continue
        if _is_the_curve(fn, slope, offset):
            continue  # (x² - 1)/(x - 1) runs along x + 1 because it is x + 1: no asymptote
        if all((slope, offset) != seen for seen in found):
            found.append((slope, offset))
    return found


def _is_the_curve(fn: RealFunction, slope: Any, offset: Any) -> bool:
    """The curve is the line itself wherever it has a value: y = 3's "asymptote" y = 3."""
    xs = np.array([-7.3, -2.9, -0.61, 0.43, 1.7, 3.1, 8.9])
    ys = fn.values(xs)
    line = float(slope) * xs + float(offset)
    finite = np.isfinite(ys)
    return int(finite.sum()) >= 3 and bool(
        np.all(np.abs(ys[finite] - line[finite]) < 1e-9 * (1.0 + np.abs(line[finite])))
    )

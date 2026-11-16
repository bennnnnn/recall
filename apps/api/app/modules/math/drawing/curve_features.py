"""Where a curve crosses, turns, bends and breaks, found by the server.

Each kind is found from the curve itself over a dense grid and refined (a sign change by
bisection, a turning point by golden section), so a cusp, a corner and a turning point are
found the same way, and a pole is never taken for a root. A place found is then given its
exact value when SymPy confirms one: a root of the formula's own factors (``exact_xs``), or
a simple closed form (π/4, e, √5) at which the formula that defines it is zero to 20 digits.
Otherwise it is the refined decimal. Nothing here raises: what cannot be found is not.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np
from sympy import (
    Abs,
    CRootOf,
    E,
    Float,
    Poly,
    PolynomialError,
    Pow,
    denom,
    log,
    nsimplify,
    numer,
    pi,
    sign,
    together,
)

from app.modules.math.drawing.real_curve import RealFunction, X

GRID = 4001
_BISECTIONS = 64
_GOLDEN = 0.6180339887498949
_SAME_X = 1e-6
# A place within this of an exact candidate is that candidate.
_SNAP = 1e-7
_HIGHEST_DEGREE = 8
# A picture marks at most this many of one kind of place on a curve.
MOST_FOUND = 12

Values = Callable[[Any], Any]


def bisect(values: Values, low: float, high: float) -> float:
    return float(bisect_all(values, np.array([low]), np.array([high]))[0])


def bisect_all(values: Values, lows: Any, highs: Any) -> Any:
    """Each bracket [low, high] bisected to its sign change, all at once: one call of
    ``values`` a step for every bracket, not one per bracket (a fast-oscillating curve's
    thousand roots took a second and a half one by one). A bracket whose midpoint has no
    value stops there."""
    low, high = np.asarray(lows, dtype=float).copy(), np.asarray(highs, dtype=float).copy()
    if not low.size:
        return low
    f_low = values(low)
    done = np.zeros(low.shape, dtype=bool)
    result = np.empty(low.shape)
    for _ in range(_BISECTIONS):
        mid = (low + high) / 2
        f_mid = values(mid)
        stop = ~done & ~np.isfinite(f_mid)
        result[stop], done[stop] = mid[stop], True
        same = (f_mid > 0) == (f_low > 0)
        move_low = ~done & same
        move_high = ~done & ~same
        low[move_low], f_low[move_low] = mid[move_low], f_mid[move_low]
        high[move_high] = mid[move_high]
    result[~done] = ((low + high) / 2)[~done]
    return result


def _golden_all(values: Values, lows: Any, highs: Any, senses: Any) -> Any:
    """Each bracket's x where ``sense`` * value is least, all at once (``_bisect_all``)."""
    a, b = np.asarray(lows, dtype=float).copy(), np.asarray(highs, dtype=float).copy()
    if not a.size:
        return a
    c, d = b - _GOLDEN * (b - a), a + _GOLDEN * (b - a)
    done = np.zeros(a.shape, dtype=bool)
    for _ in range(_BISECTIONS):
        fc, fd = senses * values(c), senses * values(d)
        done |= ~(np.isfinite(fc) & np.isfinite(fd))
        left = ~done & (fc < fd)
        right = ~done & ~(fc < fd)
        b[left], d[left] = d[left], c[left]
        c[left] = b[left] - _GOLDEN * (b[left] - a[left])
        a[right], c[right] = c[right], d[right]
        d[right] = a[right] + _GOLDEN * (b[right] - a[right])
    return (a + b) / 2


def _dedupe(xs: list[float], low: float, high: float) -> list[float]:
    """The places found, each once, in order: the ones nearest the middle of the search when
    there are more than a picture marks. A periodic curve's dozens of roots kept the twelve
    leftmost, and its window went with them ([-10.9, 1.17] for sin 5x, its root at 0.628
    left unmarked)."""
    out: list[float] = []
    for x in sorted(xs):
        if not out or abs(x - out[-1]) > _SAME_X * max(1.0, abs(x)):
            out.append(x)
    middle = (low + high) / 2
    return sorted(sorted(out, key=lambda x: abs(x - middle))[:MOST_FOUND])


def _scale(ys: Any) -> float:
    finite = np.abs(ys[np.isfinite(ys)])
    return float(np.median(finite)) if finite.size else 1.0


def zeros(values: Values, low: float, high: float) -> list[float]:
    """Where ``values`` is zero: crossings and touches, never a pole's sign change."""
    xs = np.linspace(low, high, GRID)
    ys = values(xs)
    scale = _scale(ys) + 1.0
    found: list[float] = [float(x) for x, y in zip(xs, ys, strict=True) if y == 0]
    y0, y1 = ys[:-1], ys[1:]
    with np.errstate(invalid="ignore"):
        crossing = (
            np.isfinite(y0) & np.isfinite(y1) & (y0 != 0) & (y1 != 0) & ((y0 > 0) != (y1 > 0))
        )
    roots = bisect_all(values, xs[:-1][crossing], xs[1:][crossing])
    held = np.abs(values(roots)) < 1e-6 * scale if roots.size else np.array([], dtype=bool)
    found += [float(x) for x in roots[held]]
    m = np.abs(ys)
    m0, m1, m2 = m[:-2], m[1:-1], m[2:]
    with np.errstate(invalid="ignore"):
        dips = np.isfinite(m0) & np.isfinite(m2) & (m1 <= m0) & (m1 < m2) & (m1 < 1e-2 * scale)
    touches = _golden_all(
        lambda v: np.abs(values(v)), xs[:-2][dips], xs[2:][dips], np.ones(int(dips.sum()))
    )
    if touches.size:
        found += [float(x) for x in touches[np.abs(values(touches)) < 1e-9 * scale]]
    return _dedupe(found, low, high)


def turning_points(values: Values, low: float, high: float) -> list[float]:
    """Interior local maxima and minima, cusps and corners included; a flat stretch none."""
    xs = np.linspace(low, high, GRID)
    ys = values(xs)
    y0, y1, y2 = ys[:-2], ys[1:-1], ys[2:]
    with np.errstate(invalid="ignore"):
        finite = np.isfinite(y0) & np.isfinite(y1) & np.isfinite(y2) & ~((y0 == y1) & (y1 == y2))
        low_turn = finite & (y1 <= y0) & (y1 < y2)
        high_turn = finite & ~low_turn & (y1 >= y0) & (y1 > y2)
    turn = low_turn | high_turn
    senses = np.where(low_turn, 1.0, -1.0)[turn]
    found = _golden_all(values, xs[:-2][turn], xs[2:][turn], senses)
    if found.size:
        found = found[np.isfinite(values(found))]
    return _dedupe([float(x) for x in found], low, high)


def bends(fn: RealFunction, low: float, high: float) -> list[float]:
    """Inflection points: where the second derivative changes sign and the curve runs on.
    The sign is read across a place it has no value (x^(1/3) bends at 0, where its second
    derivative is infinite), and a second derivative that is zero but for rounding (a
    straight piece) has none."""
    xs = np.linspace(low, high, GRID)
    second = fn.values(xs, 2)
    finite = np.abs(second[np.isfinite(second)])
    if not finite.size:
        return []
    noise = 1e-9 * (1.0 + float(np.median(finite)))
    lows: list[float] = []
    highs: list[float] = []
    last: int | None = None
    for i in range(len(xs)):
        s1 = second[i]
        if not np.isfinite(s1) or abs(s1) <= noise:
            continue
        if last is not None and (second[last] > 0) != (s1 > 0):
            lows.append(float(xs[last]))
            highs.append(float(xs[i]))
        last = i
    changes = bisect_all(lambda v: fn.values(v, 2), np.array(lows), np.array(highs))
    found = [float(x) for x in changes if continuous_at(fn, float(x))]
    return _dedupe(found, low, high)


def continuous_at(fn: RealFunction, x: float) -> bool:
    """The curve runs through x: its values either side close in on its value as they near
    it (x^(1/3) at 0, steep as it is), where a jump or a pole keeps them apart."""
    here = fn.at(x)
    if not math.isfinite(here):
        return False
    gaps: list[float] = []
    for step in (1e-4, 1e-8):
        near = step * max(1.0, abs(x))
        sides = [fn.at(x - near), fn.at(x + near)]
        if not all(math.isfinite(v) for v in sides):
            return False
        gaps.append(max(abs(v - here) for v in sides))
    return gaps[1] < 1e-3 * (1.0 + abs(here)) or gaps[1] < 0.5 * gaps[0]


def _polynomial_roots(expr: Any) -> list[Any]:
    try:
        poly = Poly(expr, X)
    except (PolynomialError, ValueError, TypeError):
        return []
    if poly.degree() < 1 or poly.degree() > _HIGHEST_DEGREE or not poly.domain.is_Exact:
        return []
    try:
        roots = poly.real_roots()
    except (NotImplementedError, ValueError, TypeError):
        return []
    return [root for root in roots if not isinstance(root, CRootOf)]


def exact_xs(fn: RealFunction) -> list[Any]:
    """The exact x's a curve's places may be: roots of the numerators and denominators of the
    formula and its first two derivatives, and of what sits inside |…|, sign, a log or a
    root. A turning point, a cusp, an asymptote and a crossing of an axis are all among them
    for the school formulas (a polynomial, a rational function, a root of one)."""
    parts: list[Any] = []
    for order in range(3):
        try:
            joined = together(fn.derivative(order))
        except (TypeError, ValueError):
            continue
        parts += [numer(joined), denom(joined)]
    for node in fn.expr.atoms(Abs, sign, log):
        parts.append(node.args[0])
    parts += [node.base for node in fn.expr.atoms(Pow) if not node.exp.is_Integer]
    found: list[Any] = []
    for part in parts:
        for root in _polynomial_roots(part):
            if all(root != seen for seen in found):
                found.append(root)
    return found


def snapped(x: float, candidates: list[Any], residual: Any | None) -> Any:
    """``x`` as an exact value when SymPy confirms one, else as the decimal found."""
    for candidate in candidates:
        try:
            if abs(float(candidate) - x) < _SNAP * max(1.0, abs(x)):
                return candidate
        except (TypeError, ValueError):
            continue
    if residual is not None:
        try:
            guess = nsimplify(x, [pi, E], tolerance=1e-10, rational=False)
            if guess.count_ops() <= 6 and abs(float(guess) - x) < _SNAP * max(1.0, abs(x)):
                error = residual.subs(X, guess).evalf(30)
                if error.is_real and abs(float(error)) < 1e-20:
                    return guess
        except (TypeError, ValueError, ZeroDivisionError, AttributeError):
            pass
    return Float(x, 12)

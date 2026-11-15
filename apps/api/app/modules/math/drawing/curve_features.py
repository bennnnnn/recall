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
_MOST_FOUND = 12

Values = Callable[[Any], Any]


def _scalar(values: Values, x: float) -> float:
    return float(values(np.array([x]))[0])


def bisect(values: Values, low: float, high: float) -> float:
    f_low = _scalar(values, low)
    for _ in range(_BISECTIONS):
        mid = (low + high) / 2
        f_mid = _scalar(values, mid)
        if not math.isfinite(f_mid):
            return mid
        if (f_mid > 0) == (f_low > 0):
            low, f_low = mid, f_mid
        else:
            high = mid
    return (low + high) / 2


def _golden(values: Values, low: float, high: float, sense: int) -> float:
    """The x in [low, high] where ``sense`` * value is least."""
    a, b = low, high
    c, d = b - _GOLDEN * (b - a), a + _GOLDEN * (b - a)
    for _ in range(_BISECTIONS):
        fc, fd = sense * _scalar(values, c), sense * _scalar(values, d)
        if not (math.isfinite(fc) and math.isfinite(fd)):
            break
        if fc < fd:
            b, d = d, c
            c = b - _GOLDEN * (b - a)
        else:
            a, c = c, d
            d = a + _GOLDEN * (b - a)
    return (a + b) / 2


def _dedupe(xs: list[float]) -> list[float]:
    out: list[float] = []
    for x in sorted(xs):
        if not out or abs(x - out[-1]) > _SAME_X * max(1.0, abs(x)):
            out.append(x)
    return out[:_MOST_FOUND]


def _scale(ys: Any) -> float:
    finite = np.abs(ys[np.isfinite(ys)])
    return float(np.median(finite)) if finite.size else 1.0


def zeros(values: Values, low: float, high: float) -> list[float]:
    """Where ``values`` is zero: crossings and touches, never a pole's sign change."""
    xs = np.linspace(low, high, GRID)
    ys = values(xs)
    scale = _scale(ys) + 1.0
    found: list[float] = [float(x) for x, y in zip(xs, ys, strict=True) if y == 0]
    for i in range(len(xs) - 1):
        y0, y1 = ys[i], ys[i + 1]
        if not (np.isfinite(y0) and np.isfinite(y1)) or y0 == 0 or y1 == 0 or (y0 > 0) == (y1 > 0):
            continue
        root = bisect(values, float(xs[i]), float(xs[i + 1]))
        if abs(_scalar(values, root)) < 1e-6 * scale:
            found.append(root)
    magnitude = np.abs(ys)
    for i in range(1, len(xs) - 1):
        m0, m1, m2 = magnitude[i - 1], magnitude[i], magnitude[i + 1]
        if np.isfinite(m0) and np.isfinite(m2) and m1 <= m0 and m1 < m2 and m1 < 1e-2 * scale:
            touch = _golden(lambda v: np.abs(values(v)), float(xs[i - 1]), float(xs[i + 1]), 1)
            if abs(_scalar(values, touch)) < 1e-9 * scale:
                found.append(touch)
    return _dedupe(found)


def turning_points(values: Values, low: float, high: float) -> list[float]:
    """Interior local maxima and minima, cusps and corners included; a flat stretch none."""
    xs = np.linspace(low, high, GRID)
    ys = values(xs)
    found: list[float] = []
    for i in range(1, len(xs) - 1):
        y0, y1, y2 = ys[i - 1], ys[i], ys[i + 1]
        if not (np.isfinite(y0) and np.isfinite(y1) and np.isfinite(y2)) or y0 == y1 == y2:
            continue
        sense = 1 if (y1 <= y0 and y1 < y2) else -1 if (y1 >= y0 and y1 > y2) else 0
        if sense == 0:
            continue
        x = _golden(values, float(xs[i - 1]), float(xs[i + 1]), sense)
        if math.isfinite(_scalar(values, x)):
            found.append(x)
    return _dedupe(found)


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
    found: list[float] = []
    last: int | None = None
    for i in range(len(xs)):
        s1 = second[i]
        if not np.isfinite(s1) or abs(s1) <= noise:
            continue
        if last is not None and (second[last] > 0) != (s1 > 0):
            x = bisect(lambda v: fn.values(v, 2), float(xs[last]), float(xs[i]))
            if continuous_at(fn, x):
                found.append(x)
        last = i
    return _dedupe(found)


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

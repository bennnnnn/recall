"""A formula as the reals read it, ready to evaluate: odd roots of negatives are real.

SymPy, and numpy after it, take the principal complex branch of a rational power, under
which x^(1/3) is not real for x < 0: round 3's x^(1/3)(x + 3)^(2/3) lost its cusp, and
(x² - 4)^(2/3) drew a flat line across [-2, 2]. In real algebra b^(p/q) with q odd is the
real root, sign(b)^p |b|^(p/q), and that is what is drawn and differentiated here. Its
derivatives are SymPy's of that form; the impulse at sign's jump is no slope and is left
out (a corner is found from the curve itself, ``curve_features``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sympy import (
    Abs,
    DiracDelta,
    Expr,
    Float,
    Rational,
    S,
    Symbol,
    diff,
    lambdify,
    nan,
    oo,
    preorder_traversal,
    sign,
    zoo,
)

from app.modules.math.solve.graph_sampling import sample_at
from app.modules.math.solve.odd_roots import real_branch

# The variable every formula is read in: real, so |x| and sign(x) differentiate as they do
# on the number line.
X = Symbol("x", real=True)


def _no_impulse(expr: Any) -> Any:
    return expr.replace(DiracDelta, lambda *_args: S.Zero)


def _signed(expr: Any) -> Any:
    """|u| as u·sign(u), which SymPy differentiates for any u (|ln x| included): its slope
    is sign(u)·u' away from u = 0."""
    return expr.replace(Abs, lambda inner: inner * sign(inner))


def as_real(expr: Any, variable: Symbol | None) -> Any:
    """``expr`` in ``X``, the real variable, on its real branch."""
    if variable is not None and variable != X:
        expr = expr.subs(variable, X)
    return real_branch(expr)


@dataclass
class RealFunction:
    """One formula of x: its SymPy form and its values and slopes over numpy arrays."""

    expr: Any
    _derivatives: list[Any] = field(default_factory=list)
    _numeric: dict[int, Any] = field(default_factory=dict)

    def derivative(self, order: int) -> Any:
        while len(self._derivatives) < order:
            last = self._derivatives[-1] if self._derivatives else _signed(self.expr)
            self._derivatives.append(_no_impulse(diff(last, X)))
        return self.expr if order == 0 else self._derivatives[order - 1]

    def values(self, xs: Any, order: int = 0) -> Any:
        """The formula's (or a derivative's) value at every x; NaN where it has none."""
        fn = self._numeric.get(order)
        try:
            if fn is None:
                fn = lambdify(X, self.derivative(order), modules=["numpy"])
                self._numeric[order] = fn
            found = sample_at(fn, np.asarray(xs, dtype=float))
        except (TypeError, ValueError, ZeroDivisionError, OverflowError, NameError):
            return np.full(np.shape(xs), np.nan)
        return np.where(np.isfinite(found), found, np.nan)

    def at(self, x: float, order: int = 0) -> float:
        return float(self.values(np.array([x]), order)[0])

    def exact_at(self, x: Any) -> Any | None:
        """The formula's exact value at an exact x, or None where it has none."""
        try:
            value = self.expr.subs(X, x)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
        if not isinstance(value, Expr) or not value.is_real or value.has(S.ComplexInfinity):
            return None
        return value

    def slope_at(self, x: Any) -> Any | None:
        try:
            value = self.derivative(1).subs(X, x)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
        if not isinstance(value, Expr) or not value.is_real or value.has(S.ComplexInfinity):
            return None
        return value


# The largest denominator a decimal place is read as a simple fraction with.
_SIMPLE_DENOMINATOR = 1000


def defined_at(expr: Any, x0: Any) -> bool:
    """``expr`` has a value at ``x0`` as written: no 0⁰ or ∞⁰ and no division by zero there.
    SymPy and numpy both give 1 for x^x and (1 + 1/x)^x at 0, where neither has one, and a
    point marked there marked what is not on the curve. A decimal is read as the simple
    number it is within 1e-9 of (0^x + x's root found at 2·10⁻¹⁶ is 0, where it has none)."""
    if isinstance(x0, (Float, float)):
        # Only a simple fraction: nsimplify turned x^x's turn at 1/e into a ratio of
        # ten-digit numbers, and SymPy's exact power of it ran for hours.
        near = Rational(float(x0)).limit_denominator(_SIMPLE_DENOMINATOR)
        close = abs(float(near) - float(x0)) <= 1e-9 * max(1.0, abs(float(x0)))
        if close and not defined_at(expr, near):
            return False
    try:
        for node in preorder_traversal(expr):
            if not getattr(node, "free_symbols", None):
                continue
            if node.is_Pow:
                base, exponent = (part.subs(X, x0) for part in node.args)
                if base.has(zoo, nan, oo, -oo) or exponent.has(zoo, nan, oo, -oo):
                    return False
                if base == 0 and (exponent == 0 or exponent.is_negative):
                    return False
            if node.subs(X, x0).has(zoo, nan):
                return False
    except (TypeError, ValueError, ZeroDivisionError):
        return False
    return True

"""A lambdified function evaluated over a grid of inputs, for the graph samplers, and how
it leaves a place it breaks at, one side at a time."""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, Literal

import numpy as np
from sympy.utilities.lambdify import lambdify

from app.modules.math.solve.odd_roots import real_branch


def sample_at(fn: Any, inputs: Any) -> Any:
    """``fn`` at every input. A constant (``y = 5``) evaluates to one number, so spread it.

    Outside its domain (``sqrt`` of a negative, ``log 0``) a function is NaN or ±inf,
    which every caller drops; numpy's warning about it is expected, not a fault.
    """
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        return np.broadcast_to(np.asarray(fn(inputs), dtype=float), inputs.shape)


def real_lambdify(variable: Any, expr: Any) -> Any:
    """``expr`` as a numpy function of ``variable``, odd roots of negatives real (x^(1/3) at
    -8 is -2), as the phone reads the graph fence (``lib/math/graphExpr.ts``)."""
    return lambdify(variable, real_branch(expr), modules=["numpy"])


# How near a break a side is read: each step a tenth of the one before.
_STEPS = (1e-3, 1e-4, 1e-5, 1e-6, 1e-7)


@dataclass(frozen=True)
class Side:
    """How a curve leaves a place on one side: to a value, to infinity, or not at all."""

    kind: Literal["none", "finite", "infinite"]
    value: float = 0.0


def side(fn: Any, x0: float, direction: int) -> Side:
    """How the curve leaves ``x0`` on one side: to a value (the steps toward it shrink), to
    infinity (its size grows and the steps do not shrink, as 1/x's and ln x's do not), or
    not at all (no values there). ``fn`` is a numpy function, as ``real_lambdify`` makes."""
    scale = max(1.0, abs(x0))
    near = np.array([x0 + direction * step * scale for step in _STEPS])
    values = [float(v) for v in sample_at(fn, near)]
    if not all(math.isfinite(v) for v in values):
        return Side("none")
    steps = [abs(b - a) for a, b in pairwise(values)]
    sizes = [abs(v) for v in values]
    if steps[-1] <= 1e-4 * (1.0 + sizes[-1]):
        return Side("finite", values[-1])
    growing = all(b > a for a, b in pairwise(sizes))
    if growing and steps[-1] >= 0.5 * steps[-2] and sizes[-1] > 5:
        return Side("infinite", math.copysign(1.0, values[-1]))
    return Side("none")


def jump_xs(fn: Any, places: list[float]) -> list[float]:
    """The places among ``places`` the curve jumps at: a value on each side, and not the
    same one. 4|x² - 1|/(x - 1) jumps from -8 to 8 at 1; a sampled line drawn across it
    (round 3's c038) showed no jump at all."""
    found: list[float] = []
    for x0 in places:
        left, right = side(fn, x0, -1), side(fn, x0, 1)
        apart = abs(left.value - right.value) > 1e-6 * (1.0 + abs(left.value))
        if left.kind == right.kind == "finite" and apart:
            found.append(x0)
    return found

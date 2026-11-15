"""A lambdified function evaluated over a grid of inputs, for the graph samplers."""

from __future__ import annotations

from typing import Any

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

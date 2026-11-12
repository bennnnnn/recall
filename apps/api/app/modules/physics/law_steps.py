"""A step a law's substitution takes for granted: a symbol it uses that is no given.

The radioactive-decay law ``N = N_0 / 2^n`` is substituted as ``N = 80 / 2^4``; the 4 is
the number of half-lives, ``n = t / T_{1/2}``, and the sample is the given ``m``. Without
the step a student meets ``n`` and ``N_0`` nowhere (review 2026-11-12, D3). Each step is
written from the givens as typed when they share a unit (``20 days / 5 days``), else in SI.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.modules.physics.catalog import formula_spec, symbol_for
from app.modules.physics.display import latex_given, latex_unit, latex_working
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solvers.si import to_si
from app.services.solving import SolveServiceError


@dataclass(frozen=True)
class LawSteps:
    """What the law's section adds under it, and the rows **Substitution** opens with."""

    formula: tuple[str, ...] = ()
    substitution: tuple[str, ...] = ()


_NONE = LawSteps()
# The power the decay substitution raises 2 to: 2^{4}.
_HALVES = re.compile(r"2\^\{(?P<n>-?\d+(?:\.\d+)?)\}")


def _symbol(operation: str, name: str) -> str | None:
    spec = formula_spec(operation)
    return None if spec is None else symbol_for(spec, name)


def _quantity(value: float, unit: str) -> str:
    return f"{latex_given(value)}{latex_unit(unit)}"


def _halves(intent: PhysicsIntent, substitutions: tuple[str, ...]) -> LawSteps:
    """``n = t / T_{1/2}`` before ``N = N_0 / 2^n``, when ``n`` was worked from two times."""
    params = intent.physics_params or {}
    units = intent.physics_units or {}
    if "n_halves" in params or not {"elapsed", "half_life", "m"} <= params.keys():
        return _NONE
    operation = intent.physics_op or ""
    elapsed, half_life, sample = (
        _symbol(operation, name) for name in ("elapsed", "half_life", "m")
    )
    stated = _HALVES.search(" ".join(substitutions))
    if not (elapsed and half_life and sample and stated) or params["half_life"] <= 0:
        return _NONE
    shown = [
        (params["elapsed"], units.get("elapsed", "")),
        (params["half_life"], units.get("half_life", "")),
    ]
    if shown[0][1] != shown[1][1]:
        try:
            shown = [
                (to_si(value, unit, expected_key=key), "s")
                for (value, unit), key in zip(shown, ("elapsed", "half_life"), strict=True)
            ]
        except SolveServiceError:
            return _NONE
    value = shown[0][0] / shown[1][0]
    if not math.isclose(value, float(stated.group("n")), rel_tol=1e-4):
        return _NONE
    fraction = rf"\frac{{{_quantity(*shown[0])}}}{{{_quantity(*shown[1])}}}"
    return LawSteps(
        formula=(
            rf"where $N_0 = {sample}$, the starting amount, and "
            rf"$n = \frac{{{elapsed}}}{{{half_life}}}$, the number of half-lives",
        ),
        substitution=(f"n = {fraction}", f"n = {latex_working(value)}"),
    )


def law_steps(intent: PhysicsIntent, substitutions: tuple[str, ...]) -> LawSteps:
    """The steps ``intent``'s law takes for granted, if it has any."""
    if intent.physics_op == "half_life_remaining":
        return _halves(intent, substitutions)
    return _NONE

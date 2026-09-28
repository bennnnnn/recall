"""Solver-owned formula and substitution rows.

The direct reply reads these fields. A solver stores both rows itself.
"""

from __future__ import annotations

import re
from dataclasses import replace

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.catalog import CATALOG, matching_variant
from app.modules.physics.solvers.common import PhysicsResult
from app.services.solving import SolveServiceError

_DECIMAL_VALUE = re.compile(r"(?<![\d.])([+-]?\d+\.\d+)(?![\d.])")


def display_number(value: float) -> str:
    magnitude = abs(value)
    if magnitude and (magnitude >= 1e6 or magnitude < 1e-4):
        return f"{value:.6g}"
    return str(int(value)) if value.is_integer() else f"{value:g}"


def given_unit_suffix(unit: str | None) -> str:
    if not unit:
        return ""
    if unit.lower() in {"deg", "degree", "degrees", "°"}:
        return r"^\circ"
    return rf"\,\mathrm{{{unit}}}"


def _visible_equation(equation: str) -> str:
    equation = _DECIMAL_VALUE.sub(lambda match: match.group(1).rstrip("0").rstrip("."), equation)
    return equation.replace("*", "·")


def result_symbol_for(intent: PhysicsIntent) -> str | None:
    """The quantity the solver derived, read from the formula spec."""
    spec = CATALOG.get(intent.physics_op or "")
    if spec is None:
        return None
    params = intent.physics_params or {}
    variant = matching_variant(spec, params)
    if variant is not None and variant.result_symbol:
        return variant.result_symbol
    if spec.solve_for:
        missing = [symbol for key, symbol in spec.solve_for if key not in params]
        if len(missing) == 1:
            return missing[0]
    return spec.result_symbol


def attach_recorded_working(result: PhysicsResult, intent: PhysicsIntent) -> PhysicsResult:
    """Clean the formula and substitution rows the solver stored."""
    operation = intent.physics_op or "physics"
    if not result.formulas or not result.substitutions:
        raise SolveServiceError(f"{operation} did not store a formula and a substitution")
    return replace(
        result,
        formulas=tuple(_visible_equation(item) for item in result.formulas),
        substitutions=tuple(_visible_equation(item) for item in result.substitutions),
    )

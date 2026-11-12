"""Solve an expression operation: one catalog law, evaluated for its givens.

The catalog states the law and, for each set of givens, the arithmetic that
answers it (``u = v - at`` for v, a and t). This solver evaluates that
arithmetic in SI and prints the formula and the substitution from the same
expression, so the working is the computation.

A law whose result the question states is solved for the input it asks
(``law_binding.inverse``): W = Fs with W and F given is s = W/F. The answer is put
back into the law, and one that does not give the stated result is refused.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from app.modules.physics.display import conversion_row, si_symbol
from app.modules.physics.expression import evaluate, to_latex
from app.modules.physics.givens import unit_dimension, unit_expression
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solvers.results import PhysicsResult, QuantityResult, solved
from app.modules.physics.solvers.si import (
    params_in_si,
    solves_backwards_in_si,
    stated_on_an_offset_scale,
)
from app.services.law_binding.inverse import (
    forward_expression,
    inverse_of,
    solved_for,
    solved_input,
)
from app.services.law_binding.spec import result_variable
from app.services.solving import SolveServiceError

if TYPE_CHECKING:
    from app.services.law_binding.spec import FormulaSpec, VariableSpec

# An answer put back into its law gives the stated result to this share.
_GIVES_BACK = 1e-6


def solve_expression(intent: PhysicsIntent) -> PhysicsResult:
    from app.modules.physics.catalog import CATALOG, matching_variant

    spec = CATALOG.get(intent.physics_op or "")
    if spec is None or spec.expression is None or spec.binding is None:
        raise SolveServiceError(f"{intent.physics_op} is not an expression operation")
    params = params_in_si(intent)
    unknown = solved_input(spec, params)
    if unknown is not None:
        law, expression, value = _solve_for_input(spec, unknown, params, intent)
        symbol = law.result_symbol
    else:
        law = spec
        variant = matching_variant(spec, params)
        expression = spec.expression
        symbol = spec.result_symbol
        if variant is not None:
            expression = variant.expression or expression
            symbol = variant.result_symbol or symbol
        value = _evaluated(spec, expression, params)
    binding = law.binding
    if binding is None:  # pragma: no cover - a law solved for an input keeps a binding
        raise SolveServiceError(f"{spec.id} has no binding")
    detail = None
    if binding.negative_detail and value < 0:
        value = abs(value)
        detail = binding.negative_detail
    elif binding.nonnegative and value < 0:
        raise SolveServiceError(f"{spec.id} gives a negative {symbol} for these givens")
    if binding.at_most is not None and value > binding.at_most:
        raise SolveServiceError(f"{spec.id} gives {symbol} above {binding.at_most:g}")
    symbols = {variable.name: variable.symbol for variable in law.variables}
    formula = f"{symbol} = {to_latex(expression, symbols)}"
    substitution = f"{symbol} = {to_latex(expression, symbols, params)}"
    difference = (
        _stated_temperature_change(intent, params)
        if spec.id == "heat_energy" and unknown is None
        else None
    )
    result_unit = binding.result[0]
    unit = binding.shown_unit or ("" if result_unit == "dimensionless" else si_symbol(result_unit))
    # A law that prints an SI-sized unit of its own ("photons/s", "Bq") is not
    # answered in a like given's unit: a photon rate is not the hertz of a
    # frequency given beside it.
    own = unit_dimension(unit_expression(unit) or "") if binding.shown_unit else None
    own_unit = own is not None and own[1] == 1.0 and own[2] == 0.0
    shown = None if own_unit else _in_the_givens_unit(law, intent, result_unit, value)
    if shown is None or shown[1] == unit or math.isclose(shown[0], value):
        # No step to show: the same unit, or only its spelling ("J/kg°C" for J/(kg·K)).
        rows: tuple[str, ...] = (substitution,)
    else:
        # The arithmetic is in SI; the step to the givens' unit is part of the working.
        rows = (substitution, conversion_row(symbol, (value, unit), shown))
    return solved(
        QuantityResult("", *(shown or (value, unit)), detail=detail),
        answer=substitution,
        formulas=((difference, formula) if difference else (formula,)),
        substitutions=rows,
    )


def drawn_values(
    intent: PhysicsIntent, params: dict[str, float], value: float, unit: str
) -> tuple[dict[str, float], float]:
    """The law's inputs and its result, in SI, as its picture draws them.

    A law solved for one of its inputs is drawn as it is when its result is asked: the
    answer is that input, and the stated result is the law's value.
    """
    from app.modules.physics.catalog import CATALOG
    from app.modules.physics.solvers.si import to_si

    spec = CATALOG.get(intent.physics_op or "")
    unknown = solved_input(spec, params) if spec is not None else None
    stated = result_variable(spec) if spec is not None else None
    if unknown is None or stated is None:
        return params, value
    try:
        answer = to_si(value, unit, expected_key=unknown.name)
    except SolveServiceError:
        return params, value
    inputs = {name: given for name, given in params.items() if name != stated.name}
    return {**inputs, unknown.name: answer}, params[stated.name]


def _evaluated(spec: FormulaSpec, expression: str, params: dict[str, float]) -> float:
    """``expression`` at ``params``, where the law holds: each of its ``requires`` comes
    out positive, and the answer is finite."""
    try:
        value = evaluate(expression, params)
        holds = _holds(spec, params)
    except (KeyError, ValueError, OverflowError) as exc:
        raise SolveServiceError(f"{spec.id} has no real answer for these givens") from exc
    if not holds:
        raise SolveServiceError(f"{spec.id} does not hold for these givens")
    if not math.isfinite(value):
        raise SolveServiceError(f"{spec.id} answer is not finite")
    return value


def _holds(spec: FormulaSpec, values: dict[str, float]) -> bool:
    requires = spec.binding.requires if spec.binding is not None else ()
    return all(evaluate(condition, values) > 0 for condition in requires)


def _solve_for_input(
    spec: FormulaSpec, unknown: VariableSpec, params: dict[str, float], intent: PhysicsIntent
) -> tuple[FormulaSpec, str, float]:
    """The law solved for ``unknown`` from its stated result: the law as filled, the
    rearranged arithmetic, and the answer, which put back into the law gives the result."""
    law = solved_for(spec, unknown.name)
    stated = result_variable(spec)
    if law is None or stated is None:
        raise SolveServiceError(f"{spec.id} is not solved for {unknown.name}")
    # The stated result reaches the law in SI: its arithmetic must give the result in SI too,
    # and a reading on an offset scale is no size to solve from.
    if not solves_backwards_in_si(spec) or stated_on_an_offset_scale(intent, stated.name):
        raise SolveServiceError(f"{spec.id} gives {stated.name} in a unit not solved backwards")
    givens = {name: value for name, value in params.items() if name != stated.name}
    # The law's form is chosen from its givens, with the asked input among them.
    forward = forward_expression(spec, {**givens, unknown.name: 1.0})
    inverse = inverse_of(spec, forward, unknown.name) if forward else None
    if forward is None or inverse is None:
        raise SolveServiceError(f"{spec.id} has no one arithmetic for {unknown.name}")
    value = _evaluated(law, inverse, params)
    whole = {**givens, unknown.name: value}
    try:
        gives = evaluate(forward, whole)
        holds = _holds(spec, whole)
    except (KeyError, ValueError, OverflowError) as exc:
        raise SolveServiceError(f"{spec.id} has no real answer for these givens") from exc
    if not holds or not math.isclose(gives, params[stated.name], rel_tol=_GIVES_BACK):
        raise SolveServiceError(f"{spec.id} solved for {unknown.name} misses its stated result")
    return law, inverse, value


def _stated_temperature_change(intent: PhysicsIntent, params: dict[str, float]) -> str | None:
    """The ΔT row when a question gave two readings: ``80 - 20 = 60``."""
    if "temp_initial" not in params or "temp_final" not in params:
        return None
    change = params["temp_final"] - params["temp_initial"]
    raw = intent.physics_params or {}
    units = intent.physics_units or {}
    # Readings in one unit of kelvin's size (°C or K) subtract as written; a
    # Fahrenheit difference is not the kelvins the substitution uses.
    reading = unit_dimension(unit_expression(units.get("temp_initial", "")) or "")
    same_scale = (
        units.get("temp_initial") == units.get("temp_final")
        and reading is not None
        and math.isclose(reading[1], 1.0)
    )
    first = raw["temp_initial"] if same_scale else params["temp_initial"]
    second = raw["temp_final"] if same_scale else params["temp_final"]
    return rf"\Delta T = T_2 - T_1 = {second:g} - {first:g} = {change:g}"


def _in_the_givens_unit(
    spec: FormulaSpec, intent: PhysicsIntent, result_unit: str, value: float
) -> tuple[float, str] | None:
    """The result in the one unit its like givens share: 4 µF and 6 µF give µF.

    A textbook answers two capacitances in µF in µF, and a radius in cm with a
    focal length in cm. Givens of the result's kind in different units, or
    none, leave the answer in SI. Temperatures in °C give a temperature in
    °C, and a change of temperature stays a change: a rise of 10 K is a rise of 10 °C.
    """
    target = unit_dimension(result_unit)
    if target is None:
        return None
    units = intent.physics_units or {}
    alike = {
        variable.name: units[variable.name]
        for variable in spec.variables
        if variable.dimension is not None
        and variable.name in units
        and (kind := unit_dimension(variable.dimension)) is not None
        and kind[0] == target[0]
    }
    if len(set(alike.values())) != 1:
        return None
    unit = next(iter(alike.values()))
    expression = unit_expression(unit)
    reading = unit_dimension(expression) if expression else None
    if reading is None or reading[0] != target[0]:
        return None
    difference = any(name.startswith("delta_") for name in alike)
    offset = 0.0 if difference else reading[2]
    return (value - offset) / reading[1], unit

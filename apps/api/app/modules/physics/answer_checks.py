"""Checks on a solved result against its question: the asked quantity and the asked unit."""

from __future__ import annotations

import math
import re
from dataclasses import replace

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.ask import result_dimension, result_reading
from app.modules.physics.givens import unit_dimension, unit_expression
from app.modules.physics.solver import PhysicsResult
from app.modules.physics.solvers.common import QuantityResult


def _in_the_asked_unit(intent: PhysicsIntent, result: PhysicsResult) -> PhysicsResult:
    """Each result of the asked unit's kind, shown in that unit ("in kWh")."""
    expression = unit_expression(intent.asked_unit) if intent.asked_unit else None
    target = unit_dimension(expression) if expression else None
    if target is None or intent.asked_unit is None:
        return result
    quantities: list[QuantityResult] = []
    # The unit each kept result was solved in, to tell a restatement from a twin.
    solved_in: list[str] = []
    for item in result.quantities:
        reading = result_reading(item.unit)
        if reading is None or reading[0] != target[0]:
            quantities.append(item)
            solved_in.append(item.unit)
            continue
        si = item.value * reading[1] + reading[2]
        # A note that only restated the value in this unit ("2.48 eV") is now the value.
        restated = item.detail is not None and re.fullmatch(
            rf"\s*-?[\d.]+(?:[eE][-+]?\d+)?\s*{re.escape(intent.asked_unit)}\s*", item.detail
        )
        shown = replace(
            item,
            value=(si - target[2]) / target[1],
            unit=intent.asked_unit,
            detail=None if restated else item.detail,
        )
        # One result given in two units ("J (eV)") is one result once both are
        # in eV. Two results that only share a value (45° components) stay two.
        if not any(
            unit != item.unit
            and other.symbol == shown.symbol
            and other.detail == shown.detail
            and other.unit == shown.unit
            and math.isclose(other.value, shown.value)
            for other, unit in zip(quantities, solved_in, strict=True)
        ):
            quantities.append(shown)
            solved_in.append(item.unit)
    return replace(result, quantities=tuple(quantities))


# A gas stated in litres or atmospheres is a chemistry class's question, and its answer reads
# in those units too: 49.2 L, not 0.0492 m³. A gas stated in m³ or Pa keeps SI.
_CHEMISTRY_GAS = frozenset({"atm", "mmhg", "torr", "l", "ml", "liter", "liters", "litre", "litres"})
_SI_GAS = frozenset({"m^3", "m³", "pa", "kpa", "mpa", "cm^3", "cm³"})
_CHEMISTRY_RESULTS = {"m^3": "L", "m³": "L", "Pa": "atm"}


def _in_context_units(intent: PhysicsIntent, result: PhysicsResult) -> PhysicsResult:
    """A volume or pressure left in SI, shown in L or atm when the givens are chemistry's."""
    if intent.asked_unit is not None:
        return result
    result = _per_time_of_givens(intent, result)
    written = {unit.lower() for unit in (intent.physics_units or {}).values()}
    if not written & _CHEMISTRY_GAS or written & _SI_GAS:
        return result
    for unit in {
        _CHEMISTRY_RESULTS[item.unit]
        for item in result.quantities
        if item.unit in _CHEMISTRY_RESULTS
    }:
        target = intent.model_copy(update={"asked_unit": unit})
        converted = _in_the_asked_unit(target, result)
        result = replace(
            result,
            quantities=tuple(
                new
                if old.unit in _CHEMISTRY_RESULTS and _CHEMISTRY_RESULTS[old.unit] == unit
                else old
                for old, new in zip(result.quantities, converted.quantities, strict=True)
            ),
        )
    return result


# A rate from a half-life in years is per year: 1.21e-4 1/yr, not 3.83e-12 1/s.
_SHORT_TIME = {
    "years": "yr",
    "year": "yr",
    "yr": "yr",
    "minutes": "min",
    "minute": "min",
    "min": "min",
    "hours": "h",
    "hour": "h",
    "h": "h",
    "hr": "h",
    "days": "day",
    "day": "day",
}
_TIME = "[time]^1"


def _per_time_of_givens(intent: PhysicsIntent, result: PhysicsResult) -> PhysicsResult:
    """A per-second result, per the one time unit every time given shares."""
    if intent.asked_unit is not None:
        return result
    spellings = {
        unit
        for unit in (intent.physics_units or {}).values()
        if (reading := unit_dimension(unit_expression(unit) or "")) and reading[0] == _TIME
    }
    short = {_SHORT_TIME.get(unit.lower()) for unit in spellings}
    if len(spellings) == 0 or len(short) != 1 or None in short:
        return result
    unit = short.pop()
    reading = unit_dimension(unit_expression(next(iter(spellings))) or "")
    if unit is None or reading is None:
        return result
    return replace(
        result,
        quantities=tuple(
            replace(item, value=item.value * reading[1], unit=f"1/{unit}")
            if item.unit == "1/s"
            else item
            for item in result.quantities
        ),
    )


def _answers_the_question(intent: PhysicsIntent, result: PhysicsResult) -> bool:
    """Every quantity the question asked for is among the results.

    A solver may answer more (an Atwood pair gives acceleration and tension),
    never something else. A result unit that cannot be read leaves the decision
    to the solver.
    """
    if not intent.asked:
        return True
    produced = [result_dimension(item.unit) for item in result.quantities]
    if not produced or None in produced:
        return True
    return set(intent.asked) <= set(produced)

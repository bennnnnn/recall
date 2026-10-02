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

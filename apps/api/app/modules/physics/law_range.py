"""Whether a filled law's values are inside its range (``Binding.requires``).

An expression law checks its range as it solves (``solvers/relation.solve_expression``).
A law a hand-written solver answers is checked here, by the readers that fill it from
a question (the binder and the chain), since its solver answers outside the range in
its own way: a virtual image's size, with no sign to chain on; a launch from level
ground at 0°, which never flies.

An input the question did not give counts as zero, as the solvers read it: a launch with
no stated height starts on the ground.
"""

from __future__ import annotations

from app.modules.physics.expression import evaluate
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solvers.si import params_in_si
from app.services.law_binding.spec import FormulaSpec


def holds_its_range(spec: FormulaSpec, intent: PhysicsIntent) -> bool:
    """Every ``requires`` expression is positive for these values, or there is none."""
    binding = spec.binding
    if binding is None or not binding.requires:
        return True
    given = params_in_si(intent)
    values = {variable.name: given.get(variable.name, 0.0) for variable in spec.variables}
    try:
        return all(evaluate(condition, values) > 0 for condition in binding.requires)
    except (KeyError, ValueError, OverflowError):
        return False

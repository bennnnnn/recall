"""Why physics declined a question whose values no real case has, for the prompt's note.

The readers decline a law filled with a value no such quantity takes, and the solve a result
outside its kind's range (``law_binding.domains``). Told only that nothing verified, the
model answered "A 10 V battery is connected across a -5 Ω resistor. What current flows?" with
-2 A and no word about the resistor (live round, 2026-11-14). The reason is read here from
the law the readers filled, by the rule that declined it; a decline for any other reason has
none, and a negative velocity or charge breaks no rule.
"""

from __future__ import annotations

from collections.abc import Iterator

from app.modules.physics.binding import bind_physics_intent, bind_solved_for
from app.modules.physics.catalog import formula_spec
from app.modules.physics.display import GIVEN_FIGURES, plain_quantity
from app.modules.physics.extract import extract_physics_intent, read_physics_request
from app.modules.physics.glossary import given_meaning
from app.modules.physics.registry import PHYSICS_EXTRACTORS
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solver import solve_physics
from app.modules.physics.solvers.si import params_in_si
from app.services.law_binding.domains import input_rule, outside_domain
from app.services.law_binding.spec import variable_for
from app.services.solving import ImpossibleProblemError, SolveServiceError


def stated_out_of_range(text: str) -> str | None:
    """A value the question states that no such quantity takes, as a law that reads the
    question fills it: "A resistance cannot be zero or negative, and the question gives
    -5 Ω." None when every law that reads it takes its values."""
    request = read_physics_request(text)
    if request is None:
        return None
    for intent in _readings(request.text):
        reason = _stated_reason(intent)
        if reason is not None:
            return reason
    return None


def result_out_of_range(text: str) -> str | None:
    """The question's law, filled as it was read, gives a result no such quantity takes:
    "a force of -10 N gives 2 m/s²" is a mass of -5 kg (``solver.solve_physics``). The signs
    are the reader's, so this is a reason to check them, not proof the question is wrong."""
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    try:
        solve_physics(intent)
    except ImpossibleProblemError as found:
        return str(found)
    except SolveServiceError:
        return None
    return None


def _readings(text: str) -> Iterator[PhysicsIntent]:
    """The question as the readers fill it before any check refuses it: the first extractor
    that reads it, then the binder, forward and solved for an input (``extract``)."""
    for extractor in PHYSICS_EXTRACTORS:
        intent = extractor(text)
        if intent is not None:
            yield intent
            break
    for bind in (bind_physics_intent, bind_solved_for):
        intent = bind(text)
        if intent is not None:
            yield intent


def _stated_reason(intent: PhysicsIntent) -> str | None:
    """The rule the law's first input outside its range breaks, and the value stated."""
    spec = formula_spec(intent.physics_op or "")
    if spec is None:
        return None
    try:
        values = params_in_si(intent)
    except SolveServiceError:
        return None
    name = outside_domain(spec, values)
    variable = None if name is None else variable_for(spec, name)
    if name is None or variable is None:
        return None
    rule = input_rule(variable, values[name], given_meaning(spec.id, spec.kind, name))
    if rule is None:
        return None
    params, units = intent.physics_params or {}, intent.physics_units or {}
    stated = plain_quantity(params[name], units.get(name, ""), GIVEN_FIGURES)
    return f"{rule[:1].upper()}{rule[1:]}, and the question gives {stated}."

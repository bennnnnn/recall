"""What rules a filled law out before it is solved, read from the question's own words.

Each is a question the law does not describe, whichever reader filled it:

- a stated value no such quantity takes (``law_binding.domains``): "a -5 Ω resistor" was
  verified as -2 A (audit 2026-11-13);
- a value named as a quantity none of the law's inputs of its kind is
  (``law_binding.labels``): the SUVAT reader read "an average speed of 12 m/s over 30 s" as
  a final speed, 180 m for 360, and the pendulum reader a bob's amplitude as its length.
  The binder already holds its fills to this; a chained law is held to it by the binder.
  A stated change ("rises by 20 °C") is left to the extractors, which work it into the
  ends they bind;
- a value the words put where the body gets to, filling where it starts: "how long to first
  reach a height of 15 m" was a launch from 15 m, 4.72 s for 0.99 s (audit 2026-11-07);
- air resistance said to act on a motion under gravity, whose laws leave it out: "dropped
  from 20 m and air resistance is significant" was 19.8 m/s, verified;
- a speed said to be constant answered by a law of a changing speed: "a constant speed of
  20 m/s for 5 s and covers 200 m" was 60 m/s, verified.
"""

from __future__ import annotations

import re

from app.modules.physics.givens import PHYSICS_UNITS
from app.modules.physics.motion import read_motion
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solvers.si import params_in_si
from app.services.law_binding.domains import outside_domain
from app.services.law_binding.fit import (
    given_kind,
    given_labels,
    read_givens,
    value_end,
    variable_kind,
)
from app.services.law_binding.labels import CHANGE, holds
from app.services.law_binding.roles import variable_role
from app.services.law_binding.spec import FormulaSpec, result_variable, variable_for
from app.services.law_binding.words import words_before
from app.services.solving import SolveServiceError

# Where the body gets to: "first reach a height of 15 m", "rises to 20 m", "climbs to".
_REACHED = re.compile(
    r"\b(?:reach(?:es|ed|ing)?|(?:rises?|rose|climbs?|climbed|gets?|goes|went)\s+(?:up\s+)?to)"
    r"\s+(?:(?:a|an|the)\s+)?(?:(?:height|altitude|level|point)\s+(?:of\s+)?)?$"
)
# Air resistance said to act: "air resistance is significant", "with air resistance",
# "taking air resistance into account". Named in a question about it ("why does air
# resistance matter?") or set aside ("ignore air resistance"), it is said to do nothing.
_AIR = r"(?:air\s+(?:resistance|friction|drag)|drag)"
_AIR_RESISTANCE_ACTS = re.compile(
    rf"\b{_AIR}\s+(?:is|are|was)\s+(?:not\s+(?:negligible|ignored|neglected)|significant"
    r"|important|present|included|large|considerable|appreciable)\b"
    rf"|\b(?:with|including|considering|taking\s+into\s+account|accounting\s+for|due\s+to)"
    rf"\s+(?:the\s+)?{_AIR}\b"
)
# Laws of a motion under gravity alone.
_MOTION_KINDS = frozenset({"kinematics", "projectile", "suvat", "energy"})
_HOLDS_ITS_SPEED = re.compile(
    r"\b(?:constant|steady|uniform|unchanging|unchanged)\s+(?:speed|velocity)\b"
)


def refuses(spec: FormulaSpec, intent: PhysicsIntent, text: str, *, chained: bool) -> bool:
    """``spec`` filled as ``intent`` does not describe the question ``text``."""
    lower = text.lower()
    return (
        _outside_its_domain(spec, intent)
        or (not chained and _names_another_quantity(spec, text))
        or _starts_where_it_gets_to(spec, intent, text)
        or (spec.kind in _MOTION_KINDS and _uses_gravity(spec) and air_resistance_acts(lower))
        or (spec.kind == "suvat" and holds_its_speed(lower))
    )


def _outside_its_domain(spec: FormulaSpec, intent: PhysicsIntent) -> bool:
    try:
        values = params_in_si(intent)
    except SolveServiceError:
        # A unit the solver cannot read is the solver's to refuse.
        return False
    return outside_domain(spec, values) is not None


def _names_another_quantity(spec: FormulaSpec, text: str) -> bool:
    givens = read_givens(text, PHYSICS_UNITS)
    stated = result_variable(spec)
    inputs = [v for v in (*spec.variables, *((stated,) if stated else ())) if v.visible]
    for given, label in zip(givens, given_labels(text.lower(), givens), strict=True):
        if label is None or label == CHANGE:
            continue
        kind = given_kind(given, PHYSICS_UNITS)
        alike = [variable for variable in inputs if variable_kind(variable) == kind]
        if alike and not any(holds(variable, label) for variable in alike):
            return True
    return False


def _starts_where_it_gets_to(spec: FormulaSpec, intent: PhysicsIntent, text: str) -> bool:
    """An input at the start (h₀, v₀, u: ``roles``) holds a value said as where it gets to."""
    starts = {
        value
        for name, value in (intent.physics_params or {}).items()
        if (variable := variable_for(spec, name)) is not None
        and variable_role(variable) == "initial"
    }
    lower = text.lower()
    previous = 0
    for given in read_givens(text, PHYSICS_UNITS):
        if given.value in starts and _REACHED.search(words_before(lower, previous, given.start)):
            return True
        previous = value_end(lower, given)
    return False


def _uses_gravity(spec: FormulaSpec) -> bool:
    return any(variable.name == "g" for variable in spec.variables)


def air_resistance_acts(lower: str) -> bool:
    """The question says air resistance acts on the motion."""
    return _AIR_RESISTANCE_ACTS.search(lower) is not None


def holds_its_speed(lower: str) -> bool:
    """The question says the speed is constant and says nothing that changes it."""
    return _HOLDS_ITS_SPEED.search(lower) is not None and not read_motion(lower).changes_speed

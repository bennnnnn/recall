"""A follow-up that changes what is done to a component, not the component itself.

"Find the resistance" of a resistor with 12 V and 2 A, then "what if the voltage doubled?":
the resistor is still 6 Ω, so the current doubles to 4 A. Re-solving the problem with the
voltage doubled and the current kept made the resistor 12 Ω, so that line declined, and the
model it fell to opened its reply on a guessed "**24 Ω**" (2026-11-07).

So the property the problem found is held at its verified value, the changed given takes its
new value, and the problem's other given is asked instead: "A resistance of 6 Ω and a
voltage of 24 V. Find the current." It is offered only when the solver verifies that
wording and its answer is the other given scaled by the same factor: the law itself says
the two change together, no wording is trusted alone.

Only a component's own constant is held: a resistor's resistance, a capacitor's
capacitance, a spring's constant. A component whose resistance changes with use (a lamp,
an LED, a thermistor) holds none. A density or a specific heat belongs to a material, and
"twice the mass" of it may be more of the material or a different one: those decline.
"""

from __future__ import annotations

import math
import re

from app.modules.physics.catalog import CATALOG, formula_spec
from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.givens import PHYSICS_UNITS
from app.modules.physics.glossary import given_meaning
from app.modules.physics.verified_answers import answers, plain_number, results
from app.services.law_binding.fit import read_givens
from app.services.law_binding.givens import Given
from app.services.law_binding.spec import FormulaSpec
from app.services.law_binding.units import unit_dimension

# The constants of a component, by the name its law asks them with.
_COMPONENT_CONSTANTS = frozenset({"resistance", "capacitance", "spring constant"})
_TOLERANCE = 1e-6
# Components whose resistance changes with what drives them: a filament heats, an LED or a
# diode conducts exponentially, a thermistor or an LDR is made to change. Ohm's law at a
# held resistance gave a verified "4 A" for a lamp at twice the voltage. A rubber band does
# not keep a spring constant either.
_NOT_CONSTANT = re.compile(
    r"\b(?:lamps?|bulbs?|filaments?|light|leds?|diodes?|thermistors?|ldrs?|"
    r"light[- ]dependent|motors?|rubber|elastic band)\b",
    re.IGNORECASE,
)


def kept_property_problem(prior: str, rewritten: str) -> str | None:
    """The follow-up's problem with the component's constant kept, or None.

    ``rewritten`` is ``prior`` with the one given the line changed at its new value.
    """
    intent = extract_physics_intent(prior)
    operation = intent.physics_op if intent is not None else None
    spec = formula_spec(operation) if operation is not None else None
    if spec is None or spec.binding is None or not spec.binding.asks:
        return None
    constant = spec.binding.asks[0]
    if _NOT_CONSTANT.search(prior):
        return None
    found = results(prior)
    if constant not in _COMPONENT_CONSTANTS or not found or len(found) != 1:
        return None
    pair = _changed_and_other(prior, rewritten)
    if pair is None:
        return None
    (before, after), other = pair
    if not before.si or not after.si or not other.si:
        return None
    changed_name = _input_name(spec, before.dimension)
    asked_name = _input_name(spec, other.dimension)
    if changed_name is None or asked_name is None or changed_name == asked_name:
        return None
    cue = _object_word(prior, asked_name)
    held = f"{_a(constant)} {constant} of {_written(found[0])}"
    if cue is not None:
        held = f"{_a(cue)} {cue} with {held}"
    changed = f"{_a(changed_name)} {changed_name} of {_written(after)}"
    text = f"{held[0].upper()}{held[1:]} and {changed}. Find the {asked_name}."
    return text if _scales_with(text, other, after.si / before.si) else None


def _changed_and_other(prior: str, rewritten: str) -> tuple[tuple[Given, Given], Given] | None:
    """The given the line changed (before, after) and the problem's one other given."""
    earlier = _dimensioned(prior)
    later = _dimensioned(rewritten)
    if len(earlier) != 2 or len(later) != 2:
        return None
    changed = [
        (old, new)
        for old, new in zip(earlier, later, strict=True)
        if old.dimension == new.dimension and not math.isclose(old.value, new.value)
    ]
    if len(changed) != 1:
        return None
    before, after = changed[0]
    other = next(g for g in earlier if g is not before)
    if other.dimension == before.dimension:
        return None
    return (before, after), other


def _dimensioned(text: str) -> list[Given]:
    return [g for g in read_givens(text, PHYSICS_UNITS) if g.dimension]


def _input_name(spec: FormulaSpec, dimension: str | None) -> str | None:
    """The law's word for its input of this dimension: "voltage", "extension"."""
    names = []
    for variable in spec.variables:
        reading = unit_dimension(variable.dimension) if variable.dimension else None
        if reading is not None and reading[0] == dimension:
            names.append(given_meaning(spec.id, spec.kind, variable.symbol))
    return names[0] if len(names) == 1 else None


def _object_word(prior: str, asked: str) -> str | None:
    """The object a law that answers ``asked`` needs named ("capacitor"), when the problem
    names it; None when no such law needs one."""
    for spec in CATALOG.values():
        binding = spec.binding
        if binding is None or asked not in binding.asks:
            continue
        for cue in binding.cues:
            if re.search(rf"\b{re.escape(cue)}\b", prior, re.IGNORECASE):
                return cue
    return None


def _a(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def _written(given: Given) -> str:
    return f"{given.value:g} {given.unit}".strip()


def _scales_with(text: str, other: Given, factor: float) -> bool:
    """The solver answers ``text`` with the other given scaled by ``factor``: the law holds
    the constant fixed only while its two inputs change together."""
    found = answers(text)
    if not found or len(found) != 1 or other.si is None:
        return False
    values = [g for g in read_givens(plain_number(found[0][0]), PHYSICS_UNITS) if g.dimension]
    if len(values) != 1 or values[0].dimension != other.dimension or values[0].si is None:
        return False
    return math.isclose(values[0].si, other.si * factor, rel_tol=_TOLERANCE)

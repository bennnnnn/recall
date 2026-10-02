"""Read a question straight into a catalog operation, from its givens and its ask.

The extractors are written for the phrasings they know. Many questions just
state a law's inputs and ask for its result in words the catalog can list:
"accelerates from 10 m/s to 30 m/s in 5 s. Find its acceleration." The binder
reads every stated value with its dimension (``givens``) and the asked clause
(``ask``), then fills an operation whose ``Binding`` names that ask:

- every stated value fills one input of its dimension. Two inputs of one
  dimension are told apart by the word just before the value ("from", "to",
  "initial", "reaches") or just after it ("on the primary"), or filled in
  order (largest first where the law says so);
- a value the words mark as the result itself ("reaches 18 m/s" when the
  final speed is asked) means this is not the operation;
- unstated inputs come from phrases ("from rest" is u = 0) or settings (g,
  the named planet's mass);
- the filled inputs must be exactly a set the solver answers from.

Anything short of one operation with one way to fill it declines: two
operations fit, a value has no input, an input could take either of two
values, or the ask names nothing the catalog lists. It runs after the
extractors, so it only answers questions they declined.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.ask import ask_clause, asked_dimensions, asked_unit
from app.modules.physics.binding_values import fallback_value, largest_first, si_unit, value_end
from app.modules.physics.binding_words import (
    ask_strength,
    choose,
    implied_value,
    last_said,
    word_pattern,
    words_after,
    words_before,
)
from app.modules.physics.catalog import CATALOG
from app.modules.physics.catalog.spec import FormulaSpec, VariableSpec
from app.modules.physics.givens import ANGLE, Given, scan_givens, unit_dimension, unit_expression

_DIMENSIONLESS = "dimensionless"
_ANGULAR = "angular "
# "from 0 to 27 m/s": a bare number shares the unit of the value it runs to.
_RANGE_LINK = re.compile(r"\s*(?:to|-|\u2013|and|or)\s*", re.IGNORECASE)
# Only a conjunction between two values: they share the words before the first.
_LIST_LINK = re.compile(r"\s*(?:,|and|,\s*and)\s*", re.IGNORECASE)
# A speed written as a fraction of c, the c on the number: "0.8c".
_FRACTION_OF_C = re.compile(r"\dc(?![a-z0-9])")
# A school question states a handful of values; a paste full of numbers is
# not one law's inputs, and reading it all would cost every chat turn.
_MAX_GIVENS = 16
# A second request in the same message ("... and tell me a joke") is not a
# question the verified answer finishes.
_SECOND_REQUEST = re.compile(
    r"\b(?:and|also|then)\s+(?:also\s+)?"
    r"(?:tell|explain|show|write|give|convert|calculate|compute|solve|draw|plot|describe)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class _Fit:
    spec: FormulaSpec
    params: dict[str, float]
    units: dict[str, str]
    strength: int


def bind_physics_intent(text: str) -> PhysicsIntent | None:
    """The one catalog operation this question states and asks for, or None.

    The word checks run first, so text that names no operation's ask costs a
    few regex searches and never reads units. Detection calls this on every
    chat turn.
    """
    clause = ask_clause(text)
    if clause is None or _SECOND_REQUEST.search(text):
        return None
    lower = text.lower()
    # "0.8c" is a speed of light: the phrase relativity's cues are written as.
    cue_text = f"{lower} speed of light" if _FRACTION_OF_C.search(lower) else lower
    asked_clause = clause.lower()
    named = [
        (spec, strength)
        for spec in _bindable()
        if spec.binding is not None
        and (
            not spec.binding.cues
            or any(word_pattern(cue).search(cue_text) for cue in spec.binding.cues)
        )
        and not any(word_pattern(word).search(lower) for word in spec.binding.excludes)
        and (strength := ask_strength(asked_clause, spec.binding.asks, spec.binding.result))
    ]
    if not named:
        return None
    givens = _givens(text)
    if len(givens) > _MAX_GIVENS:
        return None
    asked = set(asked_dimensions(text))
    asked_from = lower.rfind(asked_clause)
    unit = asked_unit(text)
    asked_in = _dimension(unit_expression(unit) or "") if unit else None
    fits = [
        fit
        for spec, strength in named
        if (fit := _fit(spec, strength, text, lower, givens, asked, asked_in, asked_from))
        is not None
    ]
    if not fits:
        return None
    strongest = max(fit.strength for fit in fits)
    top = [fit for fit in fits if fit.strength == strongest]
    if len(top) != 1:
        return None
    fit = top[0]
    try:
        return PhysicsIntent(
            kind=fit.spec.kind,  # type: ignore[arg-type]
            physics_op=fit.spec.id,
            physics_params=fit.params,
            physics_units=fit.units,
        )
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _bindable() -> tuple[FormulaSpec, ...]:
    return tuple(spec for spec in CATALOG.values() if spec.binding is not None)


def _givens(text: str) -> list[Given]:
    """Stated values, a bare number taking the unit of the range it starts."""
    givens = scan_givens(text)
    read: list[Given] = []
    for index, given in enumerate(givens):
        following = givens[index + 1] if index + 1 < len(givens) else None
        if (
            given.dimension is None
            and not given.unit
            and following is not None
            and following.dimension is not None
            and _RANGE_LINK.fullmatch(text, given.end, following.start)
        ):
            reading = unit_dimension(unit_expression(following.unit) or "")
            if reading is not None:
                dimension, scale, offset = reading
                si = given.value * scale + offset
                given = Given(given.start, given.end, given.value, following.unit, dimension, si)
        read.append(given)
    return read


@lru_cache(maxsize=256)
def _dimension(expression: str) -> str | None:
    if not expression:
        return None
    reading = unit_dimension(expression)
    return None if reading is None else reading[0]


def _variable_kind(variable: VariableSpec) -> str | None:
    if variable.name.startswith("angle"):
        return ANGLE
    if variable.dimensionless:
        return _DIMENSIONLESS
    kind = _dimension(variable.dimension or "")
    return _ANGULAR + kind if kind and _angular(variable.dimension or "") else kind


def _given_dimension(given: Given) -> str | None:
    if given.dimension is not None:
        return given.dimension
    return _DIMENSIONLESS if not given.unit else None


def _given_kind(given: Given) -> str | None:
    """The input kind a value can fill: its dimension, with angular rates apart.

    A frequency in Hz and an angular velocity in rad/s share a dimension, but
    50 Hz is not 50 rad/s: each fills only its own kind of input.
    """
    dimension = _given_dimension(given)
    if dimension is not None and _angular(unit_expression(given.unit) or ""):
        return _ANGULAR + dimension
    return dimension


def _angular(expression: str) -> bool:
    return expression.startswith(("radian /", "revolution /"))


def _other_sense(
    lower: str,
    asks: tuple[str, ...],
    givens: list[Given],
    produced: set[str | None],
    asked_from: int,
) -> bool:
    """The asked word labels a value of another kind: "my weight is 70 kg".

    That question uses the word in its everyday sense (a mass), and the law's
    sense (a force) would answer something it did not ask.
    """
    for given in givens:
        kind = _given_dimension(given)
        if kind is None or kind in produced:
            continue
        before = lower[max(0, given.start - 40) : given.start]
        # In the asked clause "of" is belonging, not a value: "find the
        # internal energy of 2 mol of gas" asks for the energy of the gas.
        links = r"(?:=|is|:|was)?" if given.start >= asked_from else r"(?:of|=|is|:|was)?"
        for phrase in asks:
            label = re.search(rf"{re.escape(phrase)}\s*{links}\s*$", before)
            if label is not None:
                return True
    return False


def _fit(
    spec: FormulaSpec,
    strength: int,
    text: str,
    lower: str,
    givens: list[Given],
    asked: set[str],
    asked_in: str | None,
    asked_from: int,
) -> _Fit | None:
    binding = spec.binding
    if binding is None:
        return None
    produced = {_dimension(unit) for unit in binding.result}
    if (asked and not asked <= produced) or (asked_in is not None and asked_in not in produced):
        return None
    if _other_sense(lower, binding.asks, givens, produced, asked_from):
        return None
    variables = [variable for variable in spec.variables if variable.visible]
    params: dict[str, float] = {}
    units: dict[str, str] = {}
    # What the words state comes first: a car that starts "from rest" has u = 0,
    # so its one stated speed is the final one. Hidden classifier inputs are
    # words too: "string" sets the mode factor of a resonance.
    for variable in spec.variables:
        implied = implied_value(variable, lower)
        if implied is not None:
            params[variable.name] = implied
            units[variable.name] = si_unit(variable)
    listed = word_pattern("respectively").search(lower) is not None
    previous = 0
    earlier = ""
    for index, given in enumerate(givens):
        kind = _given_kind(given)
        options = [
            variable
            for variable in variables
            if variable.name not in params and kind is not None and _variable_kind(variable) == kind
        ]
        if not options:
            return None
        before = words_before(lower, previous, given.start)
        # "at 100 kPa and 300 K": the words before a list name every value in it.
        if _LIST_LINK.fullmatch(before):
            before = earlier
        earlier = before
        following = givens[index + 1].start if index + 1 < len(givens) else len(lower)
        after = words_after(lower, given.end, following)
        choice = choose(
            options, before, after, binding, _given_dimension(given) in produced, listed=listed
        )
        if choice is None:
            return None
        negative = last_said(before, choice.negating) >= 0
        params[choice.name] = -given.value if negative else given.value
        units[choice.name] = given.unit
        previous = value_end(lower, given)
    largest_first(params, units, binding.descending)
    for variable in variables:
        if variable.name in params:
            continue
        value = fallback_value(variable, text, lower)
        if value is not None:
            params[variable.name] = value
            units[variable.name] = si_unit(variable)
    if frozenset(params) not in binding.inputs:
        return None
    return _Fit(spec, params, units, strength)

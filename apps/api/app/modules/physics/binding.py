"""Read a question straight into a catalog operation, from its givens and its ask.

The extractors are written for the phrasings they know. Many questions just
state a law's inputs and ask for its result in words the catalog can list:
"accelerates from 10 m/s to 30 m/s in 5 s. Find its acceleration." The binder
reads every stated value with its dimension (``givens``) and the asked clause
(``ask``), then fills an operation whose ``Binding`` names that ask:

- every stated value fills one input of its dimension. Two inputs of one
  dimension are told apart by the word just before the value ("from", "to",
  "initial", "reaches"), or filled largest first where the law says so;
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
from app.modules.physics.bodies import named_body
from app.modules.physics.catalog import CATALOG
from app.modules.physics.catalog.spec import Binding, FormulaSpec, VariableSpec
from app.modules.physics.display import si_symbol
from app.modules.physics.extractors.common import _detect_gravity
from app.modules.physics.givens import ANGLE, Given, scan_givens, unit_dimension, unit_expression

_DIMENSIONLESS = "dimensionless"
# "from 0 to 27 m/s": a bare number shares the unit of the value it runs to.
_RANGE_LINK = re.compile(r"\s*(?:to|-|\u2013|and|or)\s*", re.IGNORECASE)
_SENTENCE_BREAK = re.compile(r"[.;?!](?:\s|$)")
# An asked phrase followed by its own value labels a given: "an acceleration of 2".
_LABELLED = re.compile(r"\s*(?:of|=|is|:|was)?\s*[-+]?\.?\d")
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
    asked_clause = clause.lower()
    named = [
        (spec, strength)
        for spec in _bindable()
        if spec.binding is not None
        and (not spec.binding.cues or any(_phrase(cue).search(lower) for cue in spec.binding.cues))
        and (strength := _ask_strength(asked_clause, spec.binding.asks))
    ]
    if not named:
        return None
    givens = _givens(text)
    if len(givens) > _MAX_GIVENS:
        return None
    asked = set(asked_dimensions(text))
    unit = asked_unit(text)
    asked_in = _dimension(unit_expression(unit) or "") if unit else None
    fits = [
        fit
        for spec, strength in named
        if (fit := _fit(spec, strength, text, lower, givens, asked, asked_in)) is not None
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
    return _dimension(variable.dimension or "")


def _given_kind(given: Given) -> str | None:
    if given.dimension is not None:
        return given.dimension
    return _DIMENSIONLESS if not given.unit else None


@lru_cache(maxsize=1024)
def _phrase(phrase: str) -> re.Pattern[str]:
    # A leading word boundary only: "climb" names "climbs", "accelerat" both forms.
    return re.compile(rf"(?<![\w]){re.escape(phrase)}")


def _last_said(window: str, words: tuple[str, ...]) -> int:
    """Where the last of these words ends in the window; -1 when none is there."""
    ends = [match.end() for word in words for match in _phrase(word).finditer(window)]
    return max(ends, default=-1)


def _ask_strength(clause: str, asks: tuple[str, ...]) -> int:
    """The longest asked phrase this clause names, not counting a given's label."""
    strength = 0
    for phrase in asks:
        for match in _phrase(phrase).finditer(clause):
            if not _LABELLED.match(clause, match.end()):
                strength = max(strength, len(phrase))
    return strength


def _other_sense(
    lower: str, asks: tuple[str, ...], givens: list[Given], produced: set[str | None]
) -> bool:
    """The asked word labels a value of another kind: "my weight is 70 kg".

    That question uses the word in its everyday sense (a mass), and the law's
    sense (a force) would answer something it did not ask.
    """
    for given in givens:
        kind = _given_kind(given)
        if kind is None or kind in produced:
            continue
        before = lower[max(0, given.start - 40) : given.start]
        for phrase in asks:
            label = re.search(rf"{re.escape(phrase)}\s*(?:of|=|is|:|was)?\s*$", before)
            if label is not None:
                return True
    return False


def _window(lower: str, start: int, end: int) -> str:
    """The words before a value, back to the previous value or sentence."""
    breaks = [match.end() for match in _SENTENCE_BREAK.finditer(lower, start, end)]
    return lower[max([start, *breaks]) : end]


def _choose(
    options: list[VariableSpec], window: str, binding: Binding, is_result_kind: bool
) -> VariableSpec | None:
    """The input this value fills, or None when the words do not say."""
    said = [(_last_said(window, option.words), option) for option in options]
    latest = max(position for position, _ in said)
    if is_result_kind and _last_said(window, binding.result_words) > latest:
        # "reaches 18 m/s" while the final speed is asked: that is the answer.
        return None
    if latest >= 0:
        named = [option for position, option in said if position == latest]
        return named[0] if len(named) == 1 else None
    if len(options) == 1:
        return options[0]
    if all(option.name in binding.descending for option in options):
        return options[0]
    return None


def _unstated(variable: VariableSpec, text: str, lower: str) -> float | None:
    for phrase, value in variable.implied:
        if _phrase(phrase).search(lower):
            return value
    if variable.fallback == "gravity":
        return _detect_gravity(text)
    if variable.fallback == "body_mass":
        body = named_body(lower)
        return None if body is None else body[0]
    return None


def _si_unit(variable: VariableSpec) -> str:
    if variable.name.startswith("angle"):
        return "deg"
    return si_symbol(variable.dimension) if variable.dimension else ""


def _fit(
    spec: FormulaSpec,
    strength: int,
    text: str,
    lower: str,
    givens: list[Given],
    asked: set[str],
    asked_in: str | None,
) -> _Fit | None:
    binding = spec.binding
    if binding is None:
        return None
    produced = {_dimension(unit) for unit in binding.result}
    if (asked and not asked <= produced) or (asked_in is not None and asked_in not in produced):
        return None
    if _other_sense(lower, binding.asks, givens, produced):
        return None
    variables = [variable for variable in spec.variables if variable.visible]
    params: dict[str, float] = {}
    units: dict[str, str] = {}
    previous = 0
    for given in givens:
        kind = _given_kind(given)
        options = [
            variable
            for variable in variables
            if variable.name not in params and kind is not None and _variable_kind(variable) == kind
        ]
        if not options:
            return None
        window = _window(lower, previous, given.start)
        choice = _choose(options, window, binding, kind in produced)
        if choice is None:
            return None
        negative = _last_said(window, choice.negating) >= 0
        params[choice.name] = -given.value if negative else given.value
        units[choice.name] = given.unit
        previous = given.end
    _largest_first(params, binding.descending)
    for variable in variables:
        if variable.name in params:
            continue
        value = _unstated(variable, text, lower)
        if value is not None:
            params[variable.name] = value
            units[variable.name] = _si_unit(variable)
    if frozenset(params) not in binding.inputs:
        return None
    return _Fit(spec, params, units, strength)


def _largest_first(params: dict[str, float], names: tuple[str, ...]) -> None:
    """Refill a symmetric pair largest first: the heavier Atwood mass is m₁."""
    present = [name for name in names if name in params]
    values = sorted((params[name] for name in present), reverse=True)
    for name, value in zip(present, values, strict=True):
        params[name] = value

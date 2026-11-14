"""Fill one catalog law from a question's stated values and words.

A subject's binder finds the laws whose ``Binding`` names what a question asks, then asks
this module to fill each one:

- every stated value fills one input of its dimension. Two inputs of one
  dimension are told apart by the word just before the value ("from", "to",
  "initial", "reaches") or just after it ("on the primary"), or filled in
  order (largest first where the law says so);
- a value the words mark as the result itself ("reaches 18 m/s" when the
  final speed is asked) means this is not the law;
- unstated inputs come from phrases ("from rest" is u = 0) or from the subject's
  settings (g, the named planet's mass);
- the filled inputs must be exactly a set the solver answers from.

Anything short of one way to fill the law declines: a value has no input, or an input
could take either of two values.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache

from app.services.law_binding.givens import Given, scan_givens
from app.services.law_binding.labels import LABEL_UNITS, holds, value_label
from app.services.law_binding.roles import role_words
from app.services.law_binding.spec import Binding, FormulaSpec, VariableSpec
from app.services.law_binding.units import ANGLE, UnitTable, dimension_of, unit_dimension
from app.services.law_binding.words import (
    ask_strength,
    choose,
    implied_value,
    labels_as,
    last_said,
    word_pattern,
    words_after,
    words_before,
)

_DIMENSIONLESS = "dimensionless"
_ANGULAR = "angular "
# "from 0 to 27 m/s": a bare number shares the unit of the value it runs to.
_RANGE_LINK = re.compile(r"\d\s*(?:to|-|\u2013|and|or)\s*", re.IGNORECASE)
# Only a conjunction between two values: they share the words before the first.
_LIST_LINK = re.compile(r"\s*(?:,|and|,\s*and)\s*", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Subject:
    """What one subject brings to the binder."""

    units: UnitTable
    # The value an unstated input takes: (variable, text, lower text) -> value or None.
    fallback: Callable[[VariableSpec, str, str], float | None]
    # The unit an implied or fallback value is written in.
    unit_of: Callable[[VariableSpec], str]


@dataclass(frozen=True, slots=True)
class Question:
    """A question as the binder reads it."""

    text: str
    lower: str
    givens: tuple[Given, ...]
    # Dimensions the asked clause names, and the dimension of a unit it asks in.
    asked: frozenset[str]
    asked_in: str | None
    # Where the asked clause starts in ``lower``.
    asked_from: int


@dataclass(frozen=True, slots=True)
class Fit:
    spec: FormulaSpec
    params: dict[str, float]
    units: dict[str, str]
    strength: int
    # How many facts the words state this fill used ("stops in" is v = 0): of two laws
    # named alike, the one that accounts for more of the question is its law.
    stated: int = 0


# "$0.15 per kWh" is a price. No law takes one, so it is not a value to
# account for: a question that asks the cost still declines on its ask.
_PRICE = re.compile(r"(?:[$€£¥]|\bcosts?|\bprice(?:\s+of)?|\bpays?|\bcharges)\s*$", re.IGNORECASE)


def read_givens(text: str, units: UnitTable) -> tuple[Given, ...]:
    """Stated values, a bare number taking the unit of the range it starts."""
    givens = [
        given
        for given in scan_givens(text, units)
        if given.unit or not _PRICE.search(text, 0, given.start)
    ]
    read: list[Given] = []
    for index, given in enumerate(givens):
        following = givens[index + 1] if index + 1 < len(givens) else None
        if (
            given.dimension is None
            and not given.unit
            and following is not None
            and following.dimension is not None
            and _RANGE_LINK.fullmatch(text, given.end - 1, following.start)
        ):
            reading = unit_dimension(units.expression(following.unit) or "")
            if reading is not None:
                dimension, scale, offset = reading
                si = given.value * scale + offset
                given = Given(given.start, given.end, given.value, following.unit, dimension, si)
        read.append(given)
    return tuple(read)


def variable_kind(variable: VariableSpec) -> str | None:
    if variable.name.startswith("angle"):
        return ANGLE
    if variable.dimensionless:
        return _DIMENSIONLESS
    kind = dimension_of(variable.dimension or "")
    return _ANGULAR + kind if kind and _angular(variable.dimension or "") else kind


def _given_dimension(given: Given) -> str | None:
    if given.dimension is not None:
        return given.dimension
    return _DIMENSIONLESS if not given.unit else None


def given_kind(given: Given, units: UnitTable) -> str | None:
    """The input kind a value can fill: its dimension, with angular rates apart.

    A frequency in Hz and an angular velocity in rad/s share a dimension, but
    50 Hz is not 50 rad/s: each fills only its own kind of input.
    """
    dimension = _given_dimension(given)
    if dimension is not None and _angular(units.expression(given.unit) or ""):
        return _ANGULAR + dimension
    return dimension


def _angular(expression: str) -> bool:
    return expression.startswith(("radian /", "revolution /"))


def _other_sense(question: Question, asks: tuple[str, ...], produced: set[str | None]) -> bool:
    """The asked word labels a value of another kind: "my weight is 70 kg".

    That question uses the word in its everyday sense (a mass), and the law's
    sense (a force) would answer something it did not ask.
    """
    lower = question.lower
    for given in question.givens:
        kind = _given_dimension(given)
        if kind is None or kind in produced:
            continue
        before = lower[max(0, given.start - 40) : given.start]
        # In the asked clause "of" is belonging, not a value: "find the
        # internal energy of 2 mol of gas" asks for the energy of the gas.
        links = r"(?:=|is|:|was)?" if given.start >= question.asked_from else r"(?:of|=|is|:|was)?"
        for phrase in asks:
            # "specific heat of 900 J/kg/K" names the capacity. The short ask
            # "heat" is the end of that label, not the heat the question asks for.
            # "to heat 1.5 kg of water" is the verb, and labels nothing.
            label = re.search(rf"(?<!specific )(?<!\bto ){re.escape(phrase)}\s*{links}\s*$", before)
            if label is None:
                continue
            # "the electric field 0.2 m from a charge" places the field; it
            # does not label it. Only a bare value can be read that way.
            if not label.group().rstrip().endswith(phrase) or not _PLACED.match(
                lower, value_end(lower, given)
            ):
                return True
    return False


# "the absolute pressure 50 m deep" places the pressure too.
_PLACED = re.compile(
    r"\s*(?:away\s+)?(?:from|above|below|beyond|behind|away|deep|down|under|underwater|beneath)\b"
)


def value_end(lower: str, given: Given) -> int:
    """Where a value's text ends: after its unit ("100 kPa"), not its number."""
    unit = given.unit.lower()
    for at in (given.end, given.end + 1):
        if unit and lower.startswith(unit, at):
            return at + len(unit)
    return given.end


def largest_first(
    params: dict[str, float], units: dict[str, str], names: tuple[str, ...], table: UnitTable
) -> None:
    """Refill a symmetric pair largest first: the heavier Atwood mass is m₁.

    Values are compared in SI and move with their units: 5 kg outweighs 3000 g.
    """
    present = [name for name in names if name in params]
    pairs = sorted(
        ((params[name], units[name]) for name in present),
        key=lambda pair: _in_si(pair[0], pair[1], table),
        reverse=True,
    )
    for name, (value, unit) in zip(present, pairs, strict=True):
        params[name] = value
        units[name] = unit


def _in_si(value: float, unit: str, table: UnitTable) -> float:
    reading = unit_dimension(table.expression(unit) or "") if unit else None
    return value if reading is None else value * reading[1] + reading[2]


def fit(
    spec: FormulaSpec,
    strength: int,
    question: Question,
    subject: Subject,
    known: Mapping[str, tuple[float, str]] | None = None,
) -> Fit | None:
    """This law filled from the question, or None when it does not fit exactly one way.

    ``known`` holds values worked out before (by name: value, unit), which fill their
    inputs as the words would; a law chained after another reads them (``chain``). A
    stated value then left with no open input is the earlier law's, and the chain checks
    that every value was used by some law.
    """
    binding = spec.binding
    if binding is None:
        return None
    produced = {dimension_of(unit) for unit in binding.result}
    asked, asked_in = question.asked, question.asked_in
    if (asked and not asked <= produced) or (asked_in is not None and asked_in not in produced):
        return None
    if _other_sense(question, binding.asks, produced):
        return None
    lower, givens = question.lower, question.givens
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
            units[variable.name] = subject.unit_of(variable)
    stated = len(params)
    for variable in variables:
        if known and variable.name in known and variable.name not in params:
            params[variable.name], units[variable.name] = known[variable.name]
    listed = word_pattern("respectively").search(lower) is not None
    labels = given_labels(lower, givens)
    previous = 0
    earlier = ""
    filled: list[VariableSpec] = []
    described = 0
    for index, given in enumerate(givens):
        kind = given_kind(given, subject.units)
        # "An amplitude of 0.1 m" is no distance travelled: a value named as a quantity
        # fills only an input that is it (``labels``).
        options = [
            variable
            for variable in variables
            if variable.name not in params
            and kind is not None
            and variable_kind(variable) == kind
            and holds(variable, labels[index])
        ]
        if not options:
            if known:
                continue
            return None
        before = words_before(lower, previous, given.start)
        # The words that still describe the value before ("12 teeth on the input") are
        # its own, not this one's.
        own = words_before(lower, max(previous, described), given.start)
        # "at 100 kPa and 300 K": the words before a list name every value in it.
        if _LIST_LINK.fullmatch(before):
            before, own = earlier, ""
        earlier = before
        following = _next_start(givens, index, lower)
        after = words_after(lower, given.end, following)
        described = given.end + len(after)
        if _labels_the_result(binding, given, produced, before, lower, following):
            # "A total power of 3 D; one lens is 2 D": the sum stated is no lens.
            return None
        choice = choose(
            options, before, after, binding, _given_dimension(given) in produced, listed=listed
        )
        if choice is None or _names_a_filled_input(choice, filled, own):
            return None
        filled.append(choice)
        negative = last_said(before, choice.negating) >= 0
        params[choice.name] = -given.value if negative else given.value
        units[choice.name] = given.unit
        previous = value_end(lower, given)
    largest_first(params, units, binding.descending, subject.units)
    for variable in variables:
        if variable.name in params:
            continue
        value = subject.fallback(variable, question.text, lower)
        if value is not None:
            params[variable.name] = value
            units[variable.name] = subject.unit_of(variable)
    if (
        frozenset(params) not in binding.inputs
        or _angle_left_unstated(variables, params, question)
        or named_but_unstated(variables, params, question.lower)
    ):
        return None
    return Fit(spec, params, units, strength, stated)


def _next_start(givens: Sequence[Given], index: int, lower: str) -> int:
    return givens[index + 1].start if index + 1 < len(givens) else len(lower)


# Every law the binder tries reads the same question's labels.
@lru_cache(maxsize=256)
def given_labels(lower: str, givens: tuple[Given, ...]) -> tuple[str | None, ...]:
    """The quantity each value is named as (``labels.value_label``), in order: by the words
    since the value before it, or the words that follow it."""
    found: list[str | None] = []
    previous = 0
    for index, given in enumerate(givens):
        end = value_end(lower, given)
        before = words_before(lower, previous, given.start)
        label = value_label(before, words_after(lower, end, _next_start(givens, index, lower)))
        # "500 J per cycle" is a heat engine's work, no period.
        unit = LABEL_UNITS.get(label or "")
        found.append(None if unit and given.dimension != dimension_of(unit) else label)
        previous = end
    return tuple(found)


def _labels_the_result(
    binding: Binding,
    given: Given,
    produced: set[str | None],
    before: str,
    lower: str,
    following: int,
) -> bool:
    """The value is labelled as the law's result (``Binding.result_labels``)."""
    if not binding.result_labels or _given_dimension(given) not in produced:
        return False
    after = words_after(lower, value_end(lower, given), following)
    return labels_as(binding.result_labels, before, after)


def _names_a_filled_input(choice: VariableSpec, filled: list[VariableSpec], before: str) -> bool:
    """The words before a value name, as its end of the change, an input an earlier value
    already filled.

    "Compressed to 2 L at 300 kPa. Its initial pressure was 100 kPa": "at" put 300 kPa
    at P₁, so the 100 kPa the words call initial was left only P₂, and answered 0.667 L
    for 6 L. Two values for one input is not one way to fill the law. Only a word that
    names an end counts ("initial", "started at"): "at" also places a value ("what volume
    will it have at 127 °C").
    """
    own = last_said(before, choice.words)
    kind = variable_kind(choice)
    return any(
        variable_kind(variable) == kind and last_said(before, role_words(variable.words)) > own
        for variable in filled
    )


_ANGLE_WORD = re.compile(r"(?<![\w])angles?\b", re.IGNORECASE)


def _angle_left_unstated(
    variables: list[VariableSpec], params: dict[str, float], question: Question
) -> bool:
    """The question says the force or path is at an angle and states none: "a 10 N force
    at an angle over 4 m". The law's form without its angle input is the parallel case,
    which the question rules out."""
    open_angle = any(variable_kind(v) == ANGLE and v.name not in params for v in variables)
    stated = any(
        given.dimension == ANGLE or given.unit in {"°", "deg"} for given in question.givens
    )
    return open_angle and not stated and _ANGLE_WORD.search(question.lower) is not None


def named_but_unstated(
    variables: Iterable[VariableSpec], params: Mapping[str, float], lower: str
) -> bool:
    """An input the question's situation names ("from the top of a hill") is left without
    a value: the law's form without it (a launch from the ground) is not this question."""
    return any(
        v.name not in params and any(word_pattern(w).search(lower) for w in v.named_by)
        for v in variables
    )


def named_strength(
    binding: Binding, clause: str, lower: str, units: UnitTable, *, cue_text: str | None = None
) -> int:
    """How strongly the asked clause names this law; 0 when its cues or excludes rule it out.

    The word checks run before any unit is read, so a question that names no law's ask
    costs a few regex searches. ``cue_text`` is ``lower`` with any phrase the subject
    reads a cue from added.
    """
    if not admits(binding, lower, cue_text=cue_text):
        return 0
    return ask_strength(clause, binding.asks, binding.result, units)


def admits(binding: Binding, lower: str, *, cue_text: str | None = None) -> bool:
    """The question says one of the law's cues, if it has any, and nothing it excludes."""
    cues = lower if cue_text is None else cue_text
    if binding.cues and not any(word_pattern(cue).search(cues) for cue in binding.cues):
        return False
    return not any(word_pattern(word).search(lower) for word in binding.excludes)


def read_question(
    text: str,
    clause: str,
    units: UnitTable,
    *,
    max_givens: int,
    asked: frozenset[str] = frozenset(),
    asked_in: str | None = None,
) -> Question | None:
    """The question as the binder reads it, or None when it states too many values.

    A school question states a handful of values; a paste full of numbers is not one
    law's inputs.
    """
    givens = read_givens(text, units)
    if len(givens) > max_givens:
        return None
    lower = text.lower()
    return Question(
        text=text,
        lower=lower,
        givens=givens,
        asked=asked,
        asked_in=asked_in,
        asked_from=lower.rfind(clause.lower()),
    )


def only_strongest_fit[K](
    named: Iterable[tuple[K, FormulaSpec, int]], question: Question, subject: Subject
) -> tuple[K, Fit] | None:
    """The one law that fits most strongly, with the key it was named under.

    Two laws that fit equally strongly decline: the question does not say which it is.
    Of two named alike, the one whose fill uses more of what the words state wins: "stops
    in 4 s" is a final speed of 0, which d = vt never reads.
    """
    fits = [
        (key, filled)
        for key, spec, strength in named
        if (filled := fit(spec, strength, question, subject)) is not None
    ]
    if not fits:
        return None
    strongest = max((filled.strength, filled.stated) for _, filled in fits)
    top = [entry for entry in fits if (entry[1].strength, entry[1].stated) == strongest]
    return top[0] if len(top) == 1 else None

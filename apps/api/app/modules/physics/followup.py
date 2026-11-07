"""Replay the previous physics problem when this line only continues it.

Each shape declines instead of guessing: explain the result, ask for another
quantity of the same setup ("how far does it go?"), give the result in another
unit, or replace or scale one given ("and after 10 s?", "what if the mass
doubles?"). A rewrite counts only when it verifies. A new question that brings
its own data is not a follow-up.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from app.modules.physics.ask import ask_clause, asks
from app.modules.physics.ask_words import _DIMENSIONLESS, _MONEY, _QUANTITIES
from app.modules.physics.extract import extract_physics_intent, needs_physics
from app.modules.physics.givens import ANGLE, PHYSICS_UNITS
from app.modules.physics.kept_property import kept_property_problem
from app.modules.physics.verified_answers import results as _results
from app.modules.physics.verified_answers import verified_display as _verified_display
from app.modules.physics.verified_answers import verifies as _verifies
from app.services.law_binding.fit import read_givens
from app.services.law_binding.givens import Given
from app.services.law_binding.units import unit_dimension
from app.services.problem_followup import (
    EXPLAIN_RE,
    GivenRewriter,
    adjacent_problem,
    ask_replaced,
    asked_unit,
    changes_relatively,
    continues,
    followup_line,
    given_name,
    in_unit,
    new_value,
    remove_given,
    replace_given,
    same_quantities,
    with_sentences,
)
from app.services.scaled_followup import scaled_given

PHYSICS_FOLLOWUP_HINT = (
    "This short request continues the immediately preceding physics problem. "
    "When the request changes one given or asks for a different quantity, the "
    "verified block is that new result: present it in the usual layout with the "
    "changed given under Given, and never compare it with or comment on the earlier "
    "answer. When it asks why or how, explain the verified result: why the formula "
    "applies and how the numbers produce it. Do not start a new problem. Copy the "
    "verified numbers; do not recompute them."
)

_ABOUT = re.compile(r"^(?:and )?what about (?:the |its )?(?P<ask>[a-z][a-z ]{0,40}?)\??$")
_CHANGED = re.compile(
    r"^(?:but )?(?:what )?if "
    r"(?:it (?:was|were|is) |"
    r"(?:the )?(?P<name>[a-z][a-z ]{0,30}?) (?:was|were|is) )"
    r"(?P<value>[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:e[-+]?\d+)?) ?"
    r"(?P<unit>[a-zμµ°/^0-9][a-zμµ°/^0-9. ]{0,16})?\??$"
)
# "how far does it go?" asks another quantity of the same setup.
_HOW = re.compile(
    r"^(?:(?:and|so|ok(?:ay)?|now|then)[ ,]+)?how (?P<word>far|long|high|fast) "
    r"(?:does|did|will|would|is|was|can) (?:it|she|he|they|the [a-z]+) "
    r"(?:go|travel|get|take|fall|rise|climb|move|moving|going|travelling|traveling"
    r"|stay in the air|be in the air)"
    r"(?: (?:for|in total|altogether|(?:in|during|over) (?:that|this|the same) time"
    r"|before (?:it )?(?:stops|lands|hits the ground)))?$"
)
_HOW_QUANTITY = {"far": "distance", "long": "time", "high": "maximum height", "fast": "speed"}


def physics_followup_whole(query: str | None) -> bool:
    """The follow-up problem stands for all of this line: one change, one other quantity or
    one unit, nothing besides. "and after 10 s, in km/h?" or "what if it was 3 m/s^2?
    explain why" ask more than the problem rewritten from them answers, so the server does
    not write their reply alone."""
    written = followup_line(query)
    if written is None:
        return False
    line = written.lower()
    if EXPLAIN_RE.fullmatch(line):
        return False
    return (
        scaled_given(line) is not None
        or _CHANGED.fullmatch(line) is not None
        or _ABOUT.fullmatch(line) is not None
        or _HOW.fullmatch(line) is not None
        or asked_unit(written) is not None
        or new_value(written) is not None
    )


def physics_followup_problem(query: str | None, recent: Sequence[Any]) -> str | None:
    """The problem to verify again, or None when this line is not that follow-up."""
    written = followup_line(query)
    prior = adjacent_problem(recent, needs_physics)
    if written is None or prior is None:
        return None
    line = written.lower()
    if extract_physics_intent(line) is not None:
        return None
    if EXPLAIN_RE.fullmatch(line):
        return prior
    # Before the other shapes: "what if it was 3 times higher" is no new value.
    scaled = scaled_given(line)
    if scaled is not None:
        rewritten = _GIVENS.scaled(prior, scaled)
        return _kept_or_declined(prior, rewritten) if _held_fixed(prior) else rewritten
    about = _ABOUT.fullmatch(line)
    if about is not None:
        return _another_quantity(prior, about.group("ask"))
    changed = _CHANGED.fullmatch(line)
    if changed is not None:
        rewritten = _GIVENS.changed(
            prior, changed.group("name"), changed.group("value"), changed.group("unit")
        )
        if _held_fixed(prior):
            return _kept_or_declined(prior, rewritten)
        return None if rewritten is None or _ambiguous(prior, rewritten) else rewritten
    how = _HOW.fullmatch(line)
    if how is not None:
        return _another_quantity(prior, _HOW_QUANTITY[how.group("word")])
    unit = asked_unit(written)
    if unit is not None:
        return _in_unit(prior, unit)
    value = new_value(written)
    if value is not None:
        rewritten = _GIVENS.changed(prior, None, *value)
        if _held_fixed(prior):
            return _kept_or_declined(prior, rewritten)
        return None if rewritten is None or _ambiguous(prior, rewritten) else rewritten
    return None if _held_fixed(prior) else _restated(prior, written)


# A result that is a property of the object or its medium, not of what is done to it:
# a resistor's 6 Ω stays 6 Ω when the voltage doubles (the current doubles instead), a
# string's wave speed stays when the frequency doubles, a spring's constant when the
# force does. Re-solving with one given changed would change the property itself.
_INTRINSIC = (
    "resistance",
    "resistivity",
    "capacitance",
    "spring constant",
    "specific heat capacity",
    "latent heat",
    "density",
    "refractive index",
    "coefficient of friction",
)
# Laws whose asked speed is the medium's: v = fλ.
_SET_BY_MEDIUM = frozenset({"wave_speed"})
# A device's rating is a property too: "a 60 W bulb" on twice the voltage is no 60 W bulb.
_RATING = re.compile(
    # A number starts once, not at every digit of "1.1.1…": the scan stays linear.
    r"(?<![\w.,])\d[\d.,]*\s*(?:k?w|watts?|kilowatts?)\s+(?:[a-z]+\s+)?(?:bulb|lamp|light|heater|kettle"
    r"|motor|toaster|iron|fan|oven|microwave|dryer|hairdryer|charger|appliance|tv|radio)s?\b",
    re.IGNORECASE,
)
# A source with an internal resistance holds its emf fixed while the circuit changes.
_INTERNAL = re.compile(r"\binternal resistance\b|\bemf\b|\be\.m\.f\b", re.IGNORECASE)


def _kept_or_declined(prior: str, rewritten: str | None) -> str | None:
    """A problem whose result is held fixed: re-asked with the component's constant kept
    (``kept_property``), or declined. A rated device or a source with an internal
    resistance is never re-asked: the change holds neither its rating nor its emf."""
    if rewritten is None or _RATING.search(prior) or _INTERNAL.search(prior):
        return None
    return kept_property_problem(prior, rewritten)


def _held_fixed(prior: str) -> bool:
    """True when no changed given of the problem re-solves to a true number: it asks for
    a property of the object or its medium, rates a device, or has a source whose emf
    and internal resistance the change would hold wrongly."""
    if _RATING.search(prior) or _INTERNAL.search(prior):
        return True
    asked = {ask.dimension for ask in asks(prior)}
    if asked & {_dimension_of_phrase(name) for name in _INTRINSIC}:
        return True
    if not asked & {_dimension_of_phrase("speed")}:
        return False
    intent = extract_physics_intent(prior)
    return intent is not None and intent.physics_op in _SET_BY_MEDIUM


def _in_unit(prior: str, unit: str) -> str | None:
    """The prior result in the asked unit, when the verified card writes that unit."""
    if _dimension_of_unit(unit) is None:
        return None
    rewritten = in_unit(prior, unit)
    display = _verified_display(rewritten)
    if display is None or unit.replace(" ", "") not in display.replace(" ", ""):
        return None
    return rewritten


def _another_quantity(prior: str, ask: str) -> str | None:
    phrase = " ".join(ask.split())
    if phrase not in _QUANTITIES and phrase not in {
        "range",
        "time of flight",
        "maximum height",
        "max height",
        "impact speed",
    }:
        return None
    rewritten = ask_replaced(prior, phrase)
    return rewritten if _verifies(rewritten) else None


def _restated(prior: str, written: str) -> str | None:
    """The previous problem with this line's changes, when it verifies one way only.

    "Ok and if it was going 100 km/h with the same braking, how far then?": the line's
    values take the place of the earlier ones of their kind, a quantity it says stays
    the same is stated at its earlier result, and its ask replaces the earlier one.
    """
    if (not continues(written) and not asks(written)) or changes_relatively(written):
        return None
    changed = [g for g in read_givens(written, PHYSICS_UNITS) if g.dimension]
    kept = [d for d in map(_kept_dimension, same_quantities(written, _KEPT_NAMES)) if d]
    if not changed and not kept:
        return None
    # Two new values of one kind ("from 10 m/s to 20 m/s") have no single earlier given
    # each takes the place of: replacing one after the other kept only the last.
    dimensions = [g.dimension for g in changed]
    if len(set(dimensions)) < len(dimensions):
        return None
    earlier = [g for g in read_givens(prior, PHYSICS_UNITS) if g.dimension]
    pairs = []
    for given in changed:
        # Matched against the earlier problem's givens, never the text already edited.
        same_kind = [g for g in earlier if g.dimension == given.dimension]
        # One given of its kind, and a value it changes: the same value again is no change.
        if len(same_kind) != 1 or (same_kind[0].value, same_kind[0].unit) == (
            given.value,
            given.unit,
        ):
            return None
        pairs.append((same_kind[0], given))
    text = prior
    # From the last position back, so each earlier given's position still holds.
    for old, new in sorted(pairs, key=lambda pair: pair[0].start, reverse=True):
        text = replace_given(text, old, f"{new.value:g}", new.unit)
    # Its ask clause alone ("how far then"): the rest of the line restates its values.
    # With none, the earlier asks stand, but not one the line keeps: it is a given now.
    ask = ask_clause(written) if asks(written) else _asks_left(prior, kept)
    return _kept(prior, text, ask, kept, changed)


# The names a quantity said to stay the same goes by: the ask vocabulary, and a car's
# "braking" for its deceleration. Not in the ask vocabulary, which reads "braking force"
# and "stopping distance" by their last word.
_KEPT_NAMES: dict[str, str] = {**_QUANTITIES, "braking": _QUANTITIES["deceleration"]}


def _kept_dimension(name: str) -> str | None:
    return _dimension_of_phrase("deceleration" if name == "braking" else name)


def _asks_left(prior: str, kept: list[str]) -> str | None:
    """The earlier asks without the quantities kept the same, as one ask; None when all
    stand (the earlier ask sentence stays) or none is left."""
    earlier = asks(prior)
    left = [ask.words.strip() for ask in earlier if ask.dimension not in kept]
    if len(left) == len(earlier) or not left:
        return None
    return " and ".join(left) + "?"


def _kept(
    prior: str, text: str, ask: str | None, kept: list[str], changed: list[Given]
) -> str | None:
    """``text`` with each kept quantity stated at the prior result, without the one stated
    value it now over-determines; None unless exactly one answer verifies."""
    results = _results(prior)
    if results is None:
        return None
    stated: list[str] = []
    for dimension in kept:
        earlier = [r for r in results if r.dimension == dimension]
        if len(earlier) != 1:
            if any(g.dimension == dimension for g in read_givens(text, PHYSICS_UNITS)):
                continue  # a stated value kept as it was
            return None
        sentence = _stated(earlier[0])
        if sentence is None:
            return None
        stated.append(sentence)
    if not stated:
        whole = with_sentences(text, ask=ask, stated=())
        return None if not _verifies(whole) or _ambiguous(prior, whole) else whole
    new = {(g.value, g.unit) for g in changed}
    verified: dict[str, str] = {}
    for given in read_givens(text, PHYSICS_UNITS):
        if not given.dimension or (given.value, given.unit) in new:
            continue
        candidate = with_sentences(remove_given(text, given), ask=ask, stated=tuple(stated))
        display = _verified_display(candidate)
        if display is not None:
            verified[candidate] = display
    if len(set(verified.values())) != 1:
        return None
    return next(iter(verified))


def _ambiguous(prior: str, rewritten: str) -> bool:
    """A changed value whose problem gives another answer when an earlier result is held
    in place of a stated value: "and if it was going 100 km/h?" after a car that stopped in
    4 s may keep the time or the deceleration, and the two answers differ."""
    plain = _verified_display(rewritten)
    results = _results(prior)
    if plain is None or not results:
        return False
    asked = {r.dimension for r in _results(rewritten) or []}
    before = {(g.value, g.unit) for g in read_givens(prior, PHYSICS_UNITS)}
    for result in results:
        sentence = _stated(result)
        if result.dimension in asked or sentence is None:
            continue
        for given in read_givens(rewritten, PHYSICS_UNITS):
            if not given.dimension or given.dimension == result.dimension:
                continue
            if (given.value, given.unit) not in before:
                continue  # the value the line changed
            held = with_sentences(remove_given(rewritten, given), ask=None, stated=(sentence,))
            other = _verified_display(held)
            if other is not None and other != plain:
                return True
    return False


def _stated(result: Given) -> str | None:
    """An earlier result said as a given, by the vocabulary's first name of its kind: its
    plain name ("acceleration"), which sets no sign of its own as "deceleration" would."""
    for phrase in _QUANTITIES:
        if " " not in phrase and _dimension_of_phrase(phrase) == result.dimension:
            return f"The {phrase} is {result.value:g} {result.unit}."
    return None


def _dimension_of_unit(unit: str) -> str | None:
    reading = unit_dimension(PHYSICS_UNITS.expression(unit) or "")
    return None if reading is None else reading[0]


def _dimension_of_phrase(phrase: str) -> str | None:
    expression = _QUANTITIES.get(phrase)
    if expression is None:
        return None
    if expression in {ANGLE, _DIMENSIONLESS, _MONEY}:
        return expression
    reading = unit_dimension(expression)
    return None if reading is None else reading[0]


def _asked_dimensions(prior: str) -> set[str]:
    return {ask.dimension for ask in asks(prior)}


# The words a problem uses for each kind of length: a length shares its dimension with
# every other, so a named one needs its own words in the problem.
_LENGTH_WORDS = {
    "height": r"high|height|tall|drop|drops|dropped|falls?|fell|cliff|building|tower|hill"
    r"|slope|above",
    "distance": r"far|distance|travel(?:s|s?led|ed)?|over|covers?|covered|lands?|landed"
    r"|across|away|apart",
    "radius": r"radius|string|rope|cord|circle|orbit",
    "length": r"length|long|string|rope|cord|pendulum|wire|rod",
}


def _fits(prior: str, name: str) -> bool:
    """A named length needs its own words in the problem: "the wavelength" of a dropped
    ball, or "the height" of a swung string, is no length the problem gave."""
    words = given_name(name).split()
    if not words or _dimension_of_phrase(" ".join(words)) != _dimension_of_phrase("length"):
        return True
    cue = _LENGTH_WORDS.get(words[-1], re.escape(words[-1]) + "s?")
    return re.search(rf"\b(?:{cue})\b", prior, re.IGNORECASE) is not None


_GIVENS = GivenRewriter(
    PHYSICS_UNITS,
    _dimension_of_unit,
    _dimension_of_phrase,
    _verifies,
    asked=_asked_dimensions,
    fits=_fits,
)

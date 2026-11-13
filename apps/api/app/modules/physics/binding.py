"""Read a question straight into a physics catalog operation, from its givens and its ask.

The extractors are written for the phrasings they know. Many questions just
state a law's inputs and ask for its result in words the catalog can list:
"accelerates from 10 m/s to 30 m/s in 5 s. Find its acceleration." The binder
reads the asked clause (``ask``), finds every operation whose ``Binding`` names
that ask, and fills each from the stated values with the shared engine
(``services.law_binding.fit``), with physics' settings for an unstated input
(g, the named planet's mass).

Anything short of one operation with one way to fill it declines: two
operations fit, a value has no input, an input could take either of two
values, or the ask names nothing the catalog lists. It runs after the
extractors, so it only answers questions they declined.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import lru_cache

from app.modules.physics.ask import (
    AskedEnd,
    ask_clause,
    asked_dimensions,
    asked_end,
    asked_unit,
)
from app.modules.physics.binding_values import fallback_value, light_starts_inside, si_unit
from app.modules.physics.bodies import names_only_water
from app.modules.physics.catalog import CATALOG, WATER_ONLY
from app.modules.physics.catalog.projectile import AT_AN_ANGLE
from app.modules.physics.frames import FRAMES_UNREAD_MARKER, adds_speeds_across_frames
from app.modules.physics.givens import FRACTION_OF_C, PHYSICS_UNITS, unit_expression
from app.modules.physics.law_range import holds_its_range
from app.modules.physics.motion import (
    ROLLING_BODY_MARKER,
    SPEED_CHANGE_MARKER,
    constant_speed_laws_hold,
    rolling_body,
)
from app.modules.physics.net_force import NOT_NET_FORCE_MARKER, others_share_the_force
from app.modules.physics.optic_elements import (
    LIGHT_INSIDE_MARKER,
    asked_in_vacuum,
    diverging_element,
    signed_distances,
)
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.solvers.si import solves_backwards_in_si
from app.services.law_binding.fit import (
    Fit,
    Question,
    Subject,
    admits,
    named_strength,
    only_strongest_fit,
    read_question,
    variable_kind,
)
from app.services.law_binding.inverse import (
    answered_by_its_own_law,
    can_solve_for,
    solved_for,
    stated_result,
    stated_strength,
    twins,
)
from app.services.law_binding.model_read import excluded
from app.services.law_binding.roles import contradicts, counterparts, variable_role
from app.services.law_binding.spec import FormulaSpec
from app.services.law_binding.units import dimension_of
from app.services.law_binding.words import implied_value

# Reading a paste full of numbers would cost every chat turn.
_MAX_GIVENS = 16
# A second request in the same message ("... and tell me a joke") is not a
# question the verified answer finishes.
_SECOND_REQUEST = re.compile(
    r"\b(?:and|also|then)\s+(?:also\s+)?"
    r"(?:tell|explain|show|write|give|convert|calculate|compute|solve|draw|plot|describe)\b",
    re.IGNORECASE,
)
# "Calculate his average speed and write the correct unit of speed" (a Class 8 book,
# 2026-10-30): the unit is part of the answer the card gives, not a second request.
# The spaces start after a comma (dropped with them), a word (``\b``) or another mark (kept,
# ``drop_unit_request``), never inside a run of spaces: ``,?\s+`` read a long run again from
# each of its spaces (CodeQL py/polynomial-redos). Only a request at the very start of the
# text, after spaces, is no longer dropped; a question never starts that way.
_UNIT_REQUEST = re.compile(
    r"(?:,|\b|(?P<mark>[^\w\s,]))\s+(?:and|also|then)\s+(?:also\s+)?"
    r"(?:write|give|state|mention|name)\s+(?:down\s+)?"
    r"(?:(?:the|its|his|her|their)\s+)?(?:(?:correct|proper|right|appropriate|SI|S\.I\.)\s+)?"
    r"units?(?:\s+of\s+(?:the\s+)?[a-z]+(?:\s+[a-z]+)?)?(?=\s*[.?!]|\s*$)",
    re.IGNORECASE,
)


def drop_unit_request(text: str) -> str:
    """``text`` without "and write the correct unit": the card states the unit."""
    return _UNIT_REQUEST.sub(lambda match: match["mark"] or "", text)


PHYSICS_SUBJECT = Subject(units=PHYSICS_UNITS, fallback=fallback_value, unit_of=si_unit)
_NORTH_SOUTH = re.compile(r"\b(?:north|south)(?:wards?|bound|erly)?\b")
_EAST_WEST = re.compile(r"\b(?:east|west)(?:wards?|bound|erly)?\b")
# A direction between the axes, a bearing or a stated angle is not a right angle.
_NOT_ALONG_AN_AXIS = re.compile(
    r"\b(?:north|south)[\s-]*(?:east|west)|\bbearing\b|\d\s*(?:°|degrees?\b|deg\b)"
)


# An angle stated with its number: "at 30°", "30 degrees". A temperature in degrees is
# not one ("20 °C", "20 degrees Celsius").
_STATED_ANGLE = re.compile(
    r"\d\s*(?:°(?!\s*[CFK]\b)|deg(?:rees?)?\b(?!\s*(?:c|f|k|celsius|fahrenheit|kelvin)\b))",
    re.IGNORECASE,
)


def states_an_angle(text: str) -> bool:
    """The question states an angle with its number."""
    return _STATED_ANGLE.search(text) is not None


def crosswise(lower: str) -> bool:
    """One direction on each compass axis and nothing between them: north and east."""
    return (
        _NORTH_SOUTH.search(lower) is not None
        and _EAST_WEST.search(lower) is not None
        and _NOT_ALONG_AN_AXIS.search(lower) is None
    )


def bind_physics_intent(text: str) -> PhysicsIntent | None:
    """The one catalog operation this question states and asks for, or None.

    The word checks run first, so text that names no operation's ask costs a
    few regex searches and never reads units. Detection calls this on every
    chat turn.
    """
    text = drop_unit_request(text)
    clause = ask_clause(text)
    if clause is None or _SECOND_REQUEST.search(text):
        return None
    named = [(spec, spec, strength) for spec, strength in named_laws(text, clause)]
    if not named:
        return None
    unit = asked_unit(text)
    question = read_question(
        text,
        clause,
        PHYSICS_UNITS,
        max_givens=_MAX_GIVENS,
        asked=frozenset(asked_dimensions(text)),
        asked_in=dimension_of(unit_expression(unit) or "") if unit else None,
    )
    if question is None:
        return None
    strongest = only_strongest_fit(named, question, PHYSICS_SUBJECT)
    if strongest is None:
        return None
    _, chosen = strongest
    intent = _intent(chosen.spec, chosen)
    # An expression law refuses outside its range as it solves; a hand-written one is
    # checked here, or a level launch with no height would read as a flight from the ground.
    if intent is None or (
        chosen.spec.expression is None and not holds_its_range(chosen.spec, intent)
    ):
        return None
    return intent


def _intent(spec: FormulaSpec, chosen: Fit) -> PhysicsIntent | None:
    """The filled law as an intent of the catalog operation ``spec``; None when refused."""
    try:
        return PhysicsIntent(
            # The catalog's kind is a str; the model validates it against its Literal.
            kind=spec.kind,  # type: ignore[arg-type]
            physics_op=spec.id,
            physics_params=chosen.params,
            physics_units=chosen.units,
        )
    except ValueError:
        return None


def bind_solved_for(text: str) -> PhysicsIntent | None:
    """The one catalog law whose result the question states, solved for the quantity it
    asks (``law_binding.inverse``), or None.

    "An engine does 400 J of work with a force of 80 N. How far does the cart move?" states
    W and asks s: W = Fs solved for s. The law is named by its result, stated in the law's
    own words ("of work", "a density of"), as an ask names a law the usual way; the asked
    quantity is the law's one input of the asked kind. Only a question no law answers as its
    own result is read so (``extract``), so no question answered that way changes.
    """
    text = drop_unit_request(text)
    clause = ask_clause(text)
    asked = frozenset(asked_dimensions(text))
    if clause is None or len(asked) != 1 or _SECOND_REQUEST.search(text):
        return None
    question = read_question(text, clause, PHYSICS_UNITS, max_givens=_MAX_GIVENS, asked=asked)
    if question is None:
        return None
    end = asked_end(text, clause)
    stating = _laws_stating_their_result(text, question)
    others = _admitted(text) if stating else ()
    named = [
        (spec, solved, strength)
        for spec, strength in stating
        for solved in _solved_for_the_ask(spec, next(iter(asked)), end, question.lower, others)
    ]
    strongest = only_strongest_fit(named, question, PHYSICS_SUBJECT) if named else None
    if strongest is None:
        return None
    spec, chosen = strongest
    # The law's own id: the reply names the law, its symbols and its picture as ever.
    return _intent(spec, chosen)


def _laws_stating_their_result(text: str, question: Question) -> list[tuple[FormulaSpec, int]]:
    """Each law solved as arithmetic whose result the question states in the law's own
    words, with how strongly: the longest of its asks written beside a value of its kind."""
    lower = text.lower()
    cue_text = _cue_text(text, lower)
    only_water = names_only_water(lower)
    excluded = _with_markers(lower)
    found = []
    for spec in _bindable():
        stated = stated_result(spec)
        if (
            stated is None
            or spec.binding is None
            or not (only_water or spec.id not in WATER_ONLY)
            or not admits(spec.binding, excluded, cue_text=cue_text)
        ):
            continue
        strength = stated_strength(stated, question, PHYSICS_UNITS)
        if strength:
            found.append((spec, strength))
    return found


def _admitted(text: str) -> tuple[FormulaSpec, ...]:
    """The catalog laws this question's words leave in play: its cues said, nothing it
    excludes. A law with no binding is never ruled out by words."""
    lower = text.lower()
    cue_text = _cue_text(text, lower)
    excluded = _with_markers(lower)
    return tuple(
        law
        for law in CATALOG.values()
        if law.binding is None or admits(law.binding, excluded, cue_text=cue_text)
    )


def _solved_for_the_ask(
    spec: FormulaSpec,
    asked: str,
    end: AskedEnd | None,
    lower: str,
    others: tuple[FormulaSpec, ...],
) -> list[FormulaSpec]:
    """The law solved for each of its inputs of the asked kind that SymPy can solve it for.

    An input the words already state ("from rest") is not the one asked, nor is one at the
    other end of the change from the end the question asks about, nor one another law the
    question leaves in play (``others``) gives from the same quantities
    (``answered_by_its_own_law``): capacitors in series answer nothing about two in
    parallel, which the question says they are. Inputs that play the same part (two lenses
    in contact) are one unknown, solved for once: solved for each, "the power of the other
    lens" was two equal readings, and declined.
    """
    alike = twins(spec)
    found = []
    twin_solved = False
    for variable in spec.variables:
        if (
            not variable.visible
            or variable_kind(variable) != asked
            or implied_value(variable, lower) is not None
            or (end is not None and variable_role(variable) not in (None, end.role))
            or answered_by_its_own_law(spec, variable, others)
            or (twin_solved and variable.name in alike)
        ):
            continue
        solved = solved_for(spec, variable.name)
        solves = can_solve_for(spec, variable.name) and solves_backwards_in_si(spec)
        if solved is not None and solves:
            found.append(solved)
            twin_solved = twin_solved or variable.name in alike
    return found


def named_laws(text: str, clause: str) -> list[tuple[FormulaSpec, int]]:
    """Every catalog law the asked clause names, with how strongly, as the question's
    own words allow it (its cues, its excludes, water named alone)."""
    lower = text.lower()
    cue_text = _cue_text(text, lower)
    only_water = names_only_water(lower)
    # "The mirror is convex": a law that excludes a diverging element excludes it, however
    # the question words it.
    excluded = _with_markers(lower)

    def admitted(spec: FormulaSpec) -> bool:
        return (only_water or spec.id not in WATER_ONLY) and (
            spec.binding is not None and admits(spec.binding, excluded, cue_text=cue_text)
        )

    named = [
        (spec, strength)
        for spec in _bindable()
        if spec.binding is not None
        and (only_water or spec.id not in WATER_ONLY)
        and (
            strength := named_strength(
                spec.binding, clause, excluded, PHYSICS_UNITS, cue_text=cue_text
            )
        )
    ]
    end = asked_end(text, clause)
    return named if end is None else _at_the_asked_end(named, end, admitted)


def _cue_text(text: str, lower: str) -> str:
    """The question as the cues read it, with each phrase a cue is read from added."""
    # "0.8c" is a speed of light: the phrase relativity's cues are written as.
    cue_text = f"{lower} speed of light" if FRACTION_OF_C.search(lower) else lower
    # "flies due north … a wind blows from west to east": one direction on each
    # compass axis is a right angle, the cue the perpendicular laws are written with.
    if crosswise(lower):
        cue_text = f"{cue_text} crosswise"
    # A stated angle is the cue a launch at an angle is written with (``AT_AN_ANGLE``).
    if states_an_angle(text):
        cue_text = f"{cue_text} {AT_AN_ANGLE}"
    return cue_text


def _at_the_asked_end(
    named: list[tuple[FormulaSpec, int]],
    end: AskedEnd,
    admitted: Callable[[FormulaSpec], bool],
) -> list[tuple[FormulaSpec, int]]:
    """The named laws whose result is at the asked end, each other one's place taken by
    its counterpart there (``law_binding.roles``).

    "How fast was it going at first?" names v = u + at by "how fast"; its starting
    speed is u = v - at's, named as strongly. A counterpart still needs the question's
    cues and nothing it excludes.
    """
    kept = {
        spec.id: (spec, strength)
        for spec, strength in named
        if not contradicts(spec, end.role, end.dimension)
    }
    for spec, strength in named:
        if not contradicts(spec, end.role, end.dimension):
            continue
        for law in counterparts(spec, end.role, _bindable()):
            if law.id not in kept and admitted(law):
                kept[law.id] = (law, strength)
    return list(kept.values())


def asks_another_thing(text: str) -> bool:
    """A second request ("... and tell me a joke") the verified answer does not finish."""
    return _SECOND_REQUEST.search(text) is not None


def bindable_of_kind(kind: str) -> tuple[FormulaSpec, ...]:
    """The catalog laws of one kind the binder can fill."""
    return tuple(spec for spec in _bindable() if spec.kind == kind)


def _with_markers(lower: str) -> str:
    """The question as the excludes read it: a convex mirror or a concave lens, however it
    is worded, is marked "diverging", a distance given its sign is marked "signed", a
    speed that changes, however it is said, is marked for the constant-speed laws, light
    that starts inside a medium or is asked about in air for the laws that start from air,
    a force that is not the net one for m = F/a, and a body that spins as it rolls for the
    laws of a body that only moves along."""
    if signed_distances(lower):
        lower = f"{lower} signed"
    if not constant_speed_laws_hold(lower):
        lower = f"{lower} {SPEED_CHANGE_MARKER}"
    clause = ask_clause(lower)
    if light_starts_inside(lower) or (clause is not None and asked_in_vacuum(clause)):
        lower = f"{lower} {LIGHT_INSIDE_MARKER}"
    if others_share_the_force(lower):
        lower = f"{lower} {NOT_NET_FORCE_MARKER}"
    if (FRACTION_OF_C.search(lower) or "relativ" in lower) and not adds_speeds_across_frames(lower):
        lower = f"{lower} {FRAMES_UNREAD_MARKER}"
    # A rolling ball's spin is no part of the translational energy a question asks for.
    if rolling_body(lower) and "translational" not in (clause or ""):
        lower = f"{lower} {ROLLING_BODY_MARKER}"
    return f"{lower} diverging" if diverging_element(lower) else lower


def ruled_out(spec: FormulaSpec, text: str) -> bool:
    """The question's own words rule this law out, as the binder reads them: more than
    water named for a law about water alone, or a word its binding excludes."""
    lower = text.lower()
    if spec.id in WATER_ONLY and not names_only_water(lower):
        return True
    return excluded(spec.binding, _with_markers(lower))


@lru_cache(maxsize=1)
def _bindable() -> tuple[FormulaSpec, ...]:
    return tuple(spec for spec in CATALOG.values() if spec.binding is not None)

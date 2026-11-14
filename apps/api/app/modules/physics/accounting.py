"""Numeric accountability: a verified solve may not skip a competing given.

The extractors bind values by keyword nearness. When a question states two
quantities of the kind a formula uses and the solve binds only one, the
keyword chose: "from 20 °C to 80 °C" became ΔT = 20, and "a KE at 3 m/s and
at 4 m/s" answered only the first. Such a solve is declined, not verified.

A quantity of a kind the formula never uses is a distractor and stays
allowed: a ball's mass does not change its fall time. A value the extractor
derived by adding or subtracting givens accounts for them: currents of 2 A
and 3 A entering a junction are the 5 A it binds, and 80 °C and 20 °C are
the 60 K it heats by. Parallel resistances account the same way: 4 Ω and
12 Ω are the 3 Ω a current binds. A value that a given states outright is
read, not derived, so it accounts for no other given.
"""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations, product

from app.modules.physics.bodies import orbiting_body_masses
from app.modules.physics.extractors.unit_patterns import NUMBER
from app.modules.physics.givens import ANGLE, Given, scan_givens, unit_dimension, unit_expression
from app.modules.physics.net_force import friction_coefficients, states_net_force
from app.modules.physics.schemas import PhysicsIntent
from app.modules.physics.set_aside import uses_set_aside_part
from app.modules.physics.solvers.si import PARAM_SI_DIMENSIONS, to_si
from app.services.law_binding.units import dimension_of
from app.services.number_text import count_word_pattern, number_word_value
from app.services.solving import SolveServiceError

logger = logging.getLogger(__name__)

# A stated g is a setting for whichever law needs it, not a competing given.
_GRAVITY_SETTING = re.compile(
    rf"\b(?:g\s*=|gravity\s*(?:of|is|=)?)\s*{NUMBER}(?:\s*m/s\^?2)?",
    re.IGNORECASE,
)
# Laws about a central body alone, whose results no orbiting or standing body's mass changes.
_CENTRAL_ONLY = frozenset(
    {"orbital_velocity", "escape_velocity", "surface_gravity", "gravitational_potential"}
)
# Derived values are sums or differences of a few givens; more is a guess.
_MAX_OPERANDS = 4
_MAX_SAME_KIND = 6
_OHM = unit_dimension("ohm")
_OHM_DIMENSION = None if _OHM is None else _OHM[0]


def _kind(expression: str) -> str:
    reading = unit_dimension(expression)
    if reading is None:
        raise RuntimeError(f"no dimension for {expression}")
    return reading[0]


_LENGTH = _kind("meter")
# Kinds that set the situation itself. Left out, a law answers another question:
# a push up an incline, a speed and a radius over a hump, a rolling body's size.
# A stated acceleration too: "ends at 20 m/s after accelerating at 2 m/s² over 75 m" is
# not d/v (3.75 s), which never reads it; it is 5 s.
# An energy given too: "friction does 100 J of work" changes the speed it ends with.
_SITUATION_KINDS = frozenset(
    {
        _kind("newton"),
        _kind("meter / second"),
        _kind("meter / second ** 2"),
        _LENGTH,
        ANGLE,
        _kind("joule"),
    },
)
_TIME = _kind("second")
# A time that names the moment the asked state holds: "after 2 s", "at t = 2 s", "3 s later",
# "2 s after launch". Left out, a law answers the state at another moment (the top height
# for "how high after 2 s"). A time that says how long something lasted ("in 5 s", "held for
# a second", "1 s after another ball") may belong to another part or another event.
_MOMENT_BEFORE = re.compile(r"\b(?:after|at(?:\s+t(?:ime)?\s*=)?|when\s+t\s*=)\s*$", re.IGNORECASE)
_MOMENT_AFTER = re.compile(
    r"\s*(?:later\b|after\s+(?:launch|release|it\b|being\b"
    r"|the\s+(?:launch|throw|kick|release|start)\b))",
    re.IGNORECASE,
)
# "a 2 m long plank", "a 30 cm wide box": a size, not where anything is.
_SIZE_ONLY = re.compile(
    r"\s*(?:[a-zA-Zµμ]+\s*)?(?:long|tall|wide|thick|deep|in\s+(?:length|diameter|width))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class _Param:
    dimension: str
    raw: float
    si: float | None
    # SI units per written unit; a difference ignores any offset (°C is 1 K).
    scale: float | None


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-12)


def _param_dimension(key: str) -> str | None:
    expression = PARAM_SI_DIMENSIONS.get(key)
    if expression is None:
        return None
    if key.startswith("angle") or expression in {"radian", "degree"}:
        return ANGLE
    return dimension_of(expression)


def _params(intent: PhysicsIntent) -> list[_Param]:
    units = intent.physics_units or {}
    params: list[_Param] = []
    for key, value in (intent.physics_params or {}).items():
        dimension = _param_dimension(key)
        if dimension is None:
            continue
        unit = units.get(key, "")
        params.append(
            _Param(
                dimension, value, _in_si(value, dimension, key, unit), _scale(dimension, key, unit)
            )
        )
    return params


def param_readings(intent: PhysicsIntent) -> list[tuple[str, float | None]]:
    """Each bound value's dimension and SI value."""
    return [(param.dimension, param.si) for param in _params(intent)]


def _in_si(value: float, dimension: str, key: str, unit: str) -> float | None:
    if dimension == ANGLE:
        return value if unit.lower().startswith("rad") else math.radians(value)
    try:
        return to_si(value, unit, expected_key=key)
    except SolveServiceError:
        return None


def _scale(dimension: str, key: str, unit: str) -> float | None:
    one, zero = _in_si(1.0, dimension, key, unit), _in_si(0.0, dimension, key, unit)
    return None if one is None or zero is None else one - zero


def _given_scale(given: Given) -> float | None:
    expression = unit_expression(given.unit)
    reading = None if expression is None else unit_dimension(expression)
    return None if reading is None else reading[1]


def _same_scale(given: Given, param: _Param) -> bool:
    """Whether the two values are written in units of one size: 3 km/h is not 3 m/s."""
    scale = _given_scale(given)
    return scale is None or param.scale is None or _same(scale, param.scale)


def _bound(given: Given, params: list[_Param]) -> bool:
    # Magnitudes: extractors carry direction as a sign ("5 m/s downward" is -5).
    # The written numbers may match only in units of one size; otherwise the
    # SI values must, or "3 km/h and 3 m/s" would bind both with one value.
    return any(
        (_same_scale(given, param) and _same(abs(given.value), abs(param.raw)))
        or (given.si is not None and param.si is not None and _same(abs(given.si), abs(param.si)))
        for param in params
    )


def _parallel_of(values: list[float]) -> float | None:
    """1 / (1/R1 + 1/R2 + ...). Nonpositive parts are not a resistor network."""
    if len(values) < 2 or any(value <= 0 for value in values):
        return None
    return 1.0 / sum(1.0 / value for value in values)


def _derived(given: Given, others: list[Given], params: list[_Param]) -> bool:
    """Whether a bound value is a signed sum of this given and a few others.

    Resistances may instead be combined in parallel. That check stays on the
    ohm dimension, so 4 m and 12 m are not "derived" by a length of 3 m. Written
    numbers add up only in one unit: 4 kΩ - 2 kΩ "derived" a 2 Ω resistor and a
    loop current came out 2 A for 2 mA (review 2026-11-07).
    """
    if len(others) > _MAX_SAME_KIND:
        return False
    si_targets = [abs(param.si) for param in params if param.si is not None]
    for size in range(1, _MAX_OPERANDS):
        for group in combinations(others, size):
            operands = (given, *group)
            targets = [
                abs(param.raw)
                for param in params
                if all(_same_scale(item, param) for item in operands)
            ]
            for signs in product((1.0, -1.0), repeat=len(group)):
                raw = given.value + sum(s * g.value for s, g in zip(signs, group, strict=True))
                if any(_same(abs(raw), target) for target in targets):
                    return True
                if all(item.si is not None for item in operands):
                    si = (given.si or 0.0) + sum(
                        s * (g.si or 0.0) for s, g in zip(signs, group, strict=True)
                    )
                    if any(_same(abs(si), target) for target in si_targets):
                        return True
            if given.dimension != _OHM_DIMENSION:
                continue
            raw_parallel = _parallel_of([given.value, *(item.value for item in group)])
            if raw_parallel is not None and any(_same(raw_parallel, target) for target in targets):
                return True
            if all(item.si is not None for item in operands):
                si_parallel = _parallel_of([item.si or 0.0 for item in operands])
                if si_parallel is not None and any(
                    _same(si_parallel, target) for target in si_targets
                ):
                    return True
    return False


_COUNT_BEFORE = re.compile(
    rf"\b({count_word_pattern(low=2, high=6)})\s+(?:identical\s+|equal\s+)?\Z", re.IGNORECASE
)


def _from_the_other_line(given: Given, params: list[_Param]) -> bool:
    """An angle bound as 90° less: "40° to the surface" is 50° from the normal."""
    return given.dimension == ANGLE and any(
        _same(param.raw, 90.0 - given.value) for param in params if param.dimension == ANGLE
    )


def _counted_network(given: Given, text: str, params: list[_Param]) -> bool:
    """Three 9 Ω resistors are the 27 Ω or 3 Ω a network binds."""
    if given.dimension != _OHM_DIMENSION or given.si is None:
        return False
    counted = _COUNT_BEFORE.search(text[max(0, given.start - 24) : given.start])
    if counted is None:
        return False
    count = number_word_value(counted.group(1)) or 0
    return any(
        param.si is not None
        and (_same(param.si, given.si * count) or _same(param.si, given.si / count))
        for param in params
    )


def _clearly_irrelevant(given: Given, text: str) -> bool:
    """A length that only describes an object's size: "a 2 m long plank".

    Only for a solve that uses no length at all; a length it uses is bound or
    competing above.
    """
    return given.dimension == _LENGTH and _SIZE_ONLY.match(text, given.end) is not None


def _a_moment(given: Given, text: str) -> bool:
    """A time naming when the asked state holds ("after 2 s", "3 s later"), not how long
    something lasted."""
    return (
        _MOMENT_BEFORE.search(text[: given.start]) is not None
        or _MOMENT_AFTER.match(text, given.end) is not None
    )


def _unused_situation(given: Given, params: list[_Param], text: str) -> bool:
    """A stated force, speed, acceleration, length, angle, energy or moment of a kind this
    solve never uses.

    Those change the situation: a 30 N push along a slope, a car's speed and
    the radius of the hump it crosses, a rolling sphere's radius, the 100 J
    friction takes, the 2 s after which a height is asked. A law that leaves one
    out answers a different question. A mass, a temperature or a time that only
    says how long something lasted beside a law that needs none is still a
    distractor.
    """
    situation = (
        _a_moment(given, text) if given.dimension == _TIME else given.dimension in _SITUATION_KINDS
    )
    if not situation:
        return False
    if any(param.dimension == given.dimension for param in params):
        return False
    if given.dimension == ANGLE and any(_same(abs(given.value), abs(p.raw)) for p in params):
        # "by 10 degrees" read as a temperature rise: the same number, bound as
        # the kind the extractor read it as.
        return False
    return not _clearly_irrelevant(given, text)


def competing_given(intent: PhysicsIntent, text: str) -> Given | None:
    """A stated quantity of a kind this solve uses that it neither bound nor derived.

    A stated force, speed, length or angle the solve does not use at all is
    refused too (``_unused_situation``).
    """
    return competing_given_of((intent,), text)


def competing_given_of(intents: Sequence[PhysicsIntent], text: str) -> Given | None:
    """``competing_given`` over several laws applied in turn (``chain_solve``): one may
    use some stated values and the next the rest, so every one must be used by some."""
    friction = _unused_friction(intents, text)
    if friction is not None:
        return friction
    params = [param for intent in intents for param in _params(intent)]
    op = ", ".join(intent.physics_op or "" for intent in intents)
    settings = [match.span() for match in _GRAVITY_SETTING.finditer(text)]
    givens = [
        given
        for given in scan_givens(text)
        if given.dimension is not None
        and not any(start <= given.start < end for start, end in settings)
    ]
    # "A 500 kg satellite orbits 400 km above the Earth": what orbits is no input of a law
    # about the body it orbits (``bodies.ORBITING_BODY_WORDS``), and its mass changes no
    # answer of one. Only such a law: the force between two bodies takes both masses.
    if all((intent.physics_op or "") in _CENTRAL_ONLY for intent in intents):
        orbiting = orbiting_body_masses(text)
        givens = [
            given
            for given in givens
            if not any(start <= given.start < end for start, end in orbiting)
        ]
    for given in givens:
        if _unused_situation(given, params, text):
            logger.info(
                "physics solve declined: %s %s is of a kind op=%s never uses",
                given.value,
                given.unit,
                op,
            )
            return given
        same_kind = [param for param in params if param.dimension == given.dimension]
        if not same_kind or _bound(given, same_kind):
            continue
        others = [
            other for other in givens if other is not given and other.dimension == given.dimension
        ]
        # Only a value no given states can be a derivation. Otherwise 4 - 7
        # "derives" a stated 3 m/s by coincidence and the 4 and 7 go unasked.
        derived = [
            param for param in same_kind if not any(_bound(other, [param]) for other in others)
        ]
        if (
            _derived(given, others, derived)
            or _counted_network(given, text, derived)
            or _from_the_other_line(given, derived)
        ):
            continue
        logger.info(
            "physics solve declined: %s %s left unbound by op=%s",
            given.value,
            given.unit,
            op,
        )
        return given
    return None


# The inputs that are a coefficient of friction, and the kinds a law of forces has.
_FRICTION_INPUTS = ("mu", "mu_s")
_FORCE_KINDS = frozenset({_kind("newton"), _kind("meter / second ** 2")})


def _unused_friction(intents: Sequence[PhysicsIntent], text: str) -> Given | None:
    """A coefficient of friction the question states that a law of forces leaves unused.

    A pure number is otherwise a distractor, but a stated μ says friction acts on the
    motion: "a 60 N push with μ = 0.2 gives 1 m/s²" was m = F/a = 60 kg, for 20.3 kg. A law
    with no force and no acceleration in it (½mv² of a box sliding at 3 m/s) is not about
    friction, μ = 0 says none acts, and a force the question calls the net force already
    holds it. A question that says to ignore friction (``set_aside``) has none.
    """
    params = [param for intent in intents for param in _params(intent)]
    if any(
        name in (intent.physics_params or {}) for intent in intents for name in _FRICTION_INPUTS
    ) or not any(param.dimension in _FORCE_KINDS for param in params):
        return None
    starts = [start for start, value in friction_coefficients(text) if value > 0]
    if (
        not starts
        or uses_set_aside_part(dict.fromkeys(_FRICTION_INPUTS, 0.0), text)
        or states_net_force(text.lower())
    ):
        return None
    stated = next((given for given in scan_givens(text) if given.start in starts), None)
    if stated is not None:
        logger.info("physics solve declined: a stated coefficient of friction is never used")
    return stated


# A time measured from another event: "1 s after another ball", "1 s before it starts to
# fall". Read as the time since the start, a ball dropped from 20 m "1 s after another"
# hit the ground at 9.81 m/s for 19.8.
_TIME_OFFSET = re.compile(
    # "falls for 3 s before it hits the ground" is a duration, not an offset.
    rf"(?<!for ){NUMBER}\s*(?:s|secs?|seconds?)\s+(?:before|earlier|later\s+than"
    r"|after\s+(?:another|the\s+(?:other|first|second|bell|whistle|signal)))\b",
    re.IGNORECASE,
)


def time_from_another_event(intent: PhysicsIntent, text: str) -> bool:
    """The solve takes a time the question measures from another event than its start."""
    return "t" in (intent.physics_params or {}) and _TIME_OFFSET.search(text) is not None

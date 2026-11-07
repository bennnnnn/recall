"""Every scaling follow-up either declines or re-solves to the number the formula gives.

The problems a review found wrong numbers on, crossed with the ways students scale a
given. Each problem lists its givens with the object that owns each and, for a speed,
which end of the change it is; the expected answer is worked here from the problem's own
formula, never read from the solver. (A car "going 30 m/s after accelerating" is left
out: the solver reads its 30 m/s as the starting speed, a fault of the problem's own
reading that a follow-up only inherits.) A follow-up the givens do not decide (an object
that owns nothing, a body the problem never had, a temperature in °C) must decline.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from app.modules.physics.followup import _answers, physics_followup_problem
from app.modules.physics.givens import PHYSICS_UNITS
from app.services.law_binding.fit import read_givens

G = 9.81
R_GAS = 8.314462618


@dataclass(frozen=True)
class Param:
    key: str
    value: float
    names: frozenset[str]
    owner: str | None = None
    role: str | None = None


@dataclass(frozen=True)
class Problem:
    text: str
    params: tuple[Param, ...]
    formula: Callable[[dict[str, float]], float]


def _p(
    key: str, value: float, *names: str, owner: str | None = None, role: str | None = None
) -> Param:
    return Param(key, value, frozenset(names), owner, role)


_SPEED = ("speed", "velocity")
PROBLEMS = {
    "drop": Problem(
        "A 2 kg ball is dropped from 10 m. Find its speed just before it hits the ground.",
        (_p("m", 2, "mass", owner="ball"), _p("h", 10, "height")),
        lambda v: math.sqrt(2 * G * v["h"]),
    ),
    "driver": Problem(
        "A 70 kg driver sits in a car braking at 5 m/s^2. Find the force on the driver.",
        (_p("m", 70, "mass", owner="driver"), _p("a", 5, "acceleration", owner="car")),
        lambda v: v["m"] * v["a"],
    ),
    "elevator": Problem(
        "A 60 kg person stands in an elevator accelerating upward at 2 m/s^2. "
        "Find the normal force on the person.",
        (_p("m", 60, "mass", owner="person"), _p("a", 2, "acceleration", owner="elevator")),
        lambda v: v["m"] * (G + v["a"]),
    ),
    "ramp": Problem(
        "A 5 kg box rests on a ramp inclined at 30 degrees. Find the normal force on the box.",
        (_p("m", 5, "mass", owner="box"), _p("t", 30, "angle", owner="ramp")),
        lambda v: v["m"] * G * math.cos(math.radians(v["t"])),
    ),
    "swung": Problem(
        "A 0.5 kg ball tied to a 2 m string is swung in a horizontal circle at 4 m/s. "
        "Find the tension.",
        (
            _p("m", 0.5, "mass", owner="ball"),
            _p("r", 2, "radius", "length", owner="string"),
            _p("v", 4, *_SPEED, owner="ball"),
        ),
        lambda v: v["m"] * v["v"] ** 2 / v["r"],
    ),
    "table": Problem(
        "A ball rolls off a 1.2 m high table at 3 m/s. How far from the table does it land?",
        (_p("h", 1.2, "height", owner="table"), _p("v", 3, *_SPEED, owner="ball")),
        lambda v: v["v"] * math.sqrt(2 * v["h"] / G),
    ),
    "cliff": Problem(
        "A stone is dropped from a 80 m cliff. How long to hit the water?",
        (_p("h", 80, "height", owner="cliff"),),
        lambda v: math.sqrt(2 * v["h"] / G),
    ),
    "energy": Problem(
        "A 2 kg ball moves at 3 m/s. Find its kinetic energy.",
        (_p("m", 2, "mass", owner="ball"), _p("v", 3, *_SPEED, owner="ball")),
        lambda v: 0.5 * v["m"] * v["v"] ** 2,
    ),
    "ohm": Problem(
        "A 12 V battery drives a 4 ohm resistor. Find the current.",
        (
            _p("V", 12, "voltage", owner="battery"),
            _p("R", 4, "resistance", owner="resistor"),
        ),
        lambda v: v["V"] / v["R"],
    ),
    "to_speed": Problem(
        "A car starts from rest and accelerates at 3 m/s^2 until it reaches 30 m/s. "
        "How long does it take?",
        (_p("a", 3, "acceleration", owner="car"), _p("v", 30, *_SPEED, role="final")),
        lambda v: v["v"] / v["a"],
    ),
    "from_to": Problem(
        "A car accelerates from 10 m/s to 30 m/s in 5 s. Find its acceleration.",
        (
            _p("u", 10, *_SPEED, role="initial"),
            _p("v", 30, *_SPEED, role="final"),
            _p("t", 5, "time"),
        ),
        lambda v: (v["v"] - v["u"]) / v["t"],
    ),
    "train": Problem(
        "A train slows down to 10 m/s from 30 m/s over 200 m. Find its deceleration.",
        (
            _p("v", 10, *_SPEED, role="final"),
            _p("u", 30, *_SPEED, role="initial"),
            _p("s", 200, "distance"),
        ),
        lambda v: (v["v"] ** 2 - v["u"] ** 2) / (2 * v["s"]),
    ),
    "skier": Problem(
        "A 60 kg skier starts from rest at the top of a 20 m high slope. "
        "Find her speed at the bottom.",
        (_p("m", 60, "mass", owner="skier"), _p("h", 20, "height", owner="slope")),
        lambda v: math.sqrt(2 * G * v["h"]),
    ),
    "braking": Problem(
        "A 1500 kg car moving at 20 m/s brakes to a stop in 5 s. Find the braking force.",
        (
            _p("m", 1500, "mass", owner="car"),
            _p("v", 20, *_SPEED, owner="car", role="initial"),
            _p("t", 5, "time"),
        ),
        lambda v: v["m"] * v["v"] / v["t"],
    ),
    "gas_c": Problem(
        "Find the pressure of 2 mol of an ideal gas in a 10 L container at 27 °C.",
        (
            _p("n", 2, "amount"),
            _p("V", 0.010, "volume", owner="container"),
            _p("T", 300.15, "temperature"),
        ),
        lambda v: v["n"] * R_GAS * v["T"] / v["V"],
    ),
}

# A follow-up and its true reading: (quantity, owner, role, factor); None for a line
# whose meaning is no given of the problem ("it went twice as far": the answer).
Reading = tuple[str, str | None, str | None, float] | None
TEMPLATES: list[tuple[str, Reading]] = [
    ("what if the mass doubled", ("mass", None, None, 2)),
    ("with twice the mass", ("mass", None, None, 2)),
    ("what if it was twice as heavy", ("mass", None, None, 2)),
    ("what if the earth had twice the mass", ("mass", "earth", None, 2)),
    ("what if we had twice the mass", ("mass", "we", None, 2)),
    ("what if the height doubled", ("height", None, None, 2)),
    ("what if it was twice as high", ("height", None, None, 2)),
    ("what if the distance doubled", ("distance", None, None, 2)),
    ("what if it went twice as far", None),
    ("what if the speed was twice as high", ("speed", None, None, 2)),
    ("what if it was going twice as fast", ("speed", None, None, 2)),
    ("what if the initial speed doubled", ("speed", None, "initial", 2)),
    ("what if the final speed doubled", ("speed", None, "final", 2)),
    ("what if the acceleration doubled", ("acceleration", None, None, 2)),
    ("what if it accelerated twice as fast", ("acceleration", None, None, 2)),
    ("what if the voltage were doubled", ("voltage", None, None, 2)),
    ("what if I halve the resistance", ("resistance", None, None, 0.5)),
    ("what if the angle doubled", ("angle", None, None, 2)),
    ("what if the radius doubled", ("radius", None, None, 2)),
    ("what if the time was halved", ("time", None, None, 0.5)),
    ("what if the temperature doubled", ("temperature", None, None, 2)),
    ("what if it rolled at double the speed of sound", None),
]
# Said of each object of the problem: the right given only when that object owns it.
OWNER_TEMPLATES: list[tuple[str, str, float]] = [
    ("what if the {o} was twice as heavy", "mass", 2),
    ("what if the {o} had twice the mass", "mass", 2),
    ("what if the mass of the {o} doubled", "mass", 2),
    ("what if the {o} was twice as high", "height", 2),
    ("what if the {o} had twice the acceleration", "acceleration", 2),
]
OBJECTS = (
    "ball",
    "driver",
    "car",
    "person",
    "elevator",
    "box",
    "ramp",
    "string",
    "table",
    "cliff",
    "skier",
    "slope",
    "battery",
    "resistor",
    "container",
)


def _pairs() -> list[tuple[str, str, Reading]]:
    pairs: list[tuple[str, str, Reading]] = []
    for name, problem in PROBLEMS.items():
        pairs += [(name, line, reading) for line, reading in TEMPLATES]
        mentioned = [o for o in OBJECTS if o in problem.text.lower()]
        for template, quantity, factor in OWNER_TEMPLATES:
            for owner in mentioned:
                line = template.format(o=owner)
                pairs.append((name, line, (quantity, owner, None, factor)))
    return pairs


def _expected(problem: Problem, reading: Reading) -> float | None:
    """The answer the reading gives by the problem's formula; None when the problem's
    givens do not decide which one it scales."""
    if reading is None:
        return None
    quantity, owner, role, factor = reading
    found = [
        p
        for p in problem.params
        if quantity in p.names
        and (owner is None or p.owner == owner)
        and (role is None or p.role == role)
    ]
    if len(found) != 1:
        return None
    values = {p.key: p.value for p in problem.params}
    values[found[0].key] *= factor
    return problem.formula(values)


def _si(text: str) -> float:
    answers = _answers(text)
    assert answers, text
    values = [g.si for g in read_givens(answers[0][0], PHYSICS_UNITS) if g.si is not None]
    assert values, answers
    return values[0]


@pytest.mark.parametrize(("problem", "line", "reading"), _pairs())
def test_a_scaling_follow_up_declines_or_gives_the_formulas_number(
    problem: str, line: str, reading: Reading
) -> None:
    spec = PROBLEMS[problem]
    rewritten = physics_followup_problem(line, [("user", spec.text), ("assistant", "...")])
    if rewritten is None:
        return  # declining is always safe: the model answers
    expected = _expected(spec, reading)
    assert expected is not None, f"{line!r} re-solved {rewritten!r}, which the givens don't decide"
    before = spec.formula({p.key: p.value for p in spec.params})
    ratio = _si(rewritten) / _si(spec.text)
    assert ratio == pytest.approx(expected / before, rel=0.02), rewritten


@pytest.mark.parametrize("problem", sorted(PROBLEMS))
def test_each_harness_problem_verifies_as_its_formula_says(problem: str) -> None:
    spec = PROBLEMS[problem]
    worked = spec.formula({p.key: p.value for p in spec.params})
    assert abs(_si(spec.text)) == pytest.approx(abs(worked), rel=0.02)

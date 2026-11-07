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
import re
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from app.modules.physics.followup import physics_followup_problem
from app.modules.physics.givens import PHYSICS_UNITS
from app.modules.physics.verified_answers import answers
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
    # "Two 5 kg masses": the value is more than one body's, so "the mass" is no one given.
    shared: bool = False


@dataclass(frozen=True)
class Problem:
    text: str
    params: tuple[Param, ...]
    formula: Callable[[dict[str, float]], float]
    # The result is a component's own constant (R = V/I, k = F/x, C = Q/V): a change to
    # one given keeps it, and the other given changes with it by the same factor.
    kept: bool = False


def _p(
    key: str,
    value: float,
    *names: str,
    owner: str | None = None,
    role: str | None = None,
    shared: bool = False,
) -> Param:
    return Param(key, value, frozenset(names), owner, role, shared)


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
    # The two-body problems again, one word changed: the value is still one body's.
    "in_elevator": Problem(
        "A 60 kg person in an elevator accelerating upward at 2 m/s^2. "
        "Find the normal force on the person.",
        (_p("m", 60, "mass", owner="person"), _p("a", 2, "acceleration", owner="elevator")),
        lambda v: v["m"] * (G + v["a"]),
    ),
    "in_car": Problem(
        "A 70 kg driver in a car braking at 5 m/s^2. Find the force on the driver.",
        (_p("m", 70, "mass", owner="driver"), _p("a", 5, "acceleration", owner="car")),
        lambda v: v["m"] * v["a"],
    ),
    "is_in_car": Problem(
        "A 70 kg driver is in a car braking at 5 m/s^2. Find the force on the driver.",
        (_p("m", 70, "mass", owner="driver"), _p("a", 5, "acceleration", owner="car")),
        lambda v: v["m"] * v["a"],
    ),
    "on_cart": Problem(
        "A 5 kg box on a cart accelerating at 2 m/s^2. Find the net force on the box.",
        (_p("m", 5, "mass", owner="box"), _p("a", 2, "acceleration", owner="cart")),
        lambda v: v["m"] * v["a"],
    ),
    "load": Problem(
        "A cart carrying a load of 50 kg accelerates at 2 m/s^2. Find the net force on the load.",
        (_p("m", 50, "mass", owner="load"), _p("a", 2, "acceleration", owner="cart")),
        lambda v: v["m"] * v["a"],
    ),
    "trailer": Problem(
        "A 900 kg car pulls a trailer with a force of 2000 N. Find the acceleration of the car.",
        (_p("m", 900, "mass", owner="car"), _p("F", 2000, "force")),
        lambda v: v["F"] / v["m"],
    ),
    "next_to": Problem(
        "A 2 kg ball is moving at 3 m/s next to a car. Find its kinetic energy.",
        (_p("m", 2, "mass", owner="ball"), _p("v", 3, *_SPEED, owner="ball")),
        lambda v: 0.5 * v["m"] * v["v"] ** 2,
    ),
    "hits_cart": Problem(
        "A 2 kg ball moving at 3 m/s hits a cart. Find the kinetic energy of the ball.",
        (_p("m", 2, "mass", owner="ball"), _p("v", 3, *_SPEED, owner="ball")),
        lambda v: 0.5 * v["m"] * v["v"] ** 2,
    ),
    "tows": Problem(
        "A 1000 kg car tows a boat at 20 m/s. Find the car's kinetic energy.",
        (_p("m", 1000, "mass", owner="car"), _p("v", 20, *_SPEED)),
        lambda v: 0.5 * v["m"] * v["v"] ** 2,
    ),
    "moon": Problem(
        "A 70 kg astronaut on the moon jumps at 3 m/s. Find his kinetic energy.",
        (_p("m", 70, "mass", owner="astronaut"), _p("v", 3, *_SPEED, owner="astronaut")),
        lambda v: 0.5 * v["m"] * v["v"] ** 2,
    ),
    "curve": Problem(
        "A 1200 kg car rounds a curve of radius 50 m at 15 m/s. Find the centripetal force.",
        (
            _p("m", 1200, "mass", owner="car"),
            _p("r", 50, "radius", owner="curve"),
            _p("v", 15, *_SPEED, owner="car"),
        ),
        lambda v: v["m"] * v["v"] ** 2 / v["r"],
    ),
    "upward": Problem(
        "A ball is thrown upward at 20 m/s. How high does it go?",
        (_p("v", 20, *_SPEED, owner="ball", role="initial"),),
        lambda v: v["v"] ** 2 / (2 * G),
    ),
    # A wave's speed is the medium's: a new frequency gives a new wavelength, the same speed.
    "string_wave": Problem(
        "A wave on a string has a frequency of 170 Hz and a wavelength of 2 m. Find its speed.",
        (_p("f", 170, "frequency", owner="wave"), _p("w", 2, "wavelength", owner="wave")),
        lambda v: 340.0,
    ),
    "sound": Problem(
        "A sound wave has a frequency of 170 Hz and a wavelength of 2 m. Find its speed.",
        (_p("f", 170, "frequency", owner="wave"), _p("w", 2, "wavelength", owner="wave")),
        lambda v: 340.0,
    ),
    # Two equal masses: "the mass doubled" is one of them or both.
    "two_masses": Problem(
        "Two 5 kg masses are 2 m apart. Find the gravitational force between them.",
        (_p("m", 5, "mass", shared=True), _p("r", 2, "distance")),
        lambda v: 6.674e-11 * v["m"] ** 2 / v["r"] ** 2,
    ),
    # The mass written as another body's than the subject's: "the mass" may be either.
    "satellite": Problem(
        "A satellite orbits Earth at a radius of 7000000 m. The mass of Earth is 6e24 kg. "
        "Find its orbital speed.",
        (
            _p("M", 6e24, "mass", owner="earth", shared=True),
            _p("r", 7e6, "radius", owner="satellite"),
        ),
        lambda v: math.sqrt(6.674e-11 * v["M"] / v["r"]),
    ),
    "planet": Problem(
        "A moon orbits a planet of mass 2e27 kg at a radius of 4e8 m. Find its orbital period.",
        (
            _p("M", 2e27, "mass", owner="planet", shared=True),
            _p("r", 4e8, "radius", owner="moon"),
        ),
        lambda v: 2 * math.pi * math.sqrt(v["r"] ** 3 / (6.674e-11 * v["M"])),
    ),
    # Properties of the object: they stay when what is done to it changes.
    "resistor": Problem(
        "A 12 V battery drives a current of 2 A through a resistor. Find the resistance.",
        (_p("V", 12, "voltage", owner="battery"), _p("I", 2, "current")),
        lambda v: 6.0,
        kept=True,
    ),
    "bulb": Problem(
        "A 60 W bulb runs on 120 V. Find the current.",
        (_p("P", 60, "power", owner="bulb"), _p("V", 120, "voltage")),
        lambda v: v["V"] / (120**2 / 60) if v["P"] == 60 else v["P"] / v["V"],
    ),
    "heater": Problem(
        "A 1000 W heater runs on 230 V. Find its resistance.",
        (_p("P", 1000, "power", owner="heater"), _p("V", 230, "voltage")),
        lambda v: 230**2 / 1000,
    ),
    "spring": Problem(
        "A spring stretches 0.1 m under a 5 N force. Find the spring constant.",
        (_p("x", 0.1, "extension", "length"), _p("F", 5, "force")),
        lambda v: 50.0,
        kept=True,
    ),
    "capacitor": Problem(
        "A capacitor stores a charge of 0.00006 C at 12 V. Find its capacitance.",
        (_p("Q", 6e-5, "charge"), _p("V", 12, "voltage")),
        lambda v: 5e-6,
        kept=True,
    ),
    "metal": Problem(
        "4000 J of heat raises the temperature of 1 kg of a metal by 10 K. "
        "Find the specific heat capacity.",
        (_p("Q", 4000, "heat", "energy"), _p("m", 1, "mass", owner="metal")),
        lambda v: 400.0,
    ),
    "glass": Problem(
        "Light travels at 200000000 m/s in glass. Find the refractive index of the glass.",
        (_p("v", 2e8, *_SPEED, owner="light"),),
        lambda v: 1.5,
    ),
    # An emf and an internal resistance: a change holds the wrong things fixed.
    "emf": Problem(
        "A battery with an emf of 9 V drives 0.5 A through a circuit. "
        "Find the terminal voltage if the internal resistance is 2 ohm.",
        (
            _p("E", 9, "voltage", "emf", shared=True),
            _p("I", 0.5, "current", shared=True),
            _p("r", 2, "resistance", shared=True),
        ),
        lambda v: v["E"] - v["I"] * v["r"],
    ),
    # Counts and sameness anywhere in the sentence.
    "each_sphere": Problem(
        "Each of two spheres has mass 5 kg and they are 2 m apart. "
        "Find the gravitational force between them.",
        (_p("m", 5, "mass", shared=True), _p("r", 2, "distance", shared=True)),
        lambda v: 6.674e-11 * v["m"] ** 2 / v["r"] ** 2,
    ),
    "equal_charges": Problem(
        "Two equal charges of 3e-6 C are 0.5 m apart. Find the force between them.",
        (_p("q", 3e-6, "charge", shared=True), _p("r", 0.5, "distance", shared=True)),
        lambda v: 8.988e9 * v["q"] ** 2 / v["r"] ** 2,
    ),
    "two_resistors": Problem(
        "Two resistors of 4 ohm each are connected in series to a 12 V battery. Find the current.",
        (_p("R", 4, "resistance", shared=True), _p("V", 12, "voltage", shared=True)),
        lambda v: v["V"] / (2 * v["R"]),
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
    # A pronoun may be any body of the problem: it must decline.
    ("what if it was twice as heavy", None),
    ("what if it had twice the mass", None),
    ("what if it was going twice as fast", None),
    ("what if it was thrown twice as fast", ("speed", None, "initial", 2)),
    ("what if the earth had twice the mass", ("mass", "earth", None, 2)),
    ("what if we had twice the mass", ("mass", "we", None, 2)),
    ("what if the height doubled", ("height", None, None, 2)),
    ("what if it was twice as high", None),
    ("what if the distance doubled", ("distance", None, None, 2)),
    ("what if it went twice as far", None),
    ("what if the speed was twice as high", ("speed", None, None, 2)),
    ("what if the initial speed doubled", ("speed", None, "initial", 2)),
    ("what if the final speed doubled", ("speed", None, "final", 2)),
    ("what if the acceleration doubled", ("acceleration", None, None, 2)),
    ("what if it accelerated twice as fast", None),
    ("what if the frequency doubled", ("frequency", None, None, 2)),
    ("what if the wavelength was halved", ("wavelength", None, None, 0.5)),
    ("what if the voltage were doubled", ("voltage", None, None, 2)),
    ("what if I halve the resistance", ("resistance", None, None, 0.5)),
    ("what if the angle doubled", ("angle", None, None, 2)),
    ("what if the radius doubled", ("radius", None, None, 2)),
    ("what if the time was halved", ("time", None, None, 0.5)),
    ("what if the temperature doubled", ("temperature", None, None, 2)),
    ("what if the current doubled", ("current", None, None, 2)),
    ("what if the force doubled", ("force", None, None, 2)),
    ("what if the charge doubled", ("charge", None, None, 2)),
    ("what if the power doubled", ("power", None, None, 2)),
    ("what if the heat doubled", ("heat", None, None, 2)),
    ("what if the resistance doubled", ("resistance", None, None, 2)),
    ("what if the extension doubled", ("extension", None, None, 2)),
    ("what if it rolled at double the speed of sound", None),
]
# Said of each object of the problem: the right given only when that object owns it.
OWNER_TEMPLATES: list[tuple[str, str, float]] = [
    ("what if the {o} was twice as heavy", "mass", 2),
    ("what if the {o} had twice the mass", "mass", 2),
    ("what if the mass of the {o} doubled", "mass", 2),
    ("what if the {o} was twice as high", "height", 2),
    ("what if the {o} had twice the acceleration", "acceleration", 2),
    ("what if the {o} was twice as fast", "speed", 2),
    ("what if the {o} had twice the speed", "speed", 2),
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
    "cart",
    "load",
    "trailer",
    "boat",
    "astronaut",
    "moon",
    "earth",
    "curve",
    "wave",
    "satellite",
    "planet",
    "bulb",
    "heater",
    "spring",
    "capacitor",
    "metal",
    "glass",
    "sphere",
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


def _kept_other(problem: Problem, reading: Reading) -> float | None:
    """The other given's new value when the reading scales one given of a component whose
    constant is kept; None when the reading names no one given of the problem."""
    if reading is None:
        return None
    quantity, _owner, _role, factor = reading
    scaled = [p for p in problem.params if quantity in p.names]
    if len(scaled) != 1 or len(problem.params) != 2:
        return None
    other = next(p for p in problem.params if p is not scaled[0])
    return other.value * factor


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
    # A shared value is certain only when the line names its owner ("the planet had").
    if len(found) != 1 or (found[0].shared and owner is None):
        return None
    values = {p.key: p.value for p in problem.params}
    values[found[0].key] *= factor
    return problem.formula(values)


_SUPERSCRIPT = str.maketrans("⁻⁰¹²³⁴⁵⁶⁷⁸⁹", "-0123456789")
_POWER = re.compile(r"^(?P<a>-?[\d.]+) × 10(?P<n>[⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+) (?P<unit>.+)$")


def _si(text: str) -> float:
    """The verified answer in SI, a power of ten too ("4e5 J"), which read_givens skips."""
    found = answers(text)
    assert found, text
    plain = found[0][0].split(" (")[0]
    power = _POWER.match(plain)
    if power is not None:
        scale = float(power.group("a")) * 10 ** int(power.group("n").translate(_SUPERSCRIPT))
        plain = f"{scale:.6g} {power.group('unit')}".replace("e+", "e")
    values = [g.si for g in read_givens(plain, PHYSICS_UNITS) if g.si is not None]
    if not values:  # "1.5" (an index), "400 J/(kg·K)": the number in the card's own unit
        values = [float(plain.split()[0])]
    return values[0]


@pytest.mark.parametrize(("problem", "line", "reading"), _pairs())
def test_a_scaling_follow_up_declines_or_gives_the_formulas_number(
    problem: str, line: str, reading: Reading
) -> None:
    spec = PROBLEMS[problem]
    rewritten = physics_followup_problem(line, [("user", spec.text), ("assistant", "...")])
    if rewritten is None:
        return  # declining is always safe: the model answers
    if spec.kept:
        other = _kept_other(spec, reading)
        assert other is not None, f"{line!r} re-solved {rewritten!r}, which the givens don't decide"
        assert _si(rewritten) == pytest.approx(other, rel=0.02), rewritten
        return
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

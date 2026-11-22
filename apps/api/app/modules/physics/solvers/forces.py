"""Force solvers: F = ma, rope tension, resultants, a vector resolved, and the Atwood machine."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, replace

from app.modules.physics.display import (
    GIVEN_FIGURES,
    latex_given,
    latex_number,
    latex_unit,
    plain_number,
    plain_unit,
)
from app.modules.physics.schemas import PhysicsIntent, SimulationVector
from app.modules.physics.solvers.arithmetic import latex_num
from app.modules.physics.solvers.force_scenes import (
    _atwood_scene,
    _vector_sum_scene,
    free_body_scene,
    resolution_scene,
)
from app.modules.physics.solvers.results import PhysicsResult, QuantityResult
from app.modules.physics.solvers.si import gravity_of, params_in_si
from app.services.solving import SolveServiceError


def solve_force(intent: PhysicsIntent) -> PhysicsResult:
    p = params_in_si(intent)
    op = intent.physics_op
    # Rope and vector shapes by name; anything else is the F/m/a triangle.
    solver = _OPERATIONS.get(op or "")
    if solver is not None:
        return solver(intent, p)
    return _newton_second_law(intent, p)


# A rope's tension is not m*a, which is exactly the confusion P2 refused
# rather than let ship.
def _tension(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    m = p["m"]
    if m <= 0:
        raise SolveServiceError("mass must be positive")
    g = gravity_of(p)
    a = p.get("a", 0.0)
    if a <= -g:
        raise SolveServiceError("the rope goes slack at or beyond free fall")
    t_val = m * (g + a)
    return PhysicsResult(
        answer=(
            rf"T = m(g + a) = {m:g}({g:g} + {latex_num(a)}) "
            rf"\approx {t_val:.2f} \text{{ N}}"
        ),
        formulas=(r"T = m(g + a)",),
        substitutions=(rf"T = {m:g}({g:g} + {latex_num(a)})",),
        quantities=(QuantityResult("", t_val, "N"),),
        # Two arrows and a mass is the whole of this problem, and seeing
        # them is what makes T = m(g + a) rather than m*a obvious: the rope
        # carries the weight *and* the acceleration.
        simulation_specs=free_body_scene(
            [
                SimulationVector(
                    anchor=[0.0, 0.0],
                    dx=0.0,
                    dy=t_val or 1.0,
                    label=f"T = {plain_number(t_val)} N",
                    role="result",
                ),
                SimulationVector(
                    anchor=[0.0, 0.0],
                    dx=0.0,
                    dy=-(m * g),
                    label=f"W = {plain_number(m * g)} N",
                ),
            ],
            label=f"{plain_number(m, GIVEN_FIGURES)} kg",
            alt=(
                f"A {plain_number(m, GIVEN_FIGURES)} kg mass on a rope: the tension "
                f"{plain_number(t_val)} N pulls up against its {plain_number(m * g)} N weight."
            ),
        ),
    )


def _resultant_force(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    f1, f2 = p["F1"], p["F2"]
    phi = p["angle"]  # radians (converted by params_in_si)
    # The general parallelogram law. At phi = 90 degrees the cosine term
    # drops out and it reduces to Pythagoras, so the perpendicular case
    # needs no separate branch.
    r_val = math.sqrt(f1 * f1 + f2 * f2 + 2 * f1 * f2 * math.cos(phi))
    theta = math.degrees(math.atan2(f2 * math.sin(phi), f1 + f2 * math.cos(phi)))
    return PhysicsResult(
        answer=(
            rf"R = \sqrt{{F_1^2 + F_2^2 + 2F_1F_2\cos\phi}} = "
            rf"\sqrt{{{latex_num(f1, square=True)} + {latex_num(f2, square=True)} + "
            rf"2 \cdot {f1:g} \cdot {f2:g}\cos({math.degrees(phi):g}^\circ)}} "
            rf"\approx {r_val:.2f} \text{{ N}}, \quad "
            rf"\theta = \arctan\frac{{F_2\sin\phi}}{{F_1 + F_2\cos\phi}} "
            rf"= \arctan\frac{{{f2:g}\sin({math.degrees(phi):g}^\circ)}}"
            rf"{{{f1:g} + {f2:g}\cos({math.degrees(phi):g}^\circ)}} "
            rf"\approx {theta:.2f}^\circ"
        ),
        formulas=(
            r"R = \sqrt{F_1^2 + F_2^2 + 2F_1F_2\cos\phi}",
            r"\theta = \arctan\frac{F_2\sin\phi}{F_1 + F_2\cos\phi}",
        ),
        substitutions=(
            rf"R = \sqrt{{{latex_num(f1, square=True)} + {latex_num(f2, square=True)} + 2 "
            rf"\cdot {f1:g} \cdot {f2:g}\cos({math.degrees(phi):g}^\circ)}}",
            rf"\theta = \arctan\frac{{{f2:g}\sin({math.degrees(phi):g}^\circ)}}{{{f1:g} + "
            rf"{f2:g}\cos({math.degrees(phi):g}^\circ)}}",
        ),
        quantities=(
            QuantityResult(
                "",
                r_val,
                "N",
                detail=f"{theta:.2f}°",
                detail_style="at",
            ),
        ),
        simulation_specs=_vector_sum_scene(
            [
                SimulationVector(
                    anchor=[0.0, 0.0],
                    dx=f1,
                    dy=0.0,
                    label=f"{plain_number(f1, GIVEN_FIGURES)} N",
                ),
                SimulationVector(
                    anchor=[0.0, 0.0],
                    dx=f2 * math.cos(phi),
                    dy=f2 * math.sin(phi),
                    label=f"{plain_number(f2, GIVEN_FIGURES)} N",
                ),
            ],
            SimulationVector(
                anchor=[0.0, 0.0],
                dx=r_val * math.cos(math.radians(theta)),
                dy=r_val * math.sin(math.radians(theta)),
                label=f"{plain_number(r_val)} N",
                role="result",
            ),
            alt=(
                f"Forces of {plain_number(f1, GIVEN_FIGURES)} N and "
                f"{plain_number(f2, GIVEN_FIGURES)} N add to {plain_number(r_val)} N "
                f"at {plain_number(theta)}°."
            ),
        ),
    )


# The size a resolved vector is given as, and the symbol its components are named by:
# F_x for a force, v_x for a velocity, s_x for a displacement (the catalog's ``resolve_vector``).
_RESOLVED_SYMBOLS = (("F", "F"), ("v", "v"), ("a", "a"), ("d", "s"), ("p", "p"), ("E", "E"))


@dataclass(frozen=True)
class _Component:
    """One component's working: its rows (a bearing's reduction to an acute angle first, when
    it has one), the value worked, its card, and the axis or direction it lies along."""

    formulas: tuple[str, ...]
    substitutions: tuple[str, ...]
    value: float
    quantity: QuantityResult
    side: str


def _resolve_vector(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    """One vector's horizontal and vertical components, in the unit its size was given in.

    Measured from the horizontal, A_x = A cos θ and A_y = A sin θ; from the vertical the two
    trade places, A_x = A sin θ and A_y = A cos θ. A side stated against an axis ("below the
    horizontal", "west of north") is the component's sign, kept on the answer.
    """
    raw = intent.physics_params or {}
    units = intent.physics_units or {}
    name, symbol = next((pair for pair in _RESOLVED_SYMBOLS if pair[0] in raw), (None, None))
    if name is None or symbol is None:
        raise SolveServiceError("resolve_vector needs one vector's size")
    size, unit = raw[name], units.get(name, "")
    if size <= 0:
        raise SolveServiceError("a vector's size must be positive")
    theta = p["angle"]  # radians
    vertical = raw.get("from_vertical", 0.0) == 1.0
    x_sign = -1.0 if raw.get("x_sign", 1.0) < 0 else 1.0
    y_sign = -1.0 if raw.get("y_sign", 1.0) < 0 else 1.0
    x_value = _snapped(x_sign * size * (math.sin(theta) if vertical else math.cos(theta)), size)
    y_value = _snapped(y_sign * size * (math.cos(theta) if vertical else math.sin(theta)), size)
    shown = latex_unit(unit) if unit else ""
    text_unit = f" {plain_unit(unit)}" if unit else ""
    compass = raw.get("compass", 0.0) == 1.0
    vector = _Vector(symbol, latex_given(size), size, unit, math.degrees(theta), vertical)
    parts = (
        _compass_components(vector, x_sign, y_sign)
        if compass
        else _axis_components(vector, x_sign, y_sign)
    )
    # One component asked ("the vertical component", "the westward component"): the answer
    # is that one, along the direction asked; the picture still shows both, as resolving it
    # does.
    only = int(raw.get("only", 0.0))
    if only in (1, 2):
        parts = [_toward(parts[only - 1], raw.get("toward"))]
    return PhysicsResult(
        answer=r", \quad ".join(
            rf"{part.substitutions[-1]} \approx {latex_number(part.value)}{shown}" for part in parts
        ),
        formulas=tuple(row for part in parts for row in part.formulas),
        substitutions=tuple(row for part in parts for row in part.substitutions),
        quantities=tuple(part.quantity for part in parts),
        simulation_specs=resolution_scene(
            size=size,
            x_value=x_value,
            y_value=y_value,
            unit=text_unit,
            # The axis the angle was measured from: up or down for a vertical reference, else
            # the side the horizontal component points to (a bearing "of west" is from west).
            base_deg=(90.0 if y_sign > 0 else -90.0)
            if vertical
            else (0.0 if x_sign > 0 else 180.0),
            angle_deg=math.degrees(theta),
            bearing=compass,
            alt=(
                f"A {plain_number(size, GIVEN_FIGURES)}{text_unit} vector split into "
                f"{plain_number(x_value)}{text_unit} horizontally and "
                f"{plain_number(y_value)}{text_unit} vertically."
            ),
        ),
    )


@dataclass(frozen=True)
class _Vector:
    """The vector resolved, as the question states it: its symbol and size, the angle in
    degrees, and whether that angle is from the vertical (north or south for a bearing)."""

    symbol: str
    given: str
    size: float
    unit: str
    degrees: float
    vertical: bool


def _snapped(value: float, size: float) -> float:
    """Float noise is no component: 60 N at 90° has none across (Claude review)."""
    return 0.0 if abs(value) < 1e-9 * size else value


def _component(
    vector: _Vector, side: str, trig: str, angle: str, degrees: float, sign: float, word: str
) -> _Component:
    """``A_side = (-)A trig(angle)``, worked at ``degrees``, its card's value beside ``word``."""
    minus = "-" if sign < 0 else ""
    value = _snapped(sign * vector.size * getattr(math, trig)(math.radians(degrees)), vector.size)
    subscript = side if len(side) == 1 and side in "xy" else f"{{{side}}}"
    shown = plain_number(degrees, GIVEN_FIGURES)
    return _Component(
        formulas=(rf"{vector.symbol}_{subscript} = {minus}{vector.symbol}\{trig}{angle}",),
        substitutions=(
            rf"{vector.symbol}_{subscript} = {minus}{vector.given}\{trig}({shown}^\circ)",
        ),
        value=value,
        quantity=QuantityResult("", value, vector.unit, detail=word, detail_style="suffix"),
        side=side,
    )


def _axis_components(vector: _Vector, x_sign: float, y_sign: float) -> list[_Component]:
    """A_x and A_y from the stated angle, each signed by its side."""
    x_trig, y_trig = ("sin", "cos") if vector.vertical else ("cos", "sin")
    return [
        _component(vector, "x", x_trig, r"\theta", vector.degrees, x_sign, "horizontally"),
        _component(vector, "y", y_trig, r"\theta", vector.degrees, y_sign, "vertically"),
    ]


# A three-figure bearing past a right angle, by quadrant: its last bearing, the acute angle to
# the north-south line (as a formula in θ, the bearing, and worked), and the directions the
# vector lies between.
_BEARING_QUADRANTS: tuple[tuple[float, str, Callable[[float], float], str, str], ...] = (
    (180.0, r"180^\circ - \theta", lambda bearing: 180.0 - bearing, "E", "S"),
    (270.0, r"\theta - 180^\circ", lambda bearing: bearing - 180.0, "W", "S"),
    (360.0, r"360^\circ - \theta", lambda bearing: 360.0 - bearing, "W", "N"),
)
_COMPASS_WORDS = {"E": "east", "W": "west", "N": "north", "S": "south"}
_OPPOSITE = {"E": "W", "W": "E", "N": "S", "S": "N", "x": "x", "y": "y"}


def _compass_components(vector: _Vector, x_sign: float, y_sign: float) -> list[_Component]:
    """A bearing worked as a textbook works it: each component a size along the direction it
    points ("v_E = 250 cos 30° = 216.5 km/h east"), from the angle the question states and
    the line it is measured from: from east or west the cosine is across, from north or south
    the sine. A three-figure bearing past 90° is first reduced to its acute angle from the
    north-south line, in a row of its own, so every number the substitution uses is given
    or worked above it (review, 2026-11-21)."""
    ew, ns = ("E" if x_sign > 0 else "W"), ("N" if y_sign > 0 else "S")
    angle, degrees = r"\theta", vector.degrees
    reduction: tuple[tuple[str, ...], tuple[str, ...]] = ((), ())
    if vector.vertical and degrees > 90:
        _, formula, reduce, ew, ns = next(q for q in _BEARING_QUADRANTS if degrees <= q[0])
        bearing = f"{plain_number(degrees, GIVEN_FIGURES)}^\\circ"
        angle, degrees = r"\phi", reduce(degrees)
        reduction = (
            (rf"\phi = {formula}",),
            (
                rf"\phi = {formula.replace(r'\theta', bearing)} "
                rf"= {plain_number(degrees, GIVEN_FIGURES)}^\circ",
            ),
        )
    ew_trig, ns_trig = ("sin", "cos") if vector.vertical else ("cos", "sin")
    across = _component(vector, ew, ew_trig, angle, degrees, 1.0, _COMPASS_WORDS[ew])
    up = _component(vector, ns, ns_trig, angle, degrees, 1.0, _COMPASS_WORDS[ns])
    # The reduction is worked once, before the first component that uses it.
    across = replace(
        across,
        formulas=reduction[0] + across.formulas,
        substitutions=reduction[1] + across.substitutions,
    )
    return [across, up]


def _toward(part: _Component, toward: float | None) -> _Component:
    """One compass component along the direction asked. Asked the other way from the side it
    points ("the westward component" of a plane flying north of east), it is the negative of
    that size, its sign kept beside the direction asked: -216.5 km/h west, never 216.5 km/h
    east as though the question had asked east (review, 2026-11-21)."""
    if toward is None or part.side not in _COMPASS_WORDS:
        return part
    positive = part.side in "EN"
    if (toward > 0) == positive:
        return part
    side, other = f"_{{{part.side}}} = ", f"_{{{_OPPOSITE[part.side]}}} = -"

    def negated(rows: tuple[str, ...]) -> tuple[str, ...]:
        return (*rows[:-1], rows[-1].replace(side, other, 1))

    word = _COMPASS_WORDS[_OPPOSITE[part.side]]
    return _Component(
        formulas=negated(part.formulas),
        substitutions=negated(part.substitutions),
        value=-part.value,
        quantity=QuantityResult(
            "", -part.value, part.quantity.unit, detail=word, detail_style="suffix"
        ),
        side=_OPPOSITE[part.side],
    )


def _atwood(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    m1, m2 = sorted((p["m1"], p["m2"]), reverse=True)
    if m1 <= 0 or m2 <= 0:
        raise SolveServiceError("masses must be positive")
    g = gravity_of(p)
    a_val = (m1 - m2) * g / (m1 + m2)
    t_val = 2 * m1 * m2 * g / (m1 + m2)
    return PhysicsResult(
        answer=(
            rf"a = \frac{{(m_1 - m_2)g}}{{m_1 + m_2}} = "
            rf"\frac{{({m1:g} - {m2:g}) \cdot {g:g}}}{{{m1:g} + {m2:g}}} "
            rf"\approx {a_val:.2f} \text{{ m/s}}^2, \quad "
            rf"T = \frac{{2 m_1 m_2 g}}{{m_1 + m_2}} = "
            rf"\frac{{2 \cdot {m1:g} \cdot {m2:g} \cdot {g:g}}}{{{m1:g} + {m2:g}}} "
            rf"\approx {t_val:.2f} \text{{ N}}"
        ),
        formulas=(r"a = \frac{(m_1 - m_2)g}{m_1 + m_2}", r"T = \frac{2 m_1 m_2 g}{m_1 + m_2}"),
        substitutions=(
            rf"a = \frac{{({m1:g} - {m2:g}) \cdot {g:g}}}{{{m1:g} + {m2:g}}}",
            rf"T = \frac{{2 \cdot {m1:g} \cdot {m2:g} \cdot {g:g}}}{{{m1:g} + {m2:g}}}",
        ),
        quantities=(
            QuantityResult("", a_val, "m/s^2"),
            QuantityResult("", t_val, "N"),
        ),
        simulation_specs=_atwood_scene(m1, m2, a_val, t_val),
    )


def _table_pulley(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    """A block m₁ on a frictionless table pulled over a pulley by a hanging m₂."""
    m1, m2 = p["m1"], p["m2"]
    if m1 <= 0 or m2 <= 0:
        raise SolveServiceError("masses must be positive")
    g = gravity_of(p)
    a_val = m2 * g / (m1 + m2)
    t_val = m1 * a_val
    a_row = rf"a = \frac{{{m2:g} \cdot {g:g}}}{{{m1:g} + {m2:g}}}"
    t_row = rf"T = {m1:g} \cdot \frac{{{m2:g} \cdot {g:g}}}{{{m1:g} + {m2:g}}}"
    return PhysicsResult(
        answer=(
            rf"a = \frac{{m_2 g}}{{m_1 + m_2}} = {a_row.split(' = ', 1)[1]} "
            rf"\approx {a_val:.2f} \text{{ m/s}}^2, \quad "
            rf"T = m_1 a = {t_row.split(' = ', 1)[1]} \approx {t_val:.2f} \text{{ N}}"
        ),
        formulas=(r"a = \frac{m_2 g}{m_1 + m_2}", r"T = m_1 a"),
        substitutions=(a_row, t_row),
        quantities=(
            QuantityResult("", a_val, "m/s^2"),
            QuantityResult("", t_val, "N"),
        ),
    )


def _newton_second_law(intent: PhysicsIntent, p: dict[str, float]) -> PhysicsResult:
    if "F" in p and "m" in p and "a" not in p:
        a_val = p["F"] / p["m"]
        plugged = rf"\frac{{{p['F']:g}}}{{{p['m']:g}}}"
        answer_latex = rf"a = \frac{{F}}{{m}} = {plugged} \approx {a_val:.2f} \text{{ m/s}}^2"
        formula = r"a = \frac{F}{m}"
        substitution = rf"a = {plugged}"
        quantity = QuantityResult("", a_val, "m/s^2")
    elif "F" in p and "a" in p and "m" not in p:
        m_val = p["F"] / p["a"]
        plugged = rf"\frac{{{p['F']:g}}}{{{p['a']:g}}}"
        answer_latex = rf"m = \frac{{F}}{{a}} = {plugged} \approx {m_val:.2f} \text{{ kg}}"
        formula = r"m = \frac{F}{a}"
        substitution = rf"m = {plugged}"
        quantity = QuantityResult("", m_val, "kg")
    elif "m" in p and "a" in p and "F" not in p:
        f_val = p["m"] * p["a"]
        plugged = rf"{p['m']:g} \cdot {p['a']:g}"
        answer_latex = rf"F = m \cdot a = {plugged} \approx {f_val:.2f} \text{{ N}}"
        formula = r"F = m \cdot a"
        substitution = rf"F = {plugged}"
        quantity = QuantityResult("", f_val, "N")
    else:
        raise SolveServiceError("force solve needs exactly two of F, m, a")

    # F = ma is a push and the motion it produces, drawn the same way round.
    # Both point right by convention — the question states no direction, and
    # inventing opposing ones would say the block is being decelerated. The
    # acceleration is a `motion` arrow: drawn like a force, it would teach
    # that ma is one more force on the block.
    force = p.get("F", p.get("m", 0.0) * p.get("a", 0.0))
    accel = p.get("a", p.get("F", 0.0) / p["m"] if p.get("m") else 0.0)
    scene = free_body_scene(
        [
            SimulationVector(
                anchor=[0.0, 0.0],
                dx=1.0,
                dy=0.0,
                label=f"F = {plain_number(force)} N",
                role="result" if "F" not in p else "force",
            ),
            SimulationVector(
                anchor=[0.0, -0.9],
                dx=1.0,
                dy=0.0,
                label=f"a = {plain_number(accel)} m/s²",
                role="motion",
            ),
        ],
        label=f"{plain_number(p['m'], GIVEN_FIGURES)} kg" if "m" in p else None,
        alt=(
            f"A net force of {plain_number(force)} N gives an acceleration of "
            f"{plain_number(accel)} m/s² in the same direction."
        ),
        shape="box",
    )
    return PhysicsResult(
        answer=answer_latex,
        formulas=(formula,),
        substitutions=(substitution,),
        quantities=(quantity,),
        simulation_specs=scene,
    )


_OPERATIONS: dict[str, Callable[[PhysicsIntent, dict[str, float]], PhysicsResult]] = {
    "tension": _tension,
    "resultant_force": _resultant_force,
    "resolve_vector": _resolve_vector,
    "atwood": _atwood,
    "table_pulley": _table_pulley,
}

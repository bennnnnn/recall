"""Friction and inclined-plane solvers: N = mg cos(theta), f = mu N,
a = g (sin(theta) - mu cos(theta)).
"""

from __future__ import annotations

import math

from app.models.schemas.physics import PhysicsIntent, SimulationBlockSpec, SimulationBody
from app.modules.physics.solvers.common import (
    PhysicsResult,
    QuantityResult,
    _params_in_si,
    gravity_of,
)
from app.services.solving import SolveServiceError


def solve_friction(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "friction_force"
    g = gravity_of(p)
    mu = p.get("mu", 0.0)
    theta = p.get("angle", 0.0)  # radians
    if g <= 0:
        raise SolveServiceError("gravity must be positive")
    if mu < 0:
        raise SolveServiceError("coefficient of friction cannot be negative")
    if not -math.pi / 2 < theta < math.pi / 2:
        raise SolveServiceError("incline angle must be between -90 and 90 degrees")

    deg = math.degrees(theta)
    # Mass cancels out of the incline acceleration, so it is optional there and
    # only these two branches require it.
    if op in ("normal_force", "friction_force") and "m" not in p:
        raise SolveServiceError(f"{op} needs a mass")
    normal = p.get("m", 0.0) * g * math.cos(theta)
    m = p.get("m", 0.0)

    if op == "normal_force":
        if theta == 0:
            plugged = rf"{m:g} \cdot {g:g}"
            answer = rf"N = m g = {plugged} \approx {normal:.2f} \text{{ N}}"
            formula = r"N = m g"
        else:
            plugged = rf"{m:g} \cdot {g:g} \cdot \cos({deg:g}^\circ)"
            answer = rf"N = m g \cos\theta = {plugged} \approx {normal:.2f} \text{{ N}}"
            formula = r"N = m g \cos\theta"
        return PhysicsResult(
            answer=answer,
            formulas=(formula,),
            substitutions=(rf"N = {plugged}",),
            quantities=(QuantityResult("", normal, "N"),),
            simulation_specs=_incline_scene(deg, mu=mu),
        )

    if op == "friction_force":
        f_val = mu * normal
        answer = rf"f = \mu N = {mu:g} \cdot {normal:.2f} \approx {f_val:.2f} \text{{ N}}"
        return PhysicsResult(
            answer=answer,
            formulas=(r"f = \mu N",),
            substitutions=(rf"f = {mu:g} \cdot {normal:.2f}",),
            quantities=(QuantityResult("", f_val, "N"),),
            simulation_specs=_incline_scene(deg, mu=mu),
        )

    if op == "incline_acceleration":
        a_val = g * (math.sin(theta) - mu * math.cos(theta))
        if a_val <= 0:
            # tan(theta) <= mu: static friction holds it. Reporting a negative
            # acceleration would describe the block sliding *up* the slope on
            # its own, which is not what the equation means here.
            return PhysicsResult(
                answer=(
                    rf"\tan({deg:g}^\circ) \le \mu = {mu:g}, "
                    r"\text{so friction holds the block: } a = 0 \text{ m/s}^2"
                ),
                formulas=(
                    rf"\tan({deg:g}^\circ) \le \mu = {mu:g}, "
                    r"\text{so friction holds the block: } a",
                ),
                substitutions=(r"a = 0 \text{ m/s}^2",),
                quantities=(QuantityResult("a", 0.0, "m/s^2"),),
                # a = 0 is the answer, so the block stays put and the diagram
                # is the free body that explains why.
                simulation_specs=_incline_scene(deg, mu=mu),
            )
        answer = (
            r"a = g(\sin\theta - \mu\cos\theta) = "
            rf"{g:g}(\sin({deg:g}^\circ) - {mu:g}\cos({deg:g}^\circ)) "
            rf"\approx {a_val:.2f} \text{{ m/s}}^2"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"a = g(\sin\theta - \mu\cos\theta)",),
            substitutions=(rf"a = {g:g}(\sin({deg:g}^\circ) - {mu:g}\cos({deg:g}^\circ))",),
            quantities=(QuantityResult("", a_val, "m/s^2"),),
            simulation_specs=_incline_scene(deg, mu=mu, accel=a_val),
        )

    if op == "friction_coefficient":
        mu_val = math.tan(theta)
        return PhysicsResult(
            answer=(rf"\mu = \tan(\theta) = \tan({deg:.1f}^\circ) \approx {mu_val:.2f}"),
            formulas=(r"\mu = \tan(\theta)",),
            substitutions=(rf"\mu = \tan({deg:.1f}^\circ)",),
            quantities=(QuantityResult("", mu_val, ""),),
            simulation_specs=_incline_scene(deg, mu=mu_val),
        )

    if op == "minimum_force":
        f_val = mu * m * g
        return PhysicsResult(
            answer=(
                rf"F_{{min}} = \mu m g = {mu:g} \cdot {m:g} \cdot {g:g} "
                rf"\approx {f_val:.2f} \text{{ N}}"
            ),
            formulas=(r"F_{min} = \mu m g",),
            substitutions=(rf"F_{{min}} = {mu:g} \cdot {m:g} \cdot {g:g}",),
            quantities=(QuantityResult("", f_val, "N"),),
        )

    raise SolveServiceError(f"unsupported friction op: {op}")


# The slope's own length is never stated, so it is a display choice and the
# scene is drawn at a fixed one. The same reasoning as the SHM curve's
# normalised amplitude: what the question is about is the *shape* of the
# motion — a block that starts slow and speeds up — and that shape is real
# whatever the slope measures. Inventing a number for the answer would be a
# different thing entirely.
_INCLINE_LENGTH = 6.0


def _incline_scene(
    deg: float, *, mu: float, accel: float | None = None
) -> list[SimulationBlockSpec]:
    """A block on a slope with its weight, normal and friction arrows.

    The ticket's third named scene, and the one that is mostly a *diagram*: a
    free-body picture is what an incline question wants, and for two of the
    three ops the block is not moving at all.

    A flat surface gets nothing. Weight down and normal up is a true picture
    and an empty one, and with no slope there is no friction direction to draw
    — the block is not going anywhere for friction to oppose.
    """
    if deg == 0:
        return []
    theta = math.radians(abs(deg))
    # Descending left to right, which fixes what "down the slope" means for
    # both the path and the arrows.
    down_x, down_y = math.cos(theta), -math.sin(theta)
    top_x, top_y = 0.0, _INCLINE_LENGTH * math.sin(theta)

    n_points = 60
    if accel is not None and accel > 0:
        # s = ½at², sampled uniformly in *time*, so the block visibly
        # accelerates rather than sliding at a constant rate. The duration is
        # the one that covers the drawn slope, so the block arrives at the
        # bottom exactly as the animation ends.
        duration = math.sqrt(2 * _INCLINE_LENGTH / accel)
        dt = duration / (n_points - 1)
        distances = [0.5 * accel * (i * dt) ** 2 for i in range(n_points)]
    else:
        # Held by friction, or an op with no acceleration to show: the block
        # stays where it is and the arrows are the whole picture.
        distances = [0.0] * n_points

    path = [[round(top_x + s * down_x, 4), round(top_y + s * down_y, 4)] for s in distances]
    arrows: list[str] = ["gravity", "normal"]
    if mu > 0:
        arrows.append("friction")

    margin = _INCLINE_LENGTH * 0.18
    return [
        SimulationBlockSpec(
            type="incline",
            title="Inclined Plane",
            bodies=[SimulationBody(path=path, radius=_INCLINE_LENGTH * 0.06)],
            x_min=-margin,
            x_max=_INCLINE_LENGTH * math.cos(theta) + margin,
            y_min=-margin,
            y_max=top_y + margin,
            arrows=arrows,  # type: ignore[arg-type]
            # The angle arrived here through radians, so 30 comes back as
            # 29.999999999999996 and would ship in the fence JSON that way.
            incline_deg=round(abs(deg), 4),
        )
    ]

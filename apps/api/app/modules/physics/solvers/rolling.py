"""Rolling without slipping (speed, acceleration and energy) and the parallel-axis theorem."""

from __future__ import annotations

import math

from app.modules.physics.solvers.common import PhysicsResult, QuantityResult, _latex_num
from app.modules.physics.solvers.rotational_kinematics import _unknown
from app.services.solving import SolveServiceError


def _rolling_speed(params: dict[str, float]) -> PhysicsResult:
    unknown = _unknown(params, ("v", "omega", "r"))
    if unknown != "r" and params["r"] <= 0:
        raise SolveServiceError("radius must be positive")
    if unknown == "v":
        value = params["r"] * params["omega"]
        answer = (
            rf"v = R\omega = {params['r']:g} \cdot {params['omega']:g} "
            rf"\approx {value:.2f} \text{{ m/s}}"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"v = R\omega",),
            substitutions=(rf"v = {params['r']:g} \cdot {params['omega']:g}",),
            quantities=(QuantityResult("", value, "m/s"),),
        )
    if unknown == "omega":
        value = params["v"] / params["r"]
        answer = (
            rf"\omega = \frac{{v}}{{R}} = \frac{{{params['v']:g}}}{{{params['r']:g}}} "
            rf"\approx {value:.2f} \text{{ rad/s}}"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"\omega = \frac{v}{R}",),
            substitutions=(rf"\omega = \frac{{{params['v']:g}}}{{{params['r']:g}}}",),
            quantities=(QuantityResult("", value, "rad/s"),),
        )
    if params["omega"] == 0:
        raise SolveServiceError("angular velocity must be nonzero to find the radius")
    value = params["v"] / params["omega"]
    if value <= 0:
        raise SolveServiceError("radius must be positive")
    answer = rf"R = \frac{{v}}{{\omega}} \approx {value:.2f} \text{{ m}}"
    return PhysicsResult(
        answer=answer,
        formulas=(r"R = \frac{v}{\omega}",),
        substitutions=(rf"R = \frac{{{params['v']:g}}}{{{params['omega']:g}}}",),
        quantities=(QuantityResult("", value, "m"),),
    )


def _rolling_acceleration(params: dict[str, float]) -> PhysicsResult:
    unknown = _unknown(params, ("a", "ang_alpha", "r"))
    if unknown != "r" and params["r"] <= 0:
        raise SolveServiceError("radius must be positive")
    if unknown == "a":
        value = params["r"] * params["ang_alpha"]
        answer = (
            rf"a = R\alpha = {params['r']:g} \cdot {params['ang_alpha']:g} "
            rf"\approx {value:.2f} \text{{ m/s}}^2"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"a = R\alpha",),
            substitutions=(rf"a = {params['r']:g} \cdot {params['ang_alpha']:g}",),
            quantities=(QuantityResult("", value, "m/s^2"),),
        )
    if unknown == "ang_alpha":
        value = params["a"] / params["r"]
        answer = (
            rf"\alpha = \frac{{a}}{{R}} = \frac{{{params['a']:g}}}{{{params['r']:g}}} "
            rf"\approx {value:.2f} \text{{ rad/s}}^2"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"\alpha = \frac{a}{R}",),
            substitutions=(rf"\alpha = \frac{{{params['a']:g}}}{{{params['r']:g}}}",),
            quantities=(QuantityResult("", value, "rad/s^2"),),
        )
    if params["ang_alpha"] == 0:
        raise SolveServiceError("angular acceleration must be nonzero to find the radius")
    value = params["a"] / params["ang_alpha"]
    if value <= 0:
        raise SolveServiceError("radius must be positive")
    answer = rf"R = \frac{{a}}{{\alpha}} \approx {value:.2f} \text{{ m}}"
    return PhysicsResult(
        answer=answer,
        formulas=(r"R = \frac{a}{\alpha}",),
        substitutions=(rf"R = \frac{{{params['a']:g}}}{{{params['ang_alpha']:g}}}",),
        quantities=(QuantityResult("", value, "m"),),
    )


def _rolling_energy(params: dict[str, float]) -> PhysicsResult:
    if params["m"] <= 0 or params["inertia"] <= 0:
        raise SolveServiceError("mass and moment of inertia must be positive")
    speed = params.get("v")
    omega = params.get("omega")
    radius = params.get("r")
    if speed is None and omega is not None and radius is not None:
        if radius <= 0:
            raise SolveServiceError("radius must be positive")
        speed = radius * omega
    elif omega is None and speed is not None and radius is not None:
        if radius <= 0:
            raise SolveServiceError("radius must be positive")
        omega = speed / radius
    if speed is None or omega is None:
        raise SolveServiceError("rolling energy needs both speeds, or one speed and the radius")
    value = 0.5 * params["m"] * speed**2 + 0.5 * params["inertia"] * omega**2
    answer = (
        r"K = \frac{1}{2}Mv^2 + \frac{1}{2}I\omega^2 \approx "
        rf"{value:.2f} \text{{ J}}"
    )
    return PhysicsResult(
        answer=answer,
        formulas=(r"K = \frac{1}{2}Mv^2 + \frac{1}{2}I\omega^2",),
        substitutions=(
            rf"K = \frac{{1}}{{2}} \cdot {params['m']:g} \cdot {speed:g}^2 + "
            rf"\frac{{1}}{{2}} \cdot {params['inertia']:g} \cdot {omega:g}^2",
        ),
        quantities=(QuantityResult("", value, "J"),),
    )


def _parallel_axis(params: dict[str, float]) -> PhysicsResult:
    unknown = _unknown(params, ("inertia", "inertia_cm", "m", "d"))
    if unknown != "m" and params["m"] <= 0:
        raise SolveServiceError("mass must be positive")
    if unknown == "inertia":
        value = params["inertia_cm"] + params["m"] * params["d"] ** 2
        answer = (
            rf"I = I_{{cm}} + Md^2 = {params['inertia_cm']:g} + "
            rf"{params['m']:g} \cdot {_latex_num(params['d'], square=True)} "
            rf"\approx {value:.2f} \text{{ kg}}\,\text{{m}}^2"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"I = I_{cm} + Md^2",),
            substitutions=(
                rf"I = {params['inertia_cm']:g} + {params['m']:g} \cdot "
                rf"{_latex_num(params['d'], square=True)}",
            ),
            quantities=(QuantityResult("", value, "kg*m^2"),),
        )
    if unknown == "inertia_cm":
        value = params["inertia"] - params["m"] * params["d"] ** 2
        answer = rf"I_{{cm}} = I - Md^2 \approx {value:.2f} \text{{ kg}}\,\text{{m}}^2"
        return PhysicsResult(
            answer=answer,
            formulas=(r"I_{cm} = I - Md^2",),
            substitutions=(
                rf"I_{{cm}} = {params['inertia']:g} - {params['m']:g} \cdot "
                rf"{_latex_num(params['d'], square=True)}",
            ),
            quantities=(QuantityResult("", value, "kg*m^2"),),
        )
    if unknown == "m":
        if params["d"] == 0:
            raise SolveServiceError("a zero distance does not determine the mass")
        value = (params["inertia"] - params["inertia_cm"]) / params["d"] ** 2
        if value <= 0:
            raise SolveServiceError("mass must be positive")
        answer = rf"M = \frac{{I - I_{{cm}}}}{{d^2}} \approx {value:.2f} \text{{ kg}}"
        return PhysicsResult(
            answer=answer,
            formulas=(r"M = \frac{I - I_{cm}}{d^2}",),
            substitutions=(
                rf"M = \frac{{{params['inertia']:g} - {params['inertia_cm']:g}}}"
                rf"{{{_latex_num(params['d'], square=True)}}}",
            ),
            quantities=(QuantityResult("", value, "kg"),),
        )
    square = (params["inertia"] - params["inertia_cm"]) / params["m"]
    if square < 0:
        raise SolveServiceError("those values do not give a real distance")
    value = math.sqrt(square)
    answer = rf"d = \sqrt{{\frac{{I - I_{{cm}}}}{{M}}}} \approx {value:.2f} \text{{ m}}"
    return PhysicsResult(
        answer=answer,
        formulas=(r"d = \sqrt{\frac{I - I_{cm}}{M}}",),
        substitutions=(
            rf"d = \sqrt{{\frac{{{params['inertia']:g} - {params['inertia_cm']:g}}}"
            rf"{{{params['m']:g}}}}}",
        ),
        quantities=(QuantityResult("", value, "m"),),
    )

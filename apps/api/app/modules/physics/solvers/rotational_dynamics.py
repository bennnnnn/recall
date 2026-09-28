"""Constant-alpha rotation, rolling, and the parallel-axis theorem."""

from __future__ import annotations

import math

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.solvers.common import (
    PhysicsResult,
    QuantityResult,
    _latex_num,
    _params_in_si,
)
from app.services.solving import SolveServiceError


def _unknown(params: dict[str, float], keys: tuple[str, ...]) -> str:
    missing = [key for key in keys if key not in params]
    if len(missing) != 1:
        raise SolveServiceError("needs exactly one unknown")
    return missing[0]


def solve_rotational_dynamics(intent: PhysicsIntent) -> PhysicsResult:
    params = _params_in_si(intent)
    operation = intent.physics_op or ""
    if operation == "rotational_omega":
        return _omega(params)
    if operation == "rotational_theta":
        return _theta(params)
    if operation == "rotational_alpha":
        return _alpha(params)
    if operation == "torque_inertia":
        return _torque_inertia(params)
    if operation == "torque_angular_impulse":
        return _angular_impulse(params)
    if operation == "angular_momentum_conservation":
        return _angular_momentum(params)
    if operation == "rolling_speed":
        return _rolling_speed(params)
    if operation == "rolling_acceleration":
        return _rolling_acceleration(params)
    if operation == "rolling_kinetic_energy":
        return _rolling_energy(params)
    if operation == "parallel_axis":
        return _parallel_axis(params)
    raise SolveServiceError(f"unsupported rotational op: {operation}")


def _omega(params: dict[str, float]) -> PhysicsResult:
    if {"omega0", "ang_alpha", "t"} <= params.keys():
        value = params["omega0"] + params["ang_alpha"] * params["t"]
        answer = (
            rf"\omega = \omega_0 + \alpha t = {params['omega0']:g} + "
            rf"{params['ang_alpha']:g} \cdot {params['t']:g} "
            rf"\approx {value:.2f} \text{{ rad/s}}"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"\omega = \omega_0 + \alpha t",),
            substitutions=(
                rf"\omega = {params['omega0']:g} + {params['ang_alpha']:g} \cdot {params['t']:g}",
            ),
            quantities=(QuantityResult("", value, "rad/s", number_format=".2f"),),
        )
    if {"omega0", "ang_alpha", "theta"} <= params.keys():
        disc = params["omega0"] ** 2 + 2 * params["ang_alpha"] * params["theta"]
        if disc < 0:
            raise SolveServiceError("those values do not give a real angular velocity")
        value = math.sqrt(disc)
        answer = (
            r"\omega^2 = \omega_0^2 + 2\alpha\Delta\theta \Rightarrow "
            rf"\omega \approx {value:.2f} \text{{ rad/s}}"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"\omega^2 = \omega_0^2 + 2\alpha\Delta\theta \Rightarrow \omega",),
            substitutions=(
                rf"\omega = \sqrt{{{params['omega0']:g}^2 + 2 \cdot {params['ang_alpha']:g}"
                rf" \cdot {params['theta']:g}}}",
            ),
            quantities=(QuantityResult("", value, "rad/s", number_format=".2f"),),
        )
    raise SolveServiceError("angular velocity needs omega0, alpha, and time or angle")


def _theta(params: dict[str, float]) -> PhysicsResult:
    # The catalog measures angular displacement from zero. There is no theta0 input.
    theta0 = 0.0
    if {"omega0", "ang_alpha", "t"} <= params.keys():
        value = (
            theta0 + params["omega0"] * params["t"] + 0.5 * params["ang_alpha"] * params["t"] ** 2
        )
        elapsed = _latex_num(params["t"], square=True)
        answer = (
            r"\theta = \theta_0 + \omega_0 t + \frac{1}{2}\alpha t^2 = "
            rf"{theta0:g} + {params['omega0']:g} \cdot {params['t']:g} + "
            rf"\frac{{1}}{{2}} \cdot {params['ang_alpha']:g} \cdot {elapsed} "
            rf"\approx {value:.2f} \text{{ rad}}"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"\theta = \theta_0 + \omega_0 t + \frac{1}{2}\alpha t^2",),
            substitutions=(
                rf"\theta = {theta0:g} + {params['omega0']:g} \cdot {params['t']:g} + "
                rf"\frac{{1}}{{2}} \cdot {params['ang_alpha']:g} \cdot {elapsed}",
            ),
            quantities=(QuantityResult("", value, "rad", number_format=".2f"),),
        )
    if {"omega", "omega0", "ang_alpha"} <= params.keys():
        if params["ang_alpha"] == 0:
            raise SolveServiceError("angular acceleration must be nonzero to find the angle")
        value = theta0 + (params["omega"] ** 2 - params["omega0"] ** 2) / (2 * params["ang_alpha"])
        answer = (
            r"\omega^2 = \omega_0^2 + 2\alpha\Delta\theta \Rightarrow "
            rf"\theta \approx {value:.2f} \text{{ rad}}"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"\omega^2 = \omega_0^2 + 2\alpha\Delta\theta \Rightarrow \theta",),
            substitutions=(
                rf"\theta = \frac{{{params['omega']:g}^2 - {params['omega0']:g}^2}}"
                rf"{{2 \cdot {params['ang_alpha']:g}}}",
            ),
            quantities=(QuantityResult("", value, "rad", number_format=".2f"),),
        )
    raise SolveServiceError("angular displacement needs the constant-acceleration givens")


def _alpha(params: dict[str, float]) -> PhysicsResult:
    if {"omega", "omega0", "t"} <= params.keys():
        if params["t"] == 0:
            raise SolveServiceError("elapsed time must be nonzero")
        value = (params["omega"] - params["omega0"]) / params["t"]
        answer = (
            r"\alpha = \frac{\omega - \omega_0}{t} = "
            rf"\frac{{{params['omega']:g} - {params['omega0']:g}}}{{{params['t']:g}}} "
            rf"\approx {value:.2f} \text{{ rad/s}}^2"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"\alpha = \frac{\omega - \omega_0}{t}",),
            substitutions=(
                rf"\alpha = \frac{{{params['omega']:g} - {params['omega0']:g}}}{{{params['t']:g}}}",
            ),
            quantities=(QuantityResult("", value, "rad/s^2", number_format=".2f"),),
        )
    if {"omega", "omega0", "theta"} <= params.keys():
        if params["theta"] == 0:
            raise SolveServiceError("angular displacement must be nonzero")
        value = (params["omega"] ** 2 - params["omega0"] ** 2) / (2 * params["theta"])
        answer = (
            r"\alpha = \frac{\omega^2 - \omega_0^2}{2\Delta\theta} \approx "
            rf"{value:.2f} \text{{ rad/s}}^2"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"\alpha = \frac{\omega^2 - \omega_0^2}{2\Delta\theta}",),
            substitutions=(
                rf"\alpha = \frac{{{params['omega']:g}^2 - {params['omega0']:g}^2}}"
                rf"{{2 \cdot {params['theta']:g}}}",
            ),
            quantities=(QuantityResult("", value, "rad/s^2", number_format=".2f"),),
        )
    raise SolveServiceError("angular acceleration needs two angular velocities and time or angle")


def _torque_inertia(params: dict[str, float]) -> PhysicsResult:
    unknown = _unknown(params, ("tau", "inertia", "ang_alpha"))
    if unknown == "tau":
        if params["inertia"] <= 0:
            raise SolveServiceError("moment of inertia must be positive")
        value = params["inertia"] * params["ang_alpha"]
        answer = (
            rf"\tau = I\alpha = {params['inertia']:g} \cdot {params['ang_alpha']:g} "
            rf"\approx {value:.2f} \text{{ N}}\cdot\text{{m}}"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"\tau = I\alpha",),
            substitutions=(rf"\tau = {params['inertia']:g} \cdot {params['ang_alpha']:g}",),
            quantities=(QuantityResult("", value, "N*m", number_format=".2f"),),
        )
    if unknown == "ang_alpha":
        if params["inertia"] <= 0:
            raise SolveServiceError("moment of inertia must be positive")
        value = params["tau"] / params["inertia"]
        answer = (
            rf"\alpha = \frac{{\tau}}{{I}} = \frac{{{params['tau']:g}}}{{{params['inertia']:g}}} "
            rf"\approx {value:.2f} \text{{ rad/s}}^2"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"\alpha = \frac{\tau}{I}",),
            substitutions=(rf"\alpha = \frac{{{params['tau']:g}}}{{{params['inertia']:g}}}",),
            quantities=(QuantityResult("", value, "rad/s^2", number_format=".2f"),),
        )
    if params["ang_alpha"] == 0:
        raise SolveServiceError("angular acceleration must be nonzero")
    value = params["tau"] / params["ang_alpha"]
    if value <= 0:
        raise SolveServiceError("moment of inertia must be positive")
    answer = (
        rf"I = \frac{{\tau}}{{\alpha}} = \frac{{{params['tau']:g}}}{{{params['ang_alpha']:g}}} "
        rf"\approx {value:.2f} \text{{ kg}}\,\text{{m}}^2"
    )
    return PhysicsResult(
        answer=answer,
        formulas=(r"I = \frac{\tau}{\alpha}",),
        substitutions=(rf"I = \frac{{{params['tau']:g}}}{{{params['ang_alpha']:g}}}",),
        quantities=(QuantityResult("", value, "kg*m^2", number_format=".2f"),),
    )


def _angular_impulse(params: dict[str, float]) -> PhysicsResult:
    unknown = _unknown(params, ("tau", "L_i", "L_f", "t"))
    if unknown != "t" and params["t"] == 0:
        raise SolveServiceError("elapsed time must be nonzero")
    if unknown == "tau":
        value = (params["L_f"] - params["L_i"]) / params["t"]
        answer = (
            r"\tau = \frac{\Delta L}{\Delta t} = "
            rf"\frac{{{params['L_f']:g} - {params['L_i']:g}}}{{{params['t']:g}}} "
            rf"\approx {value:.2f} \text{{ N}}\cdot\text{{m}}"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"\tau = \frac{\Delta L}{\Delta t}",),
            substitutions=(
                rf"\tau = \frac{{{params['L_f']:g} - {params['L_i']:g}}}{{{params['t']:g}}}",
            ),
            quantities=(QuantityResult("", value, "N*m", number_format=".2f"),),
        )
    if unknown == "L_f":
        value = params["L_i"] + params["tau"] * params["t"]
        answer = (
            rf"L_f = L_i + \tau\Delta t \approx {value:.2f} "
            r"\text{ kg}\,\text{m}^2\text{/s}"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"L_f = L_i + \tau\Delta t",),
            substitutions=(rf"L_f = {params['L_i']:g} + {params['tau']:g} \cdot {params['t']:g}",),
            quantities=(QuantityResult("", value, "kg*m^2/s", number_format=".2f"),),
        )
    if unknown == "L_i":
        value = params["L_f"] - params["tau"] * params["t"]
        answer = (
            rf"L_i = L_f - \tau\Delta t \approx {value:.2f} "
            r"\text{ kg}\,\text{m}^2\text{/s}"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"L_i = L_f - \tau\Delta t",),
            substitutions=(rf"L_i = {params['L_f']:g} - {params['tau']:g} \cdot {params['t']:g}",),
            quantities=(QuantityResult("", value, "kg*m^2/s", number_format=".2f"),),
        )
    if params["tau"] == 0:
        raise SolveServiceError("a zero torque does not determine the time")
    value = (params["L_f"] - params["L_i"]) / params["tau"]
    answer = rf"\Delta t = \frac{{\Delta L}}{{\tau}} \approx {value:.2f} \text{{ s}}"
    return PhysicsResult(
        answer=answer,
        formulas=(r"\Delta t = \frac{\Delta L}{\tau}",),
        substitutions=(
            rf"\Delta t = \frac{{{params['L_f']:g} - {params['L_i']:g}}}{{{params['tau']:g}}}",
        ),
        quantities=(QuantityResult("", value, "s", number_format=".2f"),),
    )


def _angular_momentum(params: dict[str, float]) -> PhysicsResult:
    unknown = _unknown(params, ("inertia_i", "omega_i", "inertia_f", "omega_f"))
    for key in ("inertia_i", "inertia_f"):
        if key != unknown and params[key] <= 0:
            raise SolveServiceError("moment of inertia must be positive")
    if unknown == "omega_f":
        value = params["inertia_i"] * params["omega_i"] / params["inertia_f"]
        shown = r"\omega_f"
        plugged = (
            rf"\omega_f = \frac{{{params['inertia_i']:g} \cdot {params['omega_i']:g}}}"
            rf"{{{params['inertia_f']:g}}}"
        )
    elif unknown == "omega_i":
        value = params["inertia_f"] * params["omega_f"] / params["inertia_i"]
        shown = r"\omega_i"
        plugged = (
            rf"\omega_i = \frac{{{params['inertia_f']:g} \cdot {params['omega_f']:g}}}"
            rf"{{{params['inertia_i']:g}}}"
        )
    elif unknown == "inertia_f":
        if params["omega_f"] == 0:
            raise SolveServiceError("final angular velocity must be nonzero")
        value = params["inertia_i"] * params["omega_i"] / params["omega_f"]
        shown = "I_f"
        plugged = (
            rf"I_f = \frac{{{params['inertia_i']:g} \cdot {params['omega_i']:g}}}"
            rf"{{{params['omega_f']:g}}}"
        )
    else:
        if params["omega_i"] == 0:
            raise SolveServiceError("initial angular velocity must be nonzero")
        value = params["inertia_f"] * params["omega_f"] / params["omega_i"]
        shown = "I_i"
        plugged = (
            rf"I_i = \frac{{{params['inertia_f']:g} \cdot {params['omega_f']:g}}}"
            rf"{{{params['omega_i']:g}}}"
        )
    if unknown.startswith("inertia") and value <= 0:
        raise SolveServiceError("moment of inertia must be positive")
    unit = r"\text{ rad/s}" if unknown.startswith("omega") else r"\text{ kg}\,\text{m}^2"
    readable = "rad/s" if unknown.startswith("omega") else "kg*m^2"
    answer = rf"I_i\omega_i = I_f\omega_f \Rightarrow {shown} \approx {value:.2f} {unit}"
    return PhysicsResult(
        answer=answer,
        formulas=(rf"I_i\omega_i = I_f\omega_f \Rightarrow {shown}",),
        substitutions=(plugged,),
        quantities=(QuantityResult("", value, readable, number_format=".2f"),),
    )


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
            quantities=(QuantityResult("", value, "m/s", number_format=".2f"),),
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
            quantities=(QuantityResult("", value, "rad/s", number_format=".2f"),),
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
        quantities=(QuantityResult("", value, "m", number_format=".2f"),),
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
            quantities=(QuantityResult("", value, "m/s^2", number_format=".2f"),),
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
            quantities=(QuantityResult("", value, "rad/s^2", number_format=".2f"),),
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
        quantities=(QuantityResult("", value, "m", number_format=".2f"),),
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
        quantities=(QuantityResult("", value, "J", number_format=".2f"),),
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
            quantities=(QuantityResult("", value, "kg*m^2", number_format=".2f"),),
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
            quantities=(QuantityResult("", value, "kg*m^2", number_format=".2f"),),
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
            quantities=(QuantityResult("", value, "kg", number_format=".2f"),),
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
        quantities=(QuantityResult("", value, "m", number_format=".2f"),),
    )

"""Springs, oscillations, and wave solvers."""

from __future__ import annotations

import math

from app.models.schemas.math import GraphBlockSpec
from app.models.schemas.physics import (
    PhysicsIntent,
)
from app.modules.physics.solvers.common import (
    PhysicsResult,
    QuantityResult,
    _latex_num,
    _params_in_si,
)
from app.services.solving import SolveServiceError


def _oscillation_curve(t_period: float, amplitude: float | None) -> GraphBlockSpec:
    """One period-and-a-bit of x(t) = A cos(2πt/T).

    The oscillation is the thing worth seeing, so hand P3's player a curve.
    Amplitude only scales the y-axis — the shape and the period are what the
    question is about — so when none is given the plot is normalised rather
    than invented.
    """
    n_points = 100
    span = 2 * t_period
    dt = span / (n_points - 1)
    a_plot = abs(amplitude) if amplitude else 1.0
    points = [
        [round(i * dt, 4), round(a_plot * math.cos(2 * math.pi * (i * dt) / t_period), 4)]
        for i in range(n_points)
    ]
    return GraphBlockSpec(
        type="trajectory",
        expr=f"x(t) = {a_plot:g}*cos(2*pi*t/{t_period:.4g})",
        variable="t",
        x_min=0.0,
        x_max=span,
        points=points,
        title="Displacement vs. Time",
        x_label="Time (s)",
        y_label="Displacement (m)" if amplitude else "Displacement (normalised)",
        trajectory_type="position_vs_time",
    )


def solve_spring(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or "spring_force"

    # A pendulum has a length, not a spring constant, so it is answered before
    # the k lookup below rather than after it.
    if op == "pendulum_period":
        length = p["L"]
        if length <= 0:
            raise SolveServiceError("pendulum length must be positive")
        g = p.get("g", 9.81)
        if g <= 0:
            raise SolveServiceError("gravity must be positive")
        t_period = 2 * math.pi * math.sqrt(length / g)
        answer = (
            rf"T = 2\pi\sqrt{{\frac{{L}}{{g}}}} = 2\pi\sqrt{{\frac{{{length:g}}}{{{g:g}}}}} "
            rf"\approx {t_period:.2f} \text{{ s}}"
        )
        return PhysicsResult(
            answer=answer,
            formulas=(r"T = 2\pi\sqrt{\frac{L}{g}}",),
            substitutions=(rf"T = 2\pi\sqrt{{\frac{{{length:g}}}{{{g:g}}}}}",),
            quantities=(QuantityResult("", t_period, "s", number_format=".2f"),),
            graph_specs=[_oscillation_curve(t_period, p.get("x"))],
        )

    # Like the pendulum above, these need no spring constant, so they are
    # answered before the k lookup rather than after it.
    if op == "shm_frequency":
        t_period = p["period"]
        if t_period <= 0:
            raise SolveServiceError("period must be positive")
        freq = 1 / t_period
        return PhysicsResult(
            answer=(
                rf"f = \frac{{1}}{{T}} = \frac{{1}}{{{t_period:g}}} "
                rf"\approx {freq:.2f} \text{{ Hz}}"
            ),
            formulas=(r"f = \frac{1}{T}",),
            substitutions=(rf"f = \frac{{1}}{{{t_period:g}}}",),
            quantities=(QuantityResult("", freq, "Hz", number_format=".2f"),),
            graph_specs=[_oscillation_curve(t_period, p.get("x"))],
        )

    if op == "shm_max_speed":
        amplitude = p["x"]
        omega = p["omega"]
        if amplitude <= 0 or omega <= 0:
            raise SolveServiceError("amplitude and angular frequency must be positive")
        v_max = amplitude * omega
        return PhysicsResult(
            answer=(
                rf"v_{{max}} = A\omega = {amplitude:g} \cdot {omega:g} "
                rf"\approx {v_max:.2f} \text{{ m/s}}"
            ),
            formulas=(r"v_{max} = A\omega",),
            substitutions=(rf"v_{{max}} = {amplitude:g} \cdot {omega:g}",),
            quantities=(QuantityResult("", v_max, "m/s", number_format=".2f"),),
            graph_specs=[_oscillation_curve(2 * math.pi / omega, amplitude)],
        )

    k = p["k"]
    if k <= 0:
        raise SolveServiceError("spring constant must be positive")

    if op == "spring_force":
        x = p["x"]
        f_val = k * abs(x)
        return PhysicsResult(
            answer=(rf"F = kx = {k:g} \cdot {abs(x):g} \approx {f_val:.2f} \text{{ N}}"),
            formulas=(r"F = kx",),
            substitutions=(rf"F = {k:g} \cdot {abs(x):g}",),
            quantities=(QuantityResult("", f_val, "N", number_format=".2f"),),
        )

    if op == "spring_energy":
        x = p["x"]
        u_val = 0.5 * k * x * x
        return PhysicsResult(
            answer=(
                rf"U = \tfrac{{1}}{{2}} k x^2 = 0.5 \cdot {k:g} \cdot "
                rf"{_latex_num(x, square=True)} \approx {u_val:.2f} \text{{ J}}"
            ),
            formulas=(r"U = \tfrac{1}{2} k x^2",),
            substitutions=(rf"E_s = 0.5 \cdot {k:g} \cdot {_latex_num(x, square=True)}",),
            quantities=(QuantityResult("", u_val, "J", number_format=".2f"),),
        )

    if op == "shm_period":
        m = p["m"]
        if m <= 0:
            raise SolveServiceError("mass must be positive")
        t_period = 2 * math.pi * math.sqrt(m / k)
        answer = (
            rf"T = 2\pi\sqrt{{\frac{{m}}{{k}}}} = 2\pi\sqrt{{\frac{{{m:g}}}{{{k:g}}}}} "
            rf"\approx {t_period:.2f} \text{{ s}}"
        )

        spec = _oscillation_curve(t_period, p.get("x"))
        return PhysicsResult(
            answer=answer,
            formulas=(r"T = 2\pi\sqrt{\frac{m}{k}}",),
            substitutions=(rf"T = 2\pi\sqrt{{\frac{{{m:g}}}{{{k:g}}}}}",),
            quantities=(QuantityResult("", t_period, "s", number_format=".2f"),),
            graph_specs=[spec],
        )

    raise SolveServiceError(f"unsupported spring op: {op}")


# ---------------------------------------------------------------------------
# Waves: v = f lambda, f = 1/T, and source-motion Doppler shift
# ---------------------------------------------------------------------------


def solve_waves(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "string_wave_speed":
        tension = p["tension"]
        density = p["linear_density"]
        if tension < 0 or density <= 0:
            raise SolveServiceError(
                "string wave speed needs nonnegative tension and positive density"
            )
        value = math.sqrt(tension / density)
        return PhysicsResult(
            answer=(
                rf"v = \sqrt{{\frac{{T}}{{\mu}}}} = "
                rf"\sqrt{{\frac{{{tension:g}}}{{{density:g}}}}} "
                rf"\approx {value:.4g} \text{{ m/s}}"
            ),
            formulas=(r"v = \sqrt{\frac{T}{\mu}}",),
            substitutions=(rf"v = \sqrt{{\frac{{{tension:g}}}{{{density:g}}}}}",),
            quantities=(QuantityResult("", value, "m/s", number_format=".4g"),),
        )

    if op == "resonance_frequency":
        speed = p["v_wave"]
        length = p["L"]
        harmonic = p["harmonic"]
        mode_factor = p["mode_factor"]
        if speed <= 0 or length <= 0 or mode_factor not in {2.0, 4.0}:
            raise SolveServiceError("resonance needs positive speed and length")
        if harmonic < 1 or not harmonic.is_integer():
            raise SolveServiceError("the harmonic number must be a positive integer")
        if mode_factor == 4.0 and int(harmonic) % 2 == 0:
            raise SolveServiceError("a pipe closed at one end supports only odd harmonics")
        value = harmonic * speed / (mode_factor * length)
        symbolic = r"f_n = \frac{n v}{4L}" if mode_factor == 4.0 else r"f_n = \frac{n v}{2L}"
        plugged = rf"\frac{{{harmonic:g} \cdot {speed:g}}}{{{mode_factor:g} \cdot {length:g}}}"
        return PhysicsResult(
            answer=rf"{symbolic} = {plugged} \approx {value:.4g} \text{{ Hz}}",
            formulas=(symbolic,),
            substitutions=(rf"f_n = {plugged}",),
            quantities=(QuantityResult("", value, "Hz", number_format=".4g"),),
        )

    if op == "sound_intensity":
        power = p["sound_power"]
        radius = p["r"]
        if power < 0 or radius <= 0:
            raise SolveServiceError("sound intensity needs nonnegative power and positive distance")
        value = power / (4 * math.pi * radius**2)
        return PhysicsResult(
            answer=(
                rf"I = \frac{{P}}{{4\pi r^2}} = "
                rf"\frac{{{power:g}}}{{4\pi \cdot {radius:g}^2}} "
                rf"\approx {value:.4g} \text{{ W/m}}^2"
            ),
            formulas=(r"I = \frac{P}{4\pi r^2}",),
            substitutions=(rf"I = \frac{{{power:g}}}{{4\pi \cdot {radius:g}^2}}",),
            quantities=(QuantityResult("", value, "W/m^2", number_format=".4g"),),
        )

    if op == "beat_frequency":
        first, second = p["freq"], p["freq2"]
        if first < 0 or second < 0:
            raise SolveServiceError("frequencies cannot be negative")
        value = abs(first - second)
        return PhysicsResult(
            answer=(
                rf"f_b = \lvert f_1 - f_2 \rvert = "
                rf"\lvert {first:g} - {second:g} \rvert \approx {value:.4g} \text{{ Hz}}"
            ),
            formulas=(r"f_b = \lvert f_1 - f_2 \rvert",),
            substitutions=(rf"f_b = \lvert {first:g} - {second:g} \rvert",),
            quantities=(QuantityResult("", value, "Hz", number_format=".4g"),),
        )

    if op == "wave_frequency_from_period":
        t_period = p["period"]
        if t_period <= 0:
            raise SolveServiceError("period must be positive")
        freq = 1 / t_period
        return PhysicsResult(
            answer=(
                rf"f = \frac{{1}}{{T}} = \frac{{1}}{{{t_period:g}}} "
                rf"\approx {freq:.2f} \text{{ Hz}}"
            ),
            formulas=(r"f = \frac{1}{T}",),
            substitutions=(rf"f = \frac{{1}}{{{t_period:g}}}",),
            quantities=(QuantityResult("", freq, "Hz", number_format=".2f"),),
        )

    if op == "wave_period":
        freq = p["freq"]
        if freq <= 0:
            raise SolveServiceError("frequency must be positive")
        t_period = 1 / freq
        return PhysicsResult(
            answer=(
                rf"T = \frac{{1}}{{f}} = \frac{{1}}{{{freq:g}}} "
                rf"\approx {t_period:.4g} \text{{ s}}"
            ),
            formulas=(r"T = \frac{1}{f}",),
            substitutions=(rf"T = \frac{{1}}{{{freq:g}}}",),
            quantities=(QuantityResult("", t_period, "s", number_format=".4g"),),
        )

    if op == "doppler_frequency":
        source = p["v_src"]
        observer = p.get("v_obs", 0.0)
        sound = p["v_sound"]
        freq = p["freq"]
        if sound - source <= 0 or sound + observer <= 0:
            raise SolveServiceError("that motion is at or beyond the speed of sound")
        observed = freq * (sound + observer) / (sound - source)
        if "v_obs" not in p:
            motion = "approaching" if source > 0 else "receding"
            return PhysicsResult(
                answer=(
                    rf"f' = f\,\frac{{v}}{{v - v_s}} = {freq:g} \cdot "
                    rf"\frac{{{sound:g}}}{{{sound:g} - ({source:g})}} "
                    rf"\approx {observed:.2f} \text{{ Hz}}"
                ),
                formulas=(r"f' = f\,\frac{v}{v - v_s}",),
                substitutions=(
                    rf"f' = {freq:g} \cdot \frac{{{sound:g}}}{{{sound:g} - ({source:g})}}",
                ),
                quantities=(
                    QuantityResult(
                        "",
                        observed,
                        "Hz",
                        detail=f"{motion}, sound at {sound:g} m/s",
                        number_format=".2f",
                    ),
                ),
            )
        motion = "approaching" if observed > freq else "receding"
        return PhysicsResult(
            answer=(
                rf"f' = f\,\frac{{v + v_o}}{{v - v_s}} = {freq:g} \cdot "
                rf"\frac{{{sound:g} + ({observer:g})}}{{{sound:g} - ({source:g})}} "
                rf"\approx {observed:.2f} \text{{ Hz}}"
            ),
            formulas=(r"f' = f\,\frac{v + v_o}{v - v_s}",),
            substitutions=(
                rf"f' = {freq:g} \cdot \frac{{{sound:g} + ({observer:g})}}{{{sound:g} - ({source:g}"
                rf")}}",
            ),
            quantities=(
                QuantityResult(
                    "",
                    observed,
                    "Hz",
                    detail=f"{motion}, sound at {sound:g} m/s",
                    number_format=".2f",
                ),
            ),
        )

    if op == "wave_speed":
        if p["freq"] <= 0:
            raise SolveServiceError("frequency must be positive")
        if p["wavelength"] <= 0:
            raise SolveServiceError("wavelength must be positive")
        value = p["freq"] * p["wavelength"]
        return PhysicsResult(
            answer=(
                rf"v = f\lambda = {p['freq']:g} \cdot {p['wavelength']:g} "
                rf"\approx {value:.2f} \text{{ m/s}}"
            ),
            formulas=(r"v = f\lambda",),
            substitutions=(rf"v = {p['freq']:g} \cdot {p['wavelength']:g}",),
            quantities=(QuantityResult("", value, "m/s", number_format=".2f"),),
        )

    if op == "wavelength":
        if p["freq"] <= 0:
            raise SolveServiceError("frequency must be positive")
        value = p["v_wave"] / p["freq"]
        return PhysicsResult(
            answer=(
                rf"\lambda = \frac{{v}}{{f}} = \frac{{{p['v_wave']:g}}}{{{p['freq']:g}}} "
                rf"\approx {value:.2f} \text{{ m}}"
            ),
            formulas=(r"\lambda = \frac{v}{f}",),
            substitutions=(rf"\lambda = \frac{{{p['v_wave']:g}}}{{{p['freq']:g}}}",),
            quantities=(QuantityResult("", value, "m", number_format=".2f"),),
        )

    if op == "wave_frequency":
        if p["wavelength"] <= 0:
            raise SolveServiceError("wavelength must be positive")
        value = p["v_wave"] / p["wavelength"]
        return PhysicsResult(
            answer=(
                rf"f = \frac{{v}}{{\lambda}} = "
                rf"\frac{{{p['v_wave']:g}}}{{{p['wavelength']:g}}} "
                rf"\approx {value:.2f} \text{{ Hz}}"
            ),
            formulas=(r"f = \frac{v}{\lambda}",),
            substitutions=(rf"f = \frac{{{p['v_wave']:g}}}{{{p['wavelength']:g}}}",),
            quantities=(QuantityResult("", value, "Hz", number_format=".2f"),),
        )

    raise SolveServiceError(f"unsupported waves op: {op}")

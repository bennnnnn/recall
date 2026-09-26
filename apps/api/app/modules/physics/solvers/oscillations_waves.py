"""Springs, oscillations, and wave solvers."""

from __future__ import annotations

import math

from app.models.schemas.math import GraphBlockSpec
from app.models.schemas.physics import (
    PhysicsIntent,
)
from app.modules.physics.solvers.common import (
    PhysicsResult,
    _latex_num,
    _params_in_si,
)
from app.services.solving import MathServiceError


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
            raise MathServiceError("pendulum length must be positive")
        g = p.get("g", 9.81)
        if g <= 0:
            raise MathServiceError("gravity must be positive")
        t_period = 2 * math.pi * math.sqrt(length / g)
        answer = (
            rf"T = 2\pi\sqrt{{\frac{{L}}{{g}}}} = 2\pi\sqrt{{\frac{{{length:g}}}{{{g:g}}}}} "
            rf"\approx {t_period:.2f} \text{{ s}}"
        )
        return PhysicsResult(
            answer=answer,
            answer_value=f"{t_period:.2f} s",
            graph_specs=[_oscillation_curve(t_period, p.get("x"))],
        )

    # Like the pendulum above, these need no spring constant, so they are
    # answered before the k lookup rather than after it.
    if op == "shm_frequency":
        t_period = p["period"]
        if t_period <= 0:
            raise MathServiceError("period must be positive")
        freq = 1 / t_period
        return PhysicsResult(
            answer=(
                rf"f = \frac{{1}}{{T}} = \frac{{1}}{{{t_period:g}}} "
                rf"\approx {freq:.2f} \text{{ Hz}}"
            ),
            answer_value=f"{freq:.2f} Hz",
            graph_specs=[_oscillation_curve(t_period, p.get("x"))],
        )

    if op == "shm_max_speed":
        amplitude = p["x"]
        omega = p["omega"]
        if amplitude <= 0 or omega <= 0:
            raise MathServiceError("amplitude and angular frequency must be positive")
        v_max = amplitude * omega
        return PhysicsResult(
            answer=(
                rf"v_{{max}} = A\omega = {amplitude:g} \cdot {omega:g} "
                rf"\approx {v_max:.2f} \text{{ m/s}}"
            ),
            answer_value=f"{v_max:.2f} m/s",
            graph_specs=[_oscillation_curve(2 * math.pi / omega, amplitude)],
        )

    k = p["k"]
    if k <= 0:
        raise MathServiceError("spring constant must be positive")

    if op == "spring_force":
        x = p["x"]
        f_val = k * abs(x)
        return PhysicsResult(
            answer=(rf"F = kx = {k:g} \cdot {abs(x):g} \approx {f_val:.2f} \text{{ N}}"),
            answer_value=f"{f_val:.2f} N",
        )

    if op == "spring_energy":
        x = p["x"]
        u_val = 0.5 * k * x * x
        return PhysicsResult(
            answer=(
                rf"U = \tfrac{{1}}{{2}} k x^2 = 0.5 \cdot {k:g} \cdot "
                rf"{_latex_num(x, square=True)} \approx {u_val:.2f} \text{{ J}}"
            ),
            answer_value=f"{u_val:.2f} J",
        )

    if op == "shm_period":
        m = p["m"]
        if m <= 0:
            raise MathServiceError("mass must be positive")
        t_period = 2 * math.pi * math.sqrt(m / k)
        answer = (
            rf"T = 2\pi\sqrt{{\frac{{m}}{{k}}}} = 2\pi\sqrt{{\frac{{{m:g}}}{{{k:g}}}}} "
            rf"\approx {t_period:.2f} \text{{ s}}"
        )

        spec = _oscillation_curve(t_period, p.get("x"))
        return PhysicsResult(answer=answer, answer_value=f"{t_period:.2f} s", graph_specs=[spec])

    raise MathServiceError(f"unsupported spring op: {op}")


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
            raise MathServiceError(
                "string wave speed needs nonnegative tension and positive density"
            )
        value = math.sqrt(tension / density)
        return PhysicsResult(
            answer=(
                rf"v = \sqrt{{\frac{{T}}{{\mu}}}} = "
                rf"\sqrt{{\frac{{{tension:g}}}{{{density:g}}}}} "
                rf"\approx {value:.4g} \text{{ m/s}}"
            ),
            answer_value=f"{value:.4g} m/s",
        )

    if op == "resonance_frequency":
        speed = p["v_wave"]
        length = p["L"]
        harmonic = p["harmonic"]
        mode_factor = p["mode_factor"]
        if speed <= 0 or length <= 0 or mode_factor not in {2.0, 4.0}:
            raise MathServiceError("resonance needs positive speed and length")
        if harmonic < 1 or not harmonic.is_integer():
            raise MathServiceError("the harmonic number must be a positive integer")
        if mode_factor == 4.0 and int(harmonic) % 2 == 0:
            raise MathServiceError("a pipe closed at one end supports only odd harmonics")
        value = harmonic * speed / (mode_factor * length)
        symbolic = r"f_n = \frac{n v}{4L}" if mode_factor == 4.0 else r"f_n = \frac{n v}{2L}"
        return PhysicsResult(
            answer=(
                symbolic + " = "
                rf"\frac{{{harmonic:g} \cdot {speed:g}}}"
                rf"{{{mode_factor:g} \cdot {length:g}}} \approx {value:.4g} \text{{ Hz}}"
            ),
            answer_value=f"{value:.4g} Hz",
        )

    if op == "sound_intensity":
        power = p["sound_power"]
        radius = p["r"]
        if power < 0 or radius <= 0:
            raise MathServiceError("sound intensity needs nonnegative power and positive distance")
        value = power / (4 * math.pi * radius**2)
        return PhysicsResult(
            answer=(
                rf"I = \frac{{P}}{{4\pi r^2}} = "
                rf"\frac{{{power:g}}}{{4\pi \cdot {radius:g}^2}} "
                rf"\approx {value:.4g} \text{{ W/m}}^2"
            ),
            answer_value=f"{value:.4g} W/m^2",
        )

    if op == "beat_frequency":
        first, second = p["freq"], p["freq2"]
        if first < 0 or second < 0:
            raise MathServiceError("frequencies cannot be negative")
        value = abs(first - second)
        return PhysicsResult(
            answer=(
                rf"f_b = \lvert f_1 - f_2 \rvert = "
                rf"\lvert {first:g} - {second:g} \rvert \approx {value:.4g} \text{{ Hz}}"
            ),
            answer_value=f"{value:.4g} Hz",
        )

    if op == "wave_frequency_from_period":
        t_period = p["period"]
        if t_period <= 0:
            raise MathServiceError("period must be positive")
        freq = 1 / t_period
        return PhysicsResult(
            answer=(
                rf"f = \frac{{1}}{{T}} = \frac{{1}}{{{t_period:g}}} "
                rf"\approx {freq:.2f} \text{{ Hz}}"
            ),
            answer_value=f"{freq:.2f} Hz",
        )

    if op == "wave_period":
        freq = p["freq"]
        if freq <= 0:
            raise MathServiceError("frequency must be positive")
        t_period = 1 / freq
        return PhysicsResult(
            answer=(
                rf"T = \frac{{1}}{{f}} = \frac{{1}}{{{freq:g}}} "
                rf"\approx {t_period:.4g} \text{{ s}}"
            ),
            answer_value=f"{t_period:.4g} s",
        )

    if op == "doppler_frequency":
        source = p["v_src"]
        sound = p["v_sound"]
        freq = p["freq"]
        if sound - source <= 0:
            raise MathServiceError("a source at or above the speed of sound has no Doppler shift")
        observed = freq * sound / (sound - source)
        motion = "approaching" if source > 0 else "receding"
        return PhysicsResult(
            answer=(
                rf"f' = f\,\frac{{v}}{{v - v_s}} = {freq:g} \cdot "
                rf"\frac{{{sound:g}}}{{{sound:g} - ({source:g})}} "
                rf"\approx {observed:.2f} \text{{ Hz}}"
            ),
            answer_value=f"{observed:.2f} Hz ({motion}, sound at {sound:g} m/s)",
        )

    if op == "wave_speed":
        if p["freq"] <= 0:
            raise MathServiceError("frequency must be positive")
        if p["wavelength"] <= 0:
            raise MathServiceError("wavelength must be positive")
        value = p["freq"] * p["wavelength"]
        return PhysicsResult(
            answer=(
                rf"v = f\lambda = {p['freq']:g} \cdot {p['wavelength']:g} "
                rf"\approx {value:.2f} \text{{ m/s}}"
            ),
            answer_value=f"{value:.2f} m/s",
        )

    if op == "wavelength":
        if p["freq"] <= 0:
            raise MathServiceError("frequency must be positive")
        value = p["v_wave"] / p["freq"]
        return PhysicsResult(
            answer=(
                rf"\lambda = \frac{{v}}{{f}} = \frac{{{p['v_wave']:g}}}{{{p['freq']:g}}} "
                rf"\approx {value:.2f} \text{{ m}}"
            ),
            answer_value=f"{value:.2f} m",
        )

    if op == "wave_frequency":
        if p["wavelength"] <= 0:
            raise MathServiceError("wavelength must be positive")
        value = p["v_wave"] / p["wavelength"]
        return PhysicsResult(
            answer=(
                rf"f = \frac{{v}}{{\lambda}} = "
                rf"\frac{{{p['v_wave']:g}}}{{{p['wavelength']:g}}} "
                rf"\approx {value:.2f} \text{{ Hz}}"
            ),
            answer_value=f"{value:.2f} Hz",
        )

    raise MathServiceError(f"unsupported waves op: {op}")

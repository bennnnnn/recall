"""Wave solvers: v = f lambda, f = 1/T, strings, pipes and the Doppler shift."""

from __future__ import annotations

import math

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.solvers.common import PhysicsResult, QuantityResult, _params_in_si
from app.services.solving import SolveServiceError


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
            quantities=(QuantityResult("", value, "m/s"),),
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
            quantities=(QuantityResult("", value, "Hz"),),
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
            quantities=(QuantityResult("", value, "W/m^2"),),
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
            quantities=(QuantityResult("", value, "Hz"),),
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
            quantities=(QuantityResult("", freq, "Hz"),),
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
            quantities=(QuantityResult("", t_period, "s"),),
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
            quantities=(QuantityResult("", value, "m/s"),),
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
            quantities=(QuantityResult("", value, "m"),),
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
            quantities=(QuantityResult("", value, "Hz"),),
        )

    raise SolveServiceError(f"unsupported waves op: {op}")

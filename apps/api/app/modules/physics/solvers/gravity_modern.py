"""Gravitation and modern-physics solvers."""

from __future__ import annotations

import math

from app.models.schemas.physics import (
    PhysicsIntent,
)
from app.modules.physics.solvers.common import (
    _BIG_G,
    _ELECTRON_MASS,
    _ELEMENTARY_CHARGE,
    _HBAR,
    _PLANCK_H,
    _SPEED_OF_LIGHT,
    _STEFAN_BOLTZMANN,
    _WIEN_B,
    PhysicsResult,
    _latex_num,
    _params_in_si,
)
from app.modules.physics.solvers.rotation import _orbit_scene
from app.services.solving import MathServiceError


def solve_gravitation(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "gravitational_force":
        r = p["r"]
        if r <= 0:
            raise MathServiceError("separation must be positive")
        f_val = _BIG_G * p["m1"] * p["m2"] / (r * r)
        return PhysicsResult(
            answer=(
                rf"F = \frac{{G m_1 m_2}}{{r^2}} = \frac{{{_BIG_G:.5g} \cdot {p['m1']:g} "
                rf"\cdot {p['m2']:g}}}{{{_latex_num(r, square=True)}}} "
                rf"\approx {f_val:.4g} \text{{ N}}"
            ),
            answer_value=f"{f_val:.4g} N",
        )

    if op == "orbital_velocity":
        r = p["radius_body"] + p.get("altitude", 0.0)
        if r <= 0:
            raise MathServiceError("orbital radius must be positive")
        v_val = math.sqrt(_BIG_G * p["M"] / r)
        return PhysicsResult(
            answer=(
                rf"v = \sqrt{{\frac{{GM}}{{r}}}} = \sqrt{{\frac{{{_BIG_G:.5g} \cdot "
                rf"{p['M']:.4g}}}{{{r:.4g}}}}} \approx {v_val:.2f} \text{{ m/s}}"
            ),
            answer_value=f"{v_val:.2f} m/s",
            simulation_specs=[_orbit_scene(r)],
        )

    if op == "escape_velocity":
        radius = p["radius_body"]
        if radius <= 0:
            raise MathServiceError("radius must be positive")
        v_val = math.sqrt(2 * _BIG_G * p["M"] / radius)
        return PhysicsResult(
            answer=(
                rf"v_e = \sqrt{{\frac{{2GM}}{{R}}}} = \sqrt{{\frac{{2 \cdot {_BIG_G:.5g} "
                rf"\cdot {p['M']:.4g}}}{{{radius:.4g}}}}} \approx {v_val:.2f} \text{{ m/s}}"
            ),
            answer_value=f"{v_val:.2f} m/s",
        )

    if op == "surface_gravity":
        radius = p["radius_body"]
        if radius <= 0:
            raise MathServiceError("radius must be positive")
        g_val = _BIG_G * p["M"] / (radius * radius)
        return PhysicsResult(
            answer=(
                rf"g = \frac{{GM}}{{R^2}} = \frac{{{_BIG_G:.5g} \cdot {p['M']:.4g}}}"
                rf"{{{_latex_num(radius, square=True)}}} \approx {g_val:.2f} "
                rf"\text{{ m/s}}^2"
            ),
            answer_value=f"{g_val:.2f} m/s^2",
        )

    raise MathServiceError(f"unsupported gravitation op: {op}")


def solve_modern(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op in {"lorentz_factor", "time_dilation", "length_contraction"}:
        speed = abs(p["v"])
        if speed >= _SPEED_OF_LIGHT:
            raise MathServiceError("special relativity requires a speed below c")
        gamma = 1 / math.sqrt(1 - (speed / _SPEED_OF_LIGHT) ** 2)
        if op == "lorentz_factor":
            return PhysicsResult(
                answer=(
                    rf"\gamma = \frac{{1}}{{\sqrt{{1-v^2/c^2}}}} = "
                    rf"\frac{{1}}{{\sqrt{{1-({speed:g}/{_SPEED_OF_LIGHT:g})^2}}}} "
                    rf"\approx {gamma:.4g}"
                ),
                answer_value=f"{gamma:.4g}",
            )
        if op == "time_dilation":
            value = gamma * p["proper_time"]
            return PhysicsResult(
                answer=(
                    rf"\Delta t = \gamma\Delta t_0 = {gamma:.4g} \cdot "
                    rf"{p['proper_time']:g} \approx {value:.4g} \text{{ s}}"
                ),
                answer_value=f"{value:.4g} s",
            )
        value = p["proper_length"] / gamma
        return PhysicsResult(
            answer=(
                rf"L = \frac{{L_0}}{{\gamma}} = \frac{{{p['proper_length']:g}}}"
                rf"{{{gamma:.4g}}} \approx {value:.4g} \text{{ m}}"
            ),
            answer_value=f"{value:.4g} m",
        )

    if op == "photoelectric_kinetic_energy":
        if p["freq"] <= 0 or p["work_function"] < 0:
            raise MathServiceError(
                "photoelectric energy needs positive frequency and work function"
            )
        value = _PLANCK_H * p["freq"] - p["work_function"]
        if value < 0:
            raise MathServiceError("the photon energy is below the work function")
        ev = value / _ELEMENTARY_CHARGE
        return PhysicsResult(
            answer=(
                rf"K_{{max}} = hf - \phi = {_PLANCK_H:.7g} \cdot {p['freq']:g} - "
                rf"{p['work_function']:g} \approx {value:.4g} \text{{ J}}"
            ),
            answer_value=f"{value:.4g} J ({ev:.4g} eV)",
        )

    if op == "uncertainty_momentum":
        if p["uncertainty_x"] <= 0:
            raise MathServiceError("position uncertainty must be positive")
        value = _HBAR / (2 * p["uncertainty_x"])
        return PhysicsResult(
            answer=(
                rf"\Delta p_{{min}} = \frac{{\hbar}}{{2\Delta x}} = "
                rf"\frac{{{_HBAR:.7g}}}{{2 \cdot {p['uncertainty_x']:g}}} "
                rf"\approx {value:.4g} \text{{ kg}}\cdot\text{{m/s}}"
            ),
            answer_value=f"{value:.4g} kg*m/s",
        )

    if op == "particle_box_energy":
        level = p["quantum_n"]
        if p["L"] <= 0 or p["m"] <= 0 or level < 1 or not level.is_integer():
            raise MathServiceError("box energy needs positive m and L and an integer n >= 1")
        value = level**2 * _PLANCK_H**2 / (8 * p["m"] * p["L"] ** 2)
        ev = value / _ELEMENTARY_CHARGE
        return PhysicsResult(
            answer=(
                rf"E_n = \frac{{n^2h^2}}{{8mL^2}} = "
                rf"\frac{{{level:g}^2 \cdot ({_PLANCK_H:.7g})^2}}"
                rf"{{8 \cdot {p['m']:g} \cdot {p['L']:g}^2}} "
                rf"\approx {value:.4g} \text{{ J}}"
            ),
            answer_value=f"{value:.4g} J ({ev:.4g} eV)",
        )

    if op == "hydrogen_energy_level":
        level = p["quantum_n"]
        if level < 1 or not level.is_integer():
            raise MathServiceError("hydrogen energy needs an integer n >= 1")
        value = -13.6 / level**2
        return PhysicsResult(
            answer=(
                rf"E_n = -\frac{{13.6\ \text{{eV}}}}{{n^2}} = "
                rf"-\frac{{13.6}}{{{level:g}^2}} \approx {value:.4g} \text{{ eV}}"
            ),
            answer_value=f"{value:.4g} eV",
        )

    if op == "compton_shift":
        value = _PLANCK_H / (_ELECTRON_MASS * _SPEED_OF_LIGHT) * (1 - math.cos(p["angle"]))
        return PhysicsResult(
            answer=(
                rf"\Delta\lambda = \frac{{h}}{{m_ec}}(1-\cos\theta) = "
                rf"\frac{{{_PLANCK_H:.7g}}}{{{_ELECTRON_MASS:.7g} \cdot {_SPEED_OF_LIGHT:g}}}"
                rf"(1-\cos {math.degrees(p['angle']):g}^\circ) "
                rf"\approx {value:.4g} \text{{ m}}"
            ),
            answer_value=f"{value:.4g} m",
        )

    if op == "wien_peak":
        if p["temp"] <= 0:
            raise MathServiceError("blackbody temperature must be positive")
        value = _WIEN_B / p["temp"]
        return PhysicsResult(
            answer=(
                rf"\lambda_{{max}} = \frac{{b}}{{T}} = "
                rf"\frac{{{_WIEN_B:.7g}}}{{{p['temp']:g}}} "
                rf"\approx {value:.4g} \text{{ m}}"
            ),
            answer_value=f"{value:.4g} m",
        )

    if op == "stefan_boltzmann_power":
        if p["temp"] <= 0 or p["area"] <= 0 or not 0 <= p["emissivity"] <= 1:
            raise MathServiceError("radiated power needs positive T and A and 0 <= emissivity <= 1")
        value = p["emissivity"] * _STEFAN_BOLTZMANN * p["area"] * p["temp"] ** 4
        return PhysicsResult(
            answer=(
                rf"P = \epsilon\sigma AT^4 = {p['emissivity']:g} \cdot "
                rf"{_STEFAN_BOLTZMANN:.7g} \cdot {p['area']:g} \cdot {p['temp']:g}^4 "
                rf"\approx {value:.4g} \text{{ W}}"
            ),
            answer_value=f"{value:.4g} W",
        )

    if op == "photon_energy":
        if "freq" in p:
            freq = p["freq"]
            if freq <= 0:
                raise MathServiceError("photon frequency must be positive")
            value = _PLANCK_H * freq
            substitution = rf"{_PLANCK_H:.5g} \cdot {freq:.4g}"
            formula = "E = hf"
        else:
            wavelength = p["wavelength"]
            if wavelength <= 0:
                raise MathServiceError("photon wavelength must be positive")
            value = _PLANCK_H * _SPEED_OF_LIGHT / wavelength
            substitution = (
                rf"\frac{{{_PLANCK_H:.5g} \cdot {_SPEED_OF_LIGHT:.0f}}}"
                rf"{{{wavelength:.4g}}}"
            )
            formula = r"E = \frac{hc}{\lambda}"
        ev = value / _ELEMENTARY_CHARGE
        return PhysicsResult(
            answer=(
                rf"{formula} = {substitution} "
                rf"\approx {value:.4g} \text{{ J}}"
            ),
            answer_value=f"{value:.4g} J ({ev:.2f} eV)",
        )

    if op == "de_broglie_wavelength":
        momentum = p["m"] * p["v"]
        if momentum <= 0:
            raise MathServiceError("momentum must be positive")
        value = _PLANCK_H / momentum
        return PhysicsResult(
            answer=(
                rf"\lambda = \frac{{h}}{{mv}} = \frac{{{_PLANCK_H:.5g}}}"
                rf"{{{p['m']:.4g} \cdot {p['v']:.4g}}} \approx {value:.4g} \text{{ m}}"
            ),
            answer_value=f"{value:.4g} m",
        )

    if op == "half_life_remaining":
        halves = p.get("n_halves")
        if halves is None:
            if p["half_life"] <= 0:
                raise MathServiceError("half-life must be positive")
            if p["elapsed"] < 0:
                raise MathServiceError("elapsed time cannot be negative")
            halves = p["elapsed"] / p["half_life"]
        if halves < 0:
            raise MathServiceError("the number of half lives cannot be negative")
        # Answer in the unit the question used. A sample given in grams should
        # not come back in kilograms; the arithmetic is a ratio either way.
        unit = (intent.physics_units or {}).get("m", "kg")
        given = (intent.physics_params or {}).get("m", p["m"])
        value = given / (2**halves)
        return PhysicsResult(
            answer=(
                rf"N = \frac{{N_0}}{{2^n}} = \frac{{{given:g}}}{{2^{{{halves:g}}}}} "
                rf"\approx {value:.4g} \text{{ {unit}}}"
            ),
            answer_value=f"{value:.4g} {unit}",
        )

    if op == "mass_energy":
        value = p["m"] * _SPEED_OF_LIGHT**2
        return PhysicsResult(
            answer=(
                rf"E = mc^2 = {p['m']:g} \cdot ({_SPEED_OF_LIGHT:.0f})^2 "
                rf"\approx {value:.4g} \text{{ J}}"
            ),
            answer_value=f"{value:.4g} J",
        )

    raise MathServiceError(f"unsupported modern op: {op}")

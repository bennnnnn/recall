"""Gravitation solvers: Newton's law, surface gravity, orbital and escape speed."""

from __future__ import annotations

import math

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.solvers.circular import _orbit_scene
from app.modules.physics.solvers.common import (
    _BIG_G,
    PhysicsResult,
    QuantityResult,
    _latex_num,
    _params_in_si,
)
from app.services.solving import SolveServiceError


def solve_gravitation(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "gravitational_force":
        r = p["r"]
        if r <= 0:
            raise SolveServiceError("separation must be positive")
        f_val = _BIG_G * p["m1"] * p["m2"] / (r * r)
        return PhysicsResult(
            answer=(
                rf"F = \frac{{G m_1 m_2}}{{r^2}} = \frac{{{_BIG_G:.5g} \cdot {p['m1']:g} "
                rf"\cdot {p['m2']:g}}}{{{_latex_num(r, square=True)}}} "
                rf"\approx {f_val:.4g} \text{{ N}}"
            ),
            formulas=(r"F = \frac{G m_1 m_2}{r^2}",),
            substitutions=(
                rf"F = \frac{{{_BIG_G:.5g} \cdot {p['m1']:g} \cdot {p['m2']:g}}}"
                rf"{{{_latex_num(r, square=True)}}}",
            ),
            quantities=(QuantityResult("", f_val, "N"),),
        )

    if op == "orbital_velocity":
        r = p["radius_body"] + p.get("altitude", 0.0)
        if r <= 0:
            raise SolveServiceError("orbital radius must be positive")
        v_val = math.sqrt(_BIG_G * p["M"] / r)
        return PhysicsResult(
            answer=(
                rf"v = \sqrt{{\frac{{GM}}{{r}}}} = \sqrt{{\frac{{{_BIG_G:.5g} \cdot "
                rf"{p['M']:.4g}}}{{{r:.4g}}}}} \approx {v_val:.2f} \text{{ m/s}}"
            ),
            formulas=(r"v = \sqrt{\frac{GM}{r}}",),
            substitutions=(rf"v = \sqrt{{\frac{{{_BIG_G:.5g} \cdot {p['M']:.4g}}}{{{r:.4g}}}}}",),
            quantities=(QuantityResult("", v_val, "m/s"),),
            simulation_specs=[_orbit_scene(r, v_val)],
        )

    if op == "escape_velocity":
        radius = p["radius_body"]
        if radius <= 0:
            raise SolveServiceError("radius must be positive")
        v_val = math.sqrt(2 * _BIG_G * p["M"] / radius)
        return PhysicsResult(
            answer=(
                rf"v_e = \sqrt{{\frac{{2GM}}{{R}}}} = \sqrt{{\frac{{2 \cdot {_BIG_G:.5g} "
                rf"\cdot {p['M']:.4g}}}{{{radius:.4g}}}}} \approx {v_val:.2f} \text{{ m/s}}"
            ),
            formulas=(r"v_e = \sqrt{\frac{2GM}{R}}",),
            substitutions=(
                rf"v_e = \sqrt{{\frac{{2 \cdot {_BIG_G:.5g} \cdot {p['M']:.4g}}}{{{radius:.4g}}}}}",
            ),
            quantities=(QuantityResult("", v_val, "m/s"),),
        )

    if op == "surface_gravity":
        radius = p["radius_body"]
        if radius <= 0:
            raise SolveServiceError("radius must be positive")
        g_val = _BIG_G * p["M"] / (radius * radius)
        return PhysicsResult(
            answer=(
                rf"g = \frac{{GM}}{{R^2}} = \frac{{{_BIG_G:.5g} \cdot {p['M']:.4g}}}"
                rf"{{{_latex_num(radius, square=True)}}} \approx {g_val:.2f} "
                rf"\text{{ m/s}}^2"
            ),
            formulas=(r"g = \frac{GM}{R^2}",),
            substitutions=(
                rf"g = \frac{{{_BIG_G:.5g} \cdot {p['M']:.4g}}}"
                rf"{{{_latex_num(radius, square=True)}}}",
            ),
            quantities=(QuantityResult("", g_val, "m/s^2"),),
        )

    raise SolveServiceError(f"unsupported gravitation op: {op}")

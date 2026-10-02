"""Optics solvers: lens power, image distance and magnification, refraction, the critical and
Brewster angles, Malus's law, double slits and single-slit diffraction.
"""

from __future__ import annotations

import math

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.solvers.common import (
    _SPEED_OF_LIGHT,
    PhysicsResult,
    QuantityResult,
    _params_in_si,
)
from app.services.solving import SolveServiceError


def solve_optics(intent: PhysicsIntent) -> PhysicsResult:
    p = _params_in_si(intent)
    op = intent.physics_op or ""

    if op == "lens_power":
        if p["focal"] == 0:
            raise SolveServiceError("lens focal length cannot be zero")
        value = 1 / p["focal"]
        return PhysicsResult(
            answer=(
                rf"P = \frac{{1}}{{f}} = \frac{{1}}{{{p['focal']:g}}} "
                rf"\approx {value:.4g} \text{{ D}}"
            ),
            formulas=(r"P = \frac{1}{f}",),
            substitutions=(rf"P = \frac{{1}}{{{p['focal']:g}}}",),
            quantities=(QuantityResult("", value, "D"),),
        )

    if op == "double_slit_fringe_spacing":
        if p["wavelength"] <= 0 or p["L"] <= 0 or p["d"] <= 0:
            raise SolveServiceError("double-slit spacing needs positive wavelength and distances")
        value = p["wavelength"] * p["L"] / p["d"]
        return PhysicsResult(
            answer=(
                rf"\Delta y = \frac{{\lambda L}}{{d}} = "
                rf"\frac{{{p['wavelength']:g} \cdot {p['L']:g}}}{{{p['d']:g}}} "
                rf"\approx {value:.4g} \text{{ m}}"
            ),
            formulas=(r"\Delta y = \frac{\lambda L}{d}",),
            substitutions=(
                rf"\Delta y = \frac{{{p['wavelength']:g} \cdot {p['L']:g}}}{{{p['d']:g}}}",
            ),
            quantities=(QuantityResult("", value, "m"),),
        )

    if op == "diffraction_central_width":
        if p["wavelength"] <= 0 or p["L"] <= 0 or p["d"] <= 0:
            raise SolveServiceError("diffraction width needs positive wavelength and distances")
        value = 2 * p["wavelength"] * p["L"] / p["d"]
        return PhysicsResult(
            answer=(
                rf"w = \frac{{2\lambda L}}{{a}} = "
                rf"\frac{{2 \cdot {p['wavelength']:g} \cdot {p['L']:g}}}{{{p['d']:g}}} "
                rf"\approx {value:.4g} \text{{ m}}"
            ),
            formulas=(r"w = \frac{2\lambda L}{a}",),
            substitutions=(
                rf"w = \frac{{2 \cdot {p['wavelength']:g} \cdot {p['L']:g}}}{{{p['d']:g}}}",
            ),
            quantities=(QuantityResult("", value, "m"),),
        )

    if op == "malus_intensity":
        value = p["intensity0"] * math.cos(p["angle"]) ** 2
        return PhysicsResult(
            answer=(
                rf"I = I_0\cos^2\theta = {p['intensity0']:g} \cdot "
                rf"\cos^2({math.degrees(p['angle']):g}^\circ) "
                rf"\approx {value:.4g} \text{{ W/m}}^2"
            ),
            formulas=(r"I = I_0\cos^2\theta",),
            substitutions=(
                rf"I = {p['intensity0']:g} \cdot \cos^2({math.degrees(p['angle']):g}^\circ)",
            ),
            quantities=(QuantityResult("", value, "W/m^2"),),
        )

    if op == "brewster_angle":
        if p["n1"] <= 0 or p["n2"] <= 0:
            raise SolveServiceError("refractive indexes must be positive")
        value = math.degrees(math.atan(p["n2"] / p["n1"]))
        return PhysicsResult(
            answer=(
                rf"\tan\theta_B = \frac{{n_2}}{{n_1}} \Rightarrow "
                rf"\theta_B = \tan^{{-1}}\!\left(\frac{{{p['n2']:g}}}{{{p['n1']:g}}}\right) "
                rf"\approx {value:.4g}^\circ"
            ),
            formulas=(r"\theta_B = \tan^{-1}\!\left(\frac{n_2}{n_1}\right)",),
            substitutions=(
                rf"\theta_B = \tan^{{-1}}\!\left(\frac{{{p['n2']:g}}}{{{p['n1']:g}}}\right)",
            ),
            quantities=(QuantityResult("", value, "deg"),),
        )

    if op == "critical_angle":
        n = p["n1"]
        if n <= 1:
            raise SolveServiceError("total internal reflection needs an index above 1")
        theta_c = math.degrees(math.asin(1 / n))
        return PhysicsResult(
            answer=(
                rf"\theta_c = \arcsin\!\left(\frac{{1}}{{n}}\right) = "
                rf"\arcsin\!\left(\frac{{1}}{{{n:g}}}\right) \approx {theta_c:.2f}^\circ"
            ),
            formulas=(r"\theta_c = \arcsin\!\left(\frac{1}{n}\right)",),
            substitutions=(rf"\theta_c = \arcsin\!\left(\frac{{1}}{{{n:g}}}\right)",),
            quantities=(QuantityResult("", theta_c, "deg"),),
        )

    if op == "refractive_index":
        if "v_wave" in p:
            if p["v_wave"] <= 0:
                raise SolveServiceError("light speed in a medium must be positive")
            n = _SPEED_OF_LIGHT / p["v_wave"]
            return PhysicsResult(
                answer=(
                    rf"n = \frac{{c}}{{v}} = \frac{{{_SPEED_OF_LIGHT:.0f}}}"
                    rf"{{{p['v_wave']:g}}} \approx {n:.3g}"
                ),
                formulas=(r"n = \frac{c}{v}",),
                substitutions=(rf"n = \frac{{{_SPEED_OF_LIGHT:.0f}}}{{{p['v_wave']:g}}}",),
                quantities=(QuantityResult("", n, ""),),
            )
        t1, t2 = p["angle"], p["angle2"]
        if math.sin(t2) == 0:
            raise SolveServiceError("the refracted angle cannot be zero")
        n = math.sin(t1) / math.sin(t2)
        return PhysicsResult(
            answer=(
                rf"n = \frac{{\sin\theta_1}}{{\sin\theta_2}} = "
                rf"\frac{{\sin({math.degrees(t1):.1f}^\circ)}}"
                rf"{{\sin({math.degrees(t2):.1f}^\circ)}} \approx {n:.2f}"
            ),
            formulas=(r"n = \frac{\sin\theta_1}{\sin\theta_2}",),
            substitutions=(
                rf"n = \frac{{\sin({math.degrees(t1):.1f}^\circ)}}{{\sin({math.degrees(t2):.1f}"
                rf"^\circ)}}",
            ),
            quantities=(QuantityResult("", n, ""),),
        )

    if op == "magnification":
        if p["h_obj"] == 0:
            raise SolveServiceError("the object height cannot be zero")
        m_val = p["h_img"] / p["h_obj"]
        return PhysicsResult(
            answer=(
                rf"m = \frac{{h_i}}{{h_o}} = \frac{{{p['h_img']:g}}}{{{p['h_obj']:g}}} "
                rf"\approx {m_val:.2f}"
            ),
            formulas=(r"m = \frac{h_i}{h_o}",),
            substitutions=(rf"m = \frac{{{p['h_img']:g}}}{{{p['h_obj']:g}}}",),
            quantities=(QuantityResult("", m_val, ""),),
        )

    if op == "image_distance":
        focal, obj = p["focal"], p["d_obj"]
        if focal <= 0 or obj <= 0:
            raise SolveServiceError("only a converging lens with a real object is solved here")
        if obj <= focal:
            # Inside the focal length the image is virtual, and the sign that
            # says so is exactly what the conventions disagree about.
            raise SolveServiceError("an object inside the focal length forms a virtual image")
        img = 1 / (1 / focal - 1 / obj)
        return PhysicsResult(
            answer=(
                rf"\frac{{1}}{{f}} = \frac{{1}}{{u}} + \frac{{1}}{{v}} \Rightarrow v = "
                rf"\frac{{uf}}{{u - f}} = \frac{{{obj:g} \cdot {focal:g}}}"
                rf"{{{obj:g} - {focal:g}}} \approx {img:.4g} \text{{ m}}"
            ),
            formulas=(r"v = \frac{uf}{u - f}",),
            substitutions=(rf"v = \frac{{{obj:g} \cdot {focal:g}}}{{{obj:g} - {focal:g}}}",),
            quantities=(QuantityResult("", img, "m"),),
        )

    raise SolveServiceError(f"unsupported optics op: {op}")

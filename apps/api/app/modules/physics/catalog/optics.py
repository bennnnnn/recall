"""Verified optics operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "image_distance",
        "optics",
        "Thin-lens and mirror equation",
        "v",
        base_latex="\\frac{1}{f} = \\frac{1}{u} + \\frac{1}{v}",
        variables=(
            var("d_obj", "u", "meter"),
            var("focal", "f", "meter"),
        ),
    ),
    formula(
        "magnification",
        "optics",
        "Magnification formula",
        "m",
        variables=(
            var("h_img", "h_i", "meter"),
            var("h_obj", "h_o", "meter"),
        ),
    ),
    formula(
        "refractive_index",
        "optics",
        "Snell's law",
        "n",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("angle2", r"\theta_2", dimensionless=True),
            var("v_wave", "v", "meter / second"),
        ),
    ),
    formula(
        "critical_angle",
        "optics",
        "Critical-angle equation",
        "\\theta_c",
        variables=(var("n1", "n_1", dimensionless=True),),
    ),
    formula(
        "lens_power",
        "optics",
        "Lens-power formula",
        "P",
        base_latex="P = \\frac{1}{f}",
        variables=(var("focal", "f", "meter"),),
    ),
    formula(
        "double_slit_fringe_spacing",
        "optics",
        "Double-slit interference",
        "\\Delta y",
        base_latex="\\Delta y = \\frac{\\lambda L}{d}",
        variables=(
            var("L", "L", "meter"),
            var("d", "d", "meter"),
            var("wavelength", r"\lambda", "meter"),
        ),
    ),
    formula(
        "diffraction_central_width",
        "optics",
        "Single-slit diffraction",
        "w",
        base_latex="w = \\frac{2\\lambda L}{a}",
        variables=(
            var("L", "L", "meter"),
            var("d", "a", "meter"),
            var("wavelength", r"\lambda", "meter"),
        ),
    ),
    formula(
        "malus_intensity",
        "optics",
        "Malus's law",
        "I",
        base_latex="I = I_0\\cos^2\\theta",
        variables=(
            var("angle", r"\theta", dimensionless=True),
            var("intensity0", "I_0", "watt / meter ** 2"),
        ),
    ),
    formula(
        "brewster_angle",
        "optics",
        "Brewster's law",
        "\\theta_B",
        base_latex="\\tan\\theta_B = \\frac{n_2}{n_1}",
        variables=(
            var("n1", "n_1", dimensionless=True),
            var("n2", "n_2", dimensionless=True),
        ),
    ),
)

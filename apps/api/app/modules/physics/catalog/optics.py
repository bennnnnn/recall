"""Verified optics operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "image_distance",
        "optics",
        "Thin-lens and mirror equation",
        "v",
        base_latex="\\frac{1}{f} = \\frac{1}{u} + \\frac{1}{v}",
    ),
    formula("magnification", "optics", "Magnification formula", "m"),
    formula("refractive_index", "optics", "Snell's law", "n"),
    formula("critical_angle", "optics", "Critical-angle equation", "\\theta_c"),
    formula("lens_power", "optics", "Lens-power formula", "P", base_latex="P = \\frac{1}{f}"),
    formula(
        "double_slit_fringe_spacing",
        "optics",
        "Double-slit interference",
        "\\Delta y",
        base_latex="\\Delta y = \\frac{\\lambda L}{d}",
    ),
    formula(
        "diffraction_central_width",
        "optics",
        "Single-slit diffraction",
        "w",
        base_latex="w = \\frac{2\\lambda L}{a}",
    ),
    formula("malus_intensity", "optics", "Malus's law", "I", base_latex="I = I_0\\cos^2\\theta"),
    formula(
        "brewster_angle",
        "optics",
        "Brewster's law",
        "\\theta_B",
        base_latex="\\tan\\theta_B = \\frac{n_2}{n_1}",
    ),
)

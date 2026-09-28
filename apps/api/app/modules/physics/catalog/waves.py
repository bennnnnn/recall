"""Verified waves operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("wave_speed", "waves", "Wave equation", "v", base_latex="v = f\\lambda"),
    formula("wavelength", "waves", "Wave equation", "\\lambda", base_latex="v = f\\lambda"),
    formula("wave_frequency", "waves", "Wave equation", "f", base_latex="v = f\\lambda"),
    formula(
        "wave_frequency_from_period",
        "waves",
        "Frequency-period relation",
        "f",
        base_latex="f = \\frac{1}{T}",
    ),
    formula(
        "wave_period", "waves", "Frequency-period relation", "T", base_latex="f = \\frac{1}{T}"
    ),
    formula("doppler_frequency", "waves", "Doppler-effect equation", "f'"),
    formula(
        "string_wave_speed",
        "waves",
        "Wave speed on a string",
        "v",
        base_latex="v = \\sqrt{\\frac{T}{\\mu}}",
    ),
    formula(
        "resonance_frequency",
        "waves",
        "Standing-wave resonance",
        "f_n",
        base_latex="f_n = \\frac{nv}{kL}",
    ),
    formula(
        "sound_intensity",
        "waves",
        "Spherical-wave intensity",
        "I",
        base_latex="I = \\frac{P}{4\\pi r^2}",
    ),
    formula(
        "beat_frequency",
        "waves",
        "Beat-frequency relation",
        "f_b",
        base_latex="f_b = \\lvert f_1 - f_2 \\rvert",
    ),
)

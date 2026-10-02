"""Verified waves operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import Binding, FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "wave_speed",
        "waves",
        "Wave equation",
        "v",
        base_latex="v = f\\lambda",
        variables=(
            var("freq", "f", "hertz"),
            var("wavelength", r"\lambda", "meter"),
        ),
    ),
    formula(
        "wavelength",
        "waves",
        "Wave equation",
        "\\lambda",
        base_latex="v = f\\lambda",
        variables=(
            var("freq", "f", "hertz"),
            var("v_wave", "v", "meter / second"),
        ),
    ),
    formula(
        "wave_frequency",
        "waves",
        "Wave equation",
        "f",
        base_latex="v = f\\lambda",
        variables=(
            var("v_wave", "v", "meter / second"),
            var("wavelength", r"\lambda", "meter"),
        ),
    ),
    formula(
        "wave_frequency_from_period",
        "waves",
        "Frequency-period relation",
        "f",
        base_latex="f = \\frac{1}{T}",
        variables=(var("period", "T", "second"),),
    ),
    formula(
        "wave_period",
        "waves",
        "Frequency-period relation",
        "T",
        base_latex="f = \\frac{1}{T}",
        variables=(var("freq", "f", "hertz"),),
    ),
    formula(
        "doppler_frequency",
        "waves",
        "Doppler-effect equation",
        "f'",
        base_latex=r"f' = f\frac{v}{v - v_s}",
        assumptions=("the observer is stationary",),
        variants=(
            FormulaVariant(
                present=frozenset({"v_obs"}),
                latex=r"f' = f\frac{v+v_o}{v-v_s}",
                assumptions=("motion is along the line joining the source and the observer",),
            ),
        ),
        variables=(
            var("freq", "f", "hertz"),
            var("v_obs", "v_o", "meter / second"),
            var("v_sound", "v", "meter / second"),
            var("v_src", "v_s", "meter / second"),
        ),
    ),
    formula(
        "string_wave_speed",
        "waves",
        "Wave speed on a string",
        "v",
        base_latex="v = \\sqrt{\\frac{T}{\\mu}}",
        variables=(
            var("linear_density", r"\mu", "kilogram / meter"),
            var("tension", "T", "newton"),
        ),
    ),
    formula(
        "resonance_frequency",
        "waves",
        "Standing-wave resonance",
        "f_n",
        base_latex=r"f_n = \frac{nv}{2L}",
        variants=(
            FormulaVariant(
                equals=(("mode_factor", 4.0),),
                latex=r"f_n = \frac{nv}{4L}",
            ),
        ),
        variables=(
            var("L", "L", "meter"),
            var(
                "harmonic",
                "n",
                dimensionless=True,
                implied=(
                    ("fundamental", 1.0),
                    ("first harmonic", 1.0),
                    ("second harmonic", 2.0),
                    ("third harmonic", 3.0),
                ),
            ),
            # A string or an open pipe is n·v/2L; a pipe closed at one end n·v/4L.
            var(
                "mode_factor",
                "mode_factor",
                dimensionless=True,
                visible=False,
                implied=(("closed at one end", 4.0), ("string", 2.0), ("open at both ends", 2.0)),
            ),
            var("v_wave", "v", "meter / second"),
        ),
        binding=Binding(
            asks=("fundamental frequency", "frequency"),
            result=("hertz",),
            inputs=(frozenset({"L", "harmonic", "mode_factor", "v_wave"}),),
            cues=("string", "pipe"),
            nonnegative=True,
        ),
    ),
    formula(
        "sound_intensity",
        "waves",
        "Spherical-wave intensity",
        "I",
        base_latex="I = \\frac{P}{4\\pi r^2}",
        variables=(
            var("r", "r", "meter"),
            var("sound_power", "P", "watt"),
        ),
    ),
    formula(
        "beat_frequency",
        "waves",
        "Beat-frequency relation",
        "f_b",
        base_latex="f_b = \\lvert f_1 - f_2 \\rvert",
        variables=(
            var("freq", "f_1", "hertz"),
            var("freq2", "f_2", "hertz"),
        ),
    ),
)

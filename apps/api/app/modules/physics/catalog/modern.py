"""Verified modern operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "half_life_remaining",
        "modern",
        "Radioactive-decay law",
        "N",
        variables=(
            var("elapsed", "t", "second"),
            var("half_life", r"T_{1/2}", "second"),
            var("m", "m", "kilogram"),
            var("n_halves", "n", dimensionless=True),
        ),
    ),
    formula(
        "mass_energy",
        "modern",
        "Mass-energy equivalence",
        "E",
        variables=(var("m", "m", "kilogram"),),
    ),
    formula(
        "photon_energy",
        "modern",
        "Photon-energy relation",
        "E",
        variables=(
            var("freq", "f", "hertz"),
            var("wavelength", r"\lambda", "meter"),
        ),
    ),
    formula(
        "de_broglie_wavelength",
        "modern",
        "de Broglie relation",
        "\\lambda",
        variables=(
            var("m", "m", "kilogram"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "lorentz_factor",
        "modern",
        "Lorentz-factor equation",
        "\\gamma",
        base_latex="\\gamma = \\frac{1}{\\sqrt{1-v^2/c^2}}",
        variables=(var("v", "v", "meter / second"),),
    ),
    formula(
        "time_dilation",
        "modern",
        "Relativistic time dilation",
        "\\Delta t",
        base_latex="\\Delta t = \\gamma\\Delta t_0",
        variables=(
            var("proper_time", r"\Delta t_0", "second"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "length_contraction",
        "modern",
        "Relativistic length contraction",
        "L",
        base_latex="L = \\frac{L_0}{\\gamma}",
        variables=(
            var("proper_length", "L_0", "meter"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "photoelectric_kinetic_energy",
        "modern",
        "Photoelectric equation",
        "K_{max}",
        base_latex="K_{max} = hf - \\phi",
        variables=(
            var("freq", "f", "hertz"),
            var("work_function", r"\phi", "joule"),
        ),
    ),
    formula(
        "uncertainty_momentum",
        "modern",
        "Heisenberg uncertainty principle",
        "\\Delta p_{min}",
        base_latex="\\Delta p_{min} = \\frac{\\hbar}{2\\Delta x}",
        variables=(var("uncertainty_x", r"\Delta x", "meter"),),
    ),
    formula(
        "particle_box_energy",
        "modern",
        "Infinite-square-well energy",
        "E_n",
        base_latex="E_n = \\frac{n^2h^2}{8mL^2}",
        variables=(
            var("L", "L", "meter"),
            var("m", "m", "kilogram"),
            var("quantum_n", "n", dimensionless=True),
        ),
    ),
    formula(
        "hydrogen_energy_level",
        "modern",
        "Hydrogen energy-level equation",
        "E_n",
        base_latex="E_n = -\\frac{13.6\\,\\mathrm{eV}}{n^2}",
        variables=(var("quantum_n", "n", dimensionless=True),),
    ),
    formula(
        "compton_shift",
        "modern",
        "Compton-scattering equation",
        "\\Delta\\lambda",
        base_latex="\\Delta\\lambda = \\frac{h}{m_ec}(1-\\cos\\theta)",
        variables=(var("angle", r"\theta", dimensionless=True),),
    ),
    formula(
        "wien_peak",
        "modern",
        "Wien's displacement law",
        "\\lambda_{max}",
        base_latex="\\lambda_{max}T = b",
        variables=(var("temp", "T", "kelvin"),),
    ),
    formula(
        "stefan_boltzmann_power",
        "modern",
        "Stefan-Boltzmann law",
        "P",
        base_latex="P = \\epsilon\\sigma AT^4",
        variables=(
            var("area", "A", "meter ** 2"),
            var("emissivity", r"\epsilon", dimensionless=True),
            var("temp", "T", "kelvin"),
        ),
    ),
)

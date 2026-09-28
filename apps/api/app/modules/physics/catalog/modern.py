"""Verified modern operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("half_life_remaining", "modern", "Radioactive-decay law", "N"),
    formula("mass_energy", "modern", "Mass-energy equivalence", "E"),
    formula("photon_energy", "modern", "Photon-energy relation", "E"),
    formula("de_broglie_wavelength", "modern", "de Broglie relation", "\\lambda"),
    formula(
        "lorentz_factor",
        "modern",
        "Lorentz-factor equation",
        "\\gamma",
        base_latex="\\gamma = \\frac{1}{\\sqrt{1-v^2/c^2}}",
    ),
    formula(
        "time_dilation",
        "modern",
        "Relativistic time dilation",
        "\\Delta t",
        base_latex="\\Delta t = \\gamma\\Delta t_0",
    ),
    formula(
        "length_contraction",
        "modern",
        "Relativistic length contraction",
        "L",
        base_latex="L = \\frac{L_0}{\\gamma}",
    ),
    formula(
        "photoelectric_kinetic_energy",
        "modern",
        "Photoelectric equation",
        "K_{max}",
        base_latex="K_{max} = hf - \\phi",
    ),
    formula(
        "uncertainty_momentum",
        "modern",
        "Heisenberg uncertainty principle",
        "\\Delta p_{min}",
        base_latex="\\Delta p_{min} = \\frac{\\hbar}{2\\Delta x}",
    ),
    formula(
        "particle_box_energy",
        "modern",
        "Infinite-square-well energy",
        "E_n",
        base_latex="E_n = \\frac{n^2h^2}{8mL^2}",
    ),
    formula(
        "hydrogen_energy_level",
        "modern",
        "Hydrogen energy-level equation",
        "E_n",
        base_latex="E_n = -\\frac{13.6\\,\\mathrm{eV}}{n^2}",
    ),
    formula(
        "compton_shift",
        "modern",
        "Compton-scattering equation",
        "\\Delta\\lambda",
        base_latex="\\Delta\\lambda = \\frac{h}{m_ec}(1-\\cos\\theta)",
    ),
    formula(
        "wien_peak",
        "modern",
        "Wien's displacement law",
        "\\lambda_{max}",
        base_latex="\\lambda_{max}T = b",
    ),
    formula(
        "stefan_boltzmann_power",
        "modern",
        "Stefan-Boltzmann law",
        "P",
        base_latex="P = \\epsilon\\sigma AT^4",
    ),
)

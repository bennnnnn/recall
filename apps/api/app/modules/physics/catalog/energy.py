"""Verified energy operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("kinetic_energy", "energy", "Kinetic-energy formula", "KE"),
    formula("potential_energy", "energy", "Gravitational potential-energy formula", "PE"),
    formula(
        "work", "energy", "Work formula", "W", assumptions=("force parallel to the displacement",)
    ),
    formula(
        "power", "energy", "Power formula", "P", assumptions=("force parallel to the velocity",)
    ),
    formula(
        "mechanical_efficiency",
        "energy",
        "Mechanical-efficiency formula",
        "\\eta",
        base_latex="\\eta = \\frac{E_{out}}{E_{in}}",
    ),
    formula(
        "work_energy",
        "energy",
        "Work-energy theorem",
        "W_{net}",
        base_latex=r"W_{net} = \Delta K",
        assumptions=("net work equals the change in kinetic energy",),
    ),
    formula(
        "mechanical_energy_gravity",
        "energy",
        "Conservation of mechanical energy",
        "E",
        base_latex=r"\frac{1}{2}mv^2 + mgh = \text{constant}",
        assumptions=("no non-conservative work", "g is constant"),
    ),
    formula(
        "mechanical_energy_spring",
        "energy",
        "Conservation of mechanical energy",
        "E",
        base_latex=r"\frac{1}{2}mv^2 + \frac{1}{2}kx^2 = \text{constant}",
        assumptions=("no non-conservative work",),
    ),
)

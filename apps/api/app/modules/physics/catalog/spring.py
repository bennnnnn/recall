"""Verified spring operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("spring_force", "spring", "Hooke's law", "F"),
    formula("spring_energy", "spring", "Elastic potential-energy formula", "E_s"),
    formula("shm_period", "spring", "Simple-harmonic-motion equation", "T"),
    formula(
        "pendulum_period",
        "spring",
        "Simple-harmonic-motion equation",
        "T",
        assumptions=("small-angle approximation",),
    ),
    formula("shm_frequency", "spring", "Simple-harmonic-motion equation", "f"),
    formula("shm_max_speed", "spring", "Simple-harmonic-motion equation", "v_{max}"),
)

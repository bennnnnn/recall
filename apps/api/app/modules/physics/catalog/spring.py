"""Verified spring operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "spring_force",
        "spring",
        "Hooke's law",
        "F",
        variables=(
            var("k", "k", "newton / meter"),
            var("x", "x", "meter"),
        ),
    ),
    formula(
        "spring_energy",
        "spring",
        "Elastic potential-energy formula",
        "E_s",
        variables=(
            var("k", "k", "newton / meter"),
            var("x", "x", "meter"),
        ),
    ),
    formula(
        "shm_period",
        "spring",
        "Simple-harmonic-motion equation",
        "T",
        variables=(
            var("k", "k", "newton / meter"),
            var("m", "m", "kilogram"),
            var("x", "x", "meter"),
        ),
    ),
    formula(
        "pendulum_period",
        "spring",
        "Simple-harmonic-motion equation",
        "T",
        assumptions=("small-angle approximation",),
        variables=(
            var("L", "L", "meter"),
            var("g", "g", "meter / second ** 2"),
        ),
    ),
    formula(
        "shm_frequency",
        "spring",
        "Simple-harmonic-motion equation",
        "f",
        variables=(var("period", "period", "second"),),
    ),
    formula(
        "shm_max_speed",
        "spring",
        "Simple-harmonic-motion equation",
        "v_{max}",
        variables=(
            var("omega", "omega", "radian / second"),
            var("x", "x", "meter"),
        ),
    ),
)

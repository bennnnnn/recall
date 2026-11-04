"""Verified work and energy of one body: kinetic and potential energy, work, power."""

from __future__ import annotations

from app.services.law_binding.spec import Binding, FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "kinetic_energy",
        "energy",
        "Kinetic-energy formula",
        "KE",
        variables=(
            var("m", "m", "kilogram"),
            var("v", "v", "meter / second"),
        ),
        binding=Binding(
            asks=("kinetic energy",),
            result=("joule",),
            inputs=(frozenset({"m", "v"}),),
            nonnegative=True,
        ),
    ),
    formula(
        "potential_energy",
        "energy",
        "Gravitational potential-energy formula",
        "PE",
        variables=(
            var("g", "g", "meter / second ** 2"),
            var("h", "h", "meter"),
            var("m", "m", "kilogram"),
        ),
        binding=Binding(
            asks=("gravitational potential energy", "potential energy"),
            result=("joule",),
            inputs=(frozenset({"m", "h"}), frozenset({"m", "g", "h"})),
        ),
    ),
    formula(
        "work",
        "energy",
        "Work formula",
        "W",
        assumptions=("force parallel to the displacement",),
        variants=(
            FormulaVariant(
                present=frozenset({"angle"}),
                latex=r"W = Fd\cos\theta",
                assumptions=(),
            ),
        ),
        variables=(
            var("F", "F", "newton"),
            var("angle", r"\theta", dimensionless=True),
            var("d", "d", "meter"),
        ),
        binding=Binding(
            asks=("work done", "work"),
            result=("joule",),
            inputs=(frozenset({"F", "d"}), frozenset({"F", "d", "angle"})),
        ),
    ),
    formula(
        "power",
        "energy",
        "Power formula",
        "P",
        assumptions=("force parallel to the velocity",),
        assumptions_require=frozenset({"F", "v"}),
        variants=(
            FormulaVariant(
                present=frozenset({"angle"}),
                latex=r"P = Fv\cos\theta",
                assumptions=(),
            ),
        ),
        variables=(
            var("F", "F", "newton"),
            var("W", "W", "joule"),
            var("angle", r"\theta", dimensionless=True),
            var("t", "t", "second"),
            var("v", "v", "meter / second"),
        ),
        binding=Binding(
            asks=("power",),
            result=("watt",),
            inputs=(frozenset({"W", "t"}), frozenset({"F", "v"}), frozenset({"F", "v", "angle"})),
            nonnegative=True,
        ),
    ),
)

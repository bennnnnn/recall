"""Verified uniform-field operations: plates, a charge in a field, and qV."""

from __future__ import annotations

from app.modules.physics.catalog.spec import Binding, FormulaSpec, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    # The uniform field between parallel plates.
    formula(
        "plate_field",
        "magnetism",
        "Uniform electric field",
        "E",
        base_latex=r"E = \frac{V}{d}",
        assumptions=("a uniform field between parallel plates",),
        expression="V/d",
        variables=(var("V", "V", "volt"), var("d", "d", "meter")),
        binding=Binding(
            asks=("electric field strength", "field strength", "electric field"),
            result=("volt / meter",),
            inputs=(frozenset({"V", "d"}),),
            cues=("plate",),
            nonnegative=True,
        ),
    ),
    formula(
        "field_force_on_charge",
        "magnetism",
        "Electric force on a charge",
        "F",
        base_latex="F = qE",
        expression="Q*e_field",
        variables=(
            var("Q", "q", "coulomb", fallback="particle_charge"),
            var("e_field", "E", "volt / meter"),
        ),
        binding=Binding(
            asks=("force",),
            result=("newton",),
            inputs=(frozenset({"Q", "e_field"}),),
            cues=("field",),
        ),
    ),
    formula(
        "charge_energy",
        "magnetism",
        "Energy of a charge through a potential difference",
        "W",
        base_latex="W = qV",
        expression="Q*V",
        variables=(var("Q", "q", "coulomb", fallback="particle_charge"), var("V", "V", "volt")),
        binding=Binding(
            asks=("kinetic energy", "work done", "energy", "work"),
            result=("joule",),
            inputs=(frozenset({"Q", "V"}),),
            cues=(
                "accelerated through",
                "moved through",
                "through a potential",
                "potential difference",
            ),
        ),
    ),
)

"""Verified work and energy of one body: kinetic and potential energy, work, power.

Each is the catalog's arithmetic, so each is solved for any of its quantities
(``law_binding.inverse``): a stated work and force give the distance, a stated power and
time the work.
"""

from __future__ import annotations

from app.services.law_binding.spec import Binding, FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "kinetic_energy",
        "energy",
        "Kinetic-energy formula",
        "E_k",
        base_latex=r"E_k = \frac{1}{2} m v^2",
        expression="1/2*m*v**2",
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
        "E_p",
        base_latex="E_p = m g h",
        expression="m*g*h",
        variables=(
            var("g", "g", "meter / second ** 2", fallback="gravity"),
            var("h", "h", "meter"),
            var("m", "m", "kilogram"),
        ),
        binding=Binding(
            asks=("gravitational potential energy", "potential energy"),
            result=("joule",),
            # g is the planet's when not stated (``fallback``): the arithmetic has it.
            inputs=(frozenset({"m", "g", "h"}),),
            # mgh holds near a surface: no orbit, and a height under 1% of Earth's radius.
            excludes=("orbit", "satellite"),
            requires=("63710 - h",),
        ),
    ),
    formula(
        "work",
        "energy",
        "Work formula",
        "W",
        base_latex="W = Fs",
        assumptions=("force parallel to the displacement",),
        expression="F*d",
        variants=(
            FormulaVariant(
                present=frozenset({"angle"}),
                latex=r"W = Fs\cos\theta",
                assumptions=(),
                expression="F*d*cos(angle)",
            ),
        ),
        variables=(
            var("F", "F", "newton"),
            var("angle", r"\theta", dimensionless=True),
            var("d", "s", "meter"),
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
        base_latex="P = Fv",
        assumptions=("force parallel to the velocity",),
        assumptions_require=frozenset({"F", "v"}),
        expression="F*v",
        variants=(
            # The other school form, from the work done and the time it takes.
            FormulaVariant(
                present=frozenset({"W"}),
                latex=r"P = \frac{W}{t}",
                assumptions=(),
                expression="W/t",
            ),
            FormulaVariant(
                present=frozenset({"angle"}),
                latex=r"P = Fv\cos\theta",
                assumptions=(),
                expression="F*v*cos(angle)",
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
            # A force against the motion gives a negative power: 5 N at -2 m/s is -10 W.
        ),
    ),
)

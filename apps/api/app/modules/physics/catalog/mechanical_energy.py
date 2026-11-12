"""Verified work and energy of one body: kinetic and potential energy, work, power.

Each is the catalog's arithmetic, so each is solved for any of its quantities
(``law_binding.inverse``): a stated work and force give the distance, a stated power and
time the work.
"""

from __future__ import annotations

from app.modules.physics.catalog.rotation import ROLLING
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
            # A rolling body's spin carries energy too (``rolling_body_kinetic_energy``).
            excludes=ROLLING,
            # Classical only: past 8% of c, ½mv² falls short of the relativistic energy by
            # half a percent.
            requires=("0.08*c_light - v",),
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
    formula(
        "speed_from_kinetic_energy",
        "energy",
        "Kinetic energy",
        "v",
        base_latex=r"v = \sqrt{\frac{2 E_k}{m}}",
        expression="sqrt(2*kinetic/m)",
        variables=(
            var("kinetic", "E_k", "joule", words=("kinetic",)),
            var("m", "m", "kilogram"),
        ),
        binding=Binding(
            asks=("how fast", "speed", "velocity"),
            result=("meter / second",),
            inputs=(frozenset({"kinetic", "m"}),),
            cues=("kinetic energy",),
            # A rolling body keeps part of its energy as spin: 70 J on a rolling sphere is
            # 7.07 m/s, and ½mv² said 8.37 m/s (``rolling_body_kinetic_energy``).
            excludes=ROLLING,
            # Classical only: past half a percent of the rest energy ½mv² overstates the
            # speed by more than a third of a percent. An electron with 8.2e-14 J went
            # 4.24e8 m/s, faster than light, for 2.60e8 m/s.
            requires=("0.005*m*c_light**2 - kinetic",),
            nonnegative=True,
        ),
    ),
)

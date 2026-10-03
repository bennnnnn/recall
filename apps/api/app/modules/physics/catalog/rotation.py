"""Verified rotation operations."""

from __future__ import annotations

from app.services.law_binding.spec import Binding, FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    formula(
        "angular_displacement_rate",
        "rotation",
        "Angular-velocity definition",
        r"\omega",
        base_latex=r"\omega = \frac{\theta}{t}",
        variables=(
            var("t", "t", "second"),
            var("theta", r"\theta", "radian"),
        ),
    ),
    formula(
        "moment_of_inertia",
        "rotation",
        "Moment-of-inertia formula",
        "I",
        variables=(
            var("m", "m", "kilogram"),
            var("r", "r", "meter"),
            var("shape_factor", "shape_factor", dimensionless=True, visible=False),
        ),
    ),
    formula(
        "angular_momentum",
        "rotation",
        "Angular-momentum formula",
        "L",
        variables=(
            var("inertia", "I", "kilogram * meter ** 2"),
            var("omega", r"\omega", "radian / second"),
        ),
    ),
    formula(
        "rotational_kinetic_energy",
        "rotation",
        "Rotational kinetic-energy formula",
        "E_k",
        variables=(
            var("inertia", "I", "kilogram * meter ** 2"),
            var("omega", r"\omega", "radian / second"),
        ),
        binding=Binding(
            asks=("rotational kinetic energy", "rotational energy", "kinetic energy"),
            result=("joule",),
            inputs=(frozenset({"inertia", "omega"}),),
            nonnegative=True,
        ),
    ),
    formula(
        "rotational_omega",
        "rotation",
        "Rotational kinematic equation",
        r"\omega",
        base_latex=r"\omega = \omega_0 + \alpha t",
        assumptions=("constant angular acceleration",),
        variants=(
            FormulaVariant(
                latex=r"\omega^2 = \omega_0^2 + 2\alpha\Delta\theta \Rightarrow \omega",
                present=frozenset({"theta"}),
                absent=frozenset({"t"}),
                assumptions=("constant angular acceleration",),
            ),
        ),
        variables=(
            var("ang_alpha", r"\alpha", "radian / second ** 2"),
            var("omega0", r"\omega_0", "radian / second"),
            var("t", "t", "second"),
            var("theta", r"\theta", "radian"),
        ),
    ),
    formula(
        "rotational_theta",
        "rotation",
        "Rotational kinematic equation",
        r"\theta",
        base_latex=r"\theta = \theta_0 + \omega_0 t + \frac{1}{2}\alpha t^2",
        assumptions=(
            "constant angular acceleration",
            "angular displacement is measured from zero",
        ),
        variants=(
            # Displacement is the unknown, so the ω² branch is the one that
            # supplies ω and omits t. θ itself is not an input of this op.
            FormulaVariant(
                latex=r"\omega^2 = \omega_0^2 + 2\alpha\Delta\theta \Rightarrow \theta",
                present=frozenset({"omega"}),
                absent=frozenset({"t"}),
                assumptions=(
                    "constant angular acceleration",
                    "angular displacement is measured from zero",
                ),
            ),
        ),
        variables=(
            var("ang_alpha", r"\alpha", "radian / second ** 2"),
            var("omega", r"\omega", "radian / second"),
            var("omega0", r"\omega_0", "radian / second"),
            var("t", "t", "second"),
        ),
    ),
    formula(
        "rotational_alpha",
        "rotation",
        "Rotational kinematic equation",
        r"\alpha",
        base_latex=r"\omega = \omega_0 + \alpha t",
        assumptions=("constant angular acceleration",),
        variants=(
            FormulaVariant(
                latex=r"\alpha = \frac{\omega^2 - \omega_0^2}{2\Delta\theta}",
                present=frozenset({"theta"}),
                absent=frozenset({"t"}),
                assumptions=("constant angular acceleration",),
            ),
        ),
        variables=(
            var("omega", r"\omega", "radian / second"),
            var("omega0", r"\omega_0", "radian / second"),
            var("t", "t", "second"),
            var("theta", r"\theta", "radian"),
        ),
    ),
    formula(
        "torque_inertia",
        "rotation",
        "Rotational Newton's second law",
        r"\alpha",
        base_latex=r"\tau = I\alpha",
        solve_for=(("tau", r"\tau"), ("inertia", "I"), ("ang_alpha", r"\alpha")),
        variables=(
            var("ang_alpha", r"\alpha", "radian / second ** 2"),
            var("inertia", "I", "kilogram * meter ** 2"),
            var("tau", r"\tau", "newton * meter"),
        ),
    ),
    formula(
        "torque_angular_impulse",
        "rotation",
        "Angular impulse-momentum theorem",
        r"\tau",
        base_latex=r"\tau = \frac{\Delta L}{\Delta t}",
        assumptions=("torque is the average torque over the interval",),
        solve_for=(
            ("tau", r"\tau"),
            ("L_i", "L_i"),
            ("L_f", "L_f"),
            ("t", r"\Delta t"),
        ),
        variables=(
            var("L_f", "L_f", "kilogram * meter ** 2 / second"),
            var("L_i", "L_i", "kilogram * meter ** 2 / second"),
            var("t", "t", "second"),
            var("tau", r"\tau", "newton * meter"),
        ),
    ),
    formula(
        "angular_momentum_conservation",
        "rotation",
        "Conservation of angular momentum",
        r"\omega_f",
        base_latex=r"I_i\omega_i = I_f\omega_f",
        assumptions=("the system is isolated",),
        solve_for=(
            ("inertia_i", "I_i"),
            ("omega_i", r"\omega_i"),
            ("inertia_f", "I_f"),
            ("omega_f", r"\omega_f"),
        ),
        variables=(
            var("inertia_f", "I_f", "kilogram * meter ** 2"),
            var("inertia_i", "I_i", "kilogram * meter ** 2"),
            var("omega_f", r"\omega_f", "radian / second"),
            var("omega_i", r"\omega_i", "radian / second"),
        ),
    ),
    formula(
        "rolling_speed",
        "rotation",
        "Rolling-without-slipping condition",
        "v",
        base_latex=r"v = R\omega",
        assumptions=("rolling without slipping",),
        solve_for=(("v", "v"), ("omega", r"\omega"), ("r", "R")),
        variables=(
            var("omega", r"\omega", "radian / second"),
            var("r", "R", "meter"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "rolling_acceleration",
        "rotation",
        "Rolling-without-slipping condition",
        "a",
        base_latex=r"a = R\alpha",
        assumptions=("rolling without slipping",),
        solve_for=(("a", "a"), ("ang_alpha", r"\alpha"), ("r", "R")),
        variables=(
            var("a", "a", "meter / second ** 2"),
            var("ang_alpha", r"\alpha", "radian / second ** 2"),
            var("r", "R", "meter"),
        ),
    ),
    formula(
        "rolling_kinetic_energy",
        "rotation",
        "Rolling kinetic-energy formula",
        "K",
        base_latex=r"K = \frac{1}{2}Mv^2 + \frac{1}{2}I\omega^2",
        assumptions=("rolling without slipping",),
        variables=(
            var("inertia", "I", "kilogram * meter ** 2"),
            var("m", "M", "kilogram"),
            var("omega", r"\omega", "radian / second"),
            var("r", "R", "meter"),
            var("v", "v", "meter / second"),
        ),
    ),
    formula(
        "parallel_axis",
        "rotation",
        "Parallel-axis theorem",
        "I",
        base_latex=r"I = I_{cm} + Md^2",
        assumptions=("the axis is parallel to an axis through the center of mass",),
        solve_for=(("inertia", "I"), ("inertia_cm", "I_{cm}"), ("m", "M"), ("d", "d")),
        variables=(
            var("d", "d", "meter"),
            var("inertia", "I", "kilogram * meter ** 2"),
            var("inertia_cm", "I_{cm}", "kilogram * meter ** 2"),
            var("m", "m", "kilogram"),
        ),
    ),
)

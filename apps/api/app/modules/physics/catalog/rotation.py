"""Verified rotation operations."""

from __future__ import annotations

from app.modules.physics.catalog.spec import FormulaSpec, formula

SPECS: tuple[FormulaSpec, ...] = (
    formula("moment_of_inertia", "rotation", "Moment-of-inertia formula", "I"),
    formula("angular_momentum", "rotation", "Angular-momentum formula", "L"),
    formula("rotational_kinetic_energy", "rotation", "Rotational kinetic-energy formula", "E_k"),
    formula(
        "rotational_omega",
        "rotation",
        "Rotational kinematic equation",
        r"\omega",
        base_latex=r"\omega = \omega_0 + \alpha t",
        assumptions=("constant angular acceleration",),
    ),
    formula(
        "rotational_theta",
        "rotation",
        "Rotational kinematic equation",
        r"\theta",
        base_latex=r"\theta = \theta_0 + \omega_0 t + \frac{1}{2}\alpha t^2",
        assumptions=("constant angular acceleration",),
    ),
    formula(
        "rotational_alpha",
        "rotation",
        "Rotational kinematic equation",
        r"\alpha",
        base_latex=r"\omega = \omega_0 + \alpha t",
        assumptions=("constant angular acceleration",),
    ),
    formula(
        "torque_inertia",
        "rotation",
        "Rotational Newton's second law",
        r"\alpha",
        base_latex=r"\tau = I\alpha",
    ),
    formula(
        "torque_angular_impulse",
        "rotation",
        "Angular impulse-momentum theorem",
        r"\tau",
        base_latex=r"\tau = \frac{\Delta L}{\Delta t}",
        assumptions=("torque is the average torque over the interval",),
    ),
    formula(
        "angular_momentum_conservation",
        "rotation",
        "Conservation of angular momentum",
        r"\omega_f",
        base_latex=r"I_i\omega_i = I_f\omega_f",
        assumptions=("the system is isolated",),
    ),
    formula(
        "rolling_speed",
        "rotation",
        "Rolling-without-slipping condition",
        "v",
        base_latex=r"v = R\omega",
        assumptions=("rolling without slipping",),
    ),
    formula(
        "rolling_acceleration",
        "rotation",
        "Rolling-without-slipping condition",
        "a",
        base_latex=r"a = R\alpha",
        assumptions=("rolling without slipping",),
    ),
    formula(
        "rolling_kinetic_energy",
        "rotation",
        "Rolling kinetic-energy formula",
        "K",
        base_latex=r"K = \frac{1}{2}Mv^2 + \frac{1}{2}I\omega^2",
        assumptions=("rolling without slipping",),
    ),
    formula(
        "parallel_axis",
        "rotation",
        "Parallel-axis theorem",
        "I",
        base_latex=r"I = I_{cm} + Md^2",
        assumptions=("the axis is parallel to an axis through the center of mass",),
    ),
)

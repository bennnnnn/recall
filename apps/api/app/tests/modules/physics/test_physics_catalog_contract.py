"""Every solver branch must be a catalog input, and its substitution must use a given."""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from app.models.schemas.physics import PhysicsIntent
from app.modules.physics.catalog import CATALOG
from app.modules.physics.solver import solve_physics
from app.tests.modules.physics.support import extract_physics_intent

# A constant result with no quantity to insert. Everything else must show a given.
_NO_GIVEN_TO_INSERT = frozenset({"gauss_inside_shell"})

_NUMBER = re.compile(r"(?<![\d.])(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)(?![\d.])", re.IGNORECASE)


def _contains_given(text: str, value: float) -> bool:
    rendered = f"{value:g}"
    return rendered in set(_NUMBER.findall(text))


# One direct intent per solver key set. Phrasing is not involved.
_BRANCHES: tuple[tuple[str, str, dict[str, float]], ...] = (
    ("rotation", "rotational_omega", {"omega0": 2.0, "ang_alpha": 3.0, "t": 4.0}),
    ("rotation", "rotational_omega", {"omega0": 2.0, "ang_alpha": 3.0, "theta": 8.0}),
    ("rotation", "rotational_theta", {"omega0": 1.0, "ang_alpha": 2.0, "t": 3.0}),
    ("rotation", "rotational_theta", {"omega": 10.0, "omega0": 4.0, "ang_alpha": 3.0}),
    ("rotation", "rotational_alpha", {"omega": 10.0, "omega0": 4.0, "t": 2.0}),
    ("rotation", "rotational_alpha", {"omega": 10.0, "omega0": 4.0, "theta": 14.0}),
    ("rotation", "torque_inertia", {"inertia": 2.0, "ang_alpha": 3.0}),
    ("rotation", "torque_inertia", {"tau": 6.0, "inertia": 2.0}),
    ("rotation", "torque_inertia", {"tau": 6.0, "ang_alpha": 3.0}),
    ("rotation", "torque_angular_impulse", {"L_i": 4.0, "L_f": 10.0, "t": 3.0}),
    ("rotation", "torque_angular_impulse", {"L_i": 4.0, "tau": 2.0, "t": 3.0}),
    ("rotation", "torque_angular_impulse", {"L_f": 10.0, "tau": 2.0, "t": 3.0}),
    ("rotation", "torque_angular_impulse", {"L_i": 4.0, "L_f": 10.0, "tau": 2.0}),
    (
        "rotation",
        "angular_momentum_conservation",
        {"inertia_i": 4.0, "omega_i": 2.0, "inertia_f": 1.0},
    ),
    (
        "rotation",
        "angular_momentum_conservation",
        {"inertia_i": 4.0, "omega_f": 8.0, "inertia_f": 1.0},
    ),
    (
        "rotation",
        "angular_momentum_conservation",
        {"inertia_i": 4.0, "omega_i": 2.0, "omega_f": 8.0},
    ),
    (
        "rotation",
        "angular_momentum_conservation",
        {"omega_i": 2.0, "inertia_f": 1.0, "omega_f": 8.0},
    ),
    ("rotation", "rolling_speed", {"omega": 4.0, "r": 0.5}),
    ("rotation", "rolling_speed", {"v": 2.0, "r": 0.5}),
    ("rotation", "rolling_speed", {"v": 2.0, "omega": 4.0}),
    ("rotation", "rolling_acceleration", {"ang_alpha": 8.0, "r": 0.25}),
    ("rotation", "rolling_acceleration", {"a": 2.0, "r": 0.25}),
    ("rotation", "rolling_acceleration", {"a": 2.0, "ang_alpha": 8.0}),
    ("rotation", "rolling_kinetic_energy", {"m": 3.0, "inertia": 0.06, "r": 0.2, "v": 4.0}),
    ("rotation", "rolling_kinetic_energy", {"m": 3.0, "inertia": 0.06, "r": 0.2, "omega": 20.0}),
    ("rotation", "rolling_kinetic_energy", {"m": 3.0, "inertia": 0.06, "v": 4.0, "omega": 20.0}),
    ("rotation", "parallel_axis", {"inertia_cm": 2.0, "m": 3.0, "d": 4.0}),
    ("rotation", "parallel_axis", {"inertia": 50.0, "m": 3.0, "d": 4.0}),
    ("rotation", "parallel_axis", {"inertia": 50.0, "inertia_cm": 2.0, "d": 4.0}),
    ("rotation", "parallel_axis", {"inertia": 50.0, "inertia_cm": 2.0, "m": 3.0}),
    ("energy", "work_energy", {"m": 2.0, "v1": 3.0, "v2": 5.0}),
    ("energy", "work_energy", {"W": 16.0, "v1": 3.0, "v2": 5.0}),
    ("energy", "work_energy", {"W": 16.0, "m": 2.0, "v1": 3.0}),
    ("energy", "work_energy", {"W": 10.0, "m": 2.0, "v2": 5.0}),
    ("energy", "mechanical_energy_gravity", {"v1": 3.0, "h1": 5.0, "h2": 1.0, "g": 10.0}),
    ("energy", "mechanical_energy_gravity", {"v2": 3.0, "h1": 1.0, "h2": 5.0, "g": 10.0}),
    ("energy", "mechanical_energy_gravity", {"v1": 4.0, "v2": 2.0, "h1": 8.0, "g": 10.0}),
    ("energy", "mechanical_energy_gravity", {"v1": 2.0, "v2": 4.0, "h2": 8.0, "g": 10.0}),
    ("energy", "mechanical_energy_spring", {"k": 100.0, "m": 4.0, "v1": 2.0, "x1": 0.2, "x2": 0.1}),
    ("energy", "mechanical_energy_spring", {"k": 100.0, "m": 4.0, "v2": 2.0, "x1": 0.1, "x2": 0.2}),
    ("energy", "mechanical_energy_spring", {"k": 100.0, "m": 4.0, "v1": 2.0, "v2": 0.0, "x1": 0.3}),
    ("energy", "mechanical_energy_spring", {"k": 100.0, "m": 4.0, "v1": 0.0, "v2": 2.0, "x2": 0.3}),
    ("circular", "centripetal_acceleration", {"r": 2.0, "omega": 3.0}),
    ("circular", "orbital_period", {"r": 3.0, "omega": 4.0}),
    (
        "fluids",
        "bernoulli_pressure",
        {"pres1": 120000.0, "rho": 1000.0, "v1": 4.0, "v2": 2.0, "h1": 8.0, "h2": 3.0, "g": 10.0},
    ),
    ("optics", "brewster_angle", {"n1": 1.0, "n2": 1.5}),
    ("fluids", "continuity_velocity", {"A1": 0.05, "v": 3.0, "A2": 0.02}),
    ("circuit", "kirchhoff_junction", {"i_enter": 5.0, "i_leave": 2.0}),
    ("magnetism", "gauss_inside_shell", {"Q": 1e-6, "r": 0.2, "radius_body": 1.0}),
)


@pytest.mark.parametrize(("kind", "op", "params"), _BRANCHES)
def test_each_solver_branch_is_in_the_catalog_and_substitutes(
    kind: str, op: str, params: dict[str, float]
) -> None:
    spec = CATALOG[op]
    undeclared = set(params) - {variable.name for variable in spec.variables}
    assert undeclared == set()
    intent = PhysicsIntent(kind=kind, physics_op=op, physics_params=params)  # type: ignore[arg-type]
    result = solve_physics(intent)
    assert result.formulas
    assert result.substitutions
    if op in _NO_GIVEN_TO_INSERT:
        assert result.substitutions == ("E = 0",)
        return
    assert result.substitutions != result.formulas
    visible = {variable.name for variable in spec.variables if variable.visible}
    text = " ".join(result.substitutions)
    assert any(_contains_given(text, value) for name, value in params.items() if name in visible)
    if op == "work_energy" and "v1" not in params:
        assert result.substitutions[0].startswith("v_1")


def test_angular_velocity_rejects_a_supplied_omega() -> None:
    with pytest.raises(ValidationError, match="angular_velocity does not declare omega"):
        PhysicsIntent(
            kind="circular",
            physics_op="angular_velocity",
            physics_params={"r": 2.0, "omega": 3.0},
        )


def test_angular_velocity_phrasing_does_not_echo_a_supplied_omega() -> None:
    intent = extract_physics_intent(
        "what is the angular velocity at 3 rad/s around a 2 m radius circle"
    )
    if intent is not None and intent.physics_op == "angular_velocity":
        assert "omega" not in (intent.physics_params or {})


@pytest.mark.parametrize(
    ("text", "op", "required"),
    [
        (
            "Initial angular velocity of 2 rad/s and angular acceleration of 3 rad/s^2 "
            "through an angular displacement of 8 rad. Find the angular velocity.",
            "rotational_omega",
            {"omega0", "ang_alpha", "theta"},
        ),
        (
            "Angular velocity increases from 4 rad/s to 10 rad/s with angular acceleration "
            "of 3 rad/s^2. Find the angular displacement.",
            "rotational_theta",
            {"omega", "omega0", "ang_alpha"},
        ),
        (
            "Angular velocity increases from 4 rad/s to 10 rad/s through an angular "
            "displacement of 14 rad. Find the angular acceleration.",
            "rotational_alpha",
            {"omega", "omega0", "theta"},
        ),
        (
            "A 3 kg solid cylinder of radius 0.2 m rolls without slipping at 20 rad/s. "
            "Its moment of inertia is 0.06 kg m^2. Find the total kinetic energy.",
            "rolling_kinetic_energy",
            {"m", "inertia", "r", "omega"},
        ),
        (
            "centripetal acceleration at 3 rad/s with radius 2 m",
            "centripetal_acceleration",
            {"r", "omega"},
        ),
        (
            "what is the orbital period for radius 3 m at 4 rad/s",
            "orbital_period",
            {"r", "omega"},
        ),
    ],
)
def test_alternate_parameter_sentences_validate_and_solve(
    text: str, op: str, required: set[str]
) -> None:
    intent = extract_physics_intent(text)
    assert intent is not None
    assert intent.physics_op == op
    assert required <= set(intent.physics_params or {})
    result = solve_physics(intent)
    assert result.quantities
    text_rows = " ".join(result.substitutions)
    assert any(_contains_given(text_rows, (intent.physics_params or {})[name]) for name in required)

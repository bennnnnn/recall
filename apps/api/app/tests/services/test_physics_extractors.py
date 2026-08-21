"""Physics extractors — kinematics, projectile, force, energy detection."""

from __future__ import annotations

from app.services.math_tools.physics import (
    _extract_energy_intent,
    _extract_force_intent,
    _extract_kinematics_intent,
    _extract_projectile_intent,
)

# ---------------------------------------------------------------------------
# Kinematics
# ---------------------------------------------------------------------------


def test_kinematics_dropped_from_height() -> None:
    intent = _extract_kinematics_intent(
        "A ball is dropped from 20m, how long until it hits the ground?"
    )
    assert intent is not None
    assert intent.kind == "kinematics"
    assert intent.physics_op == "time_to_ground"
    assert intent.physics_params is not None
    assert intent.physics_params["h0"] == 20.0
    assert intent.physics_params["v0"] == 0.0
    assert intent.physics_params["g"] == 9.81


def test_kinematics_thrown_upward() -> None:
    intent = _extract_kinematics_intent(
        "A ball is thrown upward at 15 m/s, how long to reach the ground?"
    )
    assert intent is not None
    assert intent.kind == "kinematics"
    assert intent.physics_params is not None
    assert intent.physics_params["v0"] == 15.0


def test_kinematics_free_fall_velocity_after() -> None:
    intent = _extract_kinematics_intent(
        "An object falls from 100 m. What is its velocity after 3 seconds?"
    )
    assert intent is not None
    assert intent.kind == "kinematics"
    assert intent.physics_op == "velocity"
    assert intent.physics_params is not None
    assert intent.physics_units is not None
    assert intent.physics_params["t"] == 3.0
    assert intent.physics_units["t"] == "seconds"


def test_kinematics_position_after_duration() -> None:
    intent = _extract_kinematics_intent(
        "A ball is thrown upward at 15 m/s. What is its height after 2 seconds?"
    )
    assert intent is not None
    assert intent.physics_op == "position"
    assert intent.physics_params is not None
    assert intent.physics_params["t"] == 2.0
    assert "h0" not in intent.physics_params


def test_kinematics_after_without_duration_is_not_verified() -> None:
    assert (
        _extract_kinematics_intent(
            "An object falls from 100 m. What is its velocity after the fall?"
        )
        is None
    )


def test_kinematics_moon_gravity() -> None:
    intent = _extract_kinematics_intent(
        "A ball is dropped from 20m on the moon, how long until it hits the ground?"
    )
    assert intent is not None
    assert intent.physics_params is not None
    assert intent.physics_params["g"] == 1.62


def test_kinematics_explicit_g() -> None:
    intent = _extract_kinematics_intent(
        "A ball is dropped from 20m with g = 1.6, how long to hit the ground?"
    )
    assert intent is not None
    assert intent.physics_params is not None
    assert intent.physics_params["g"] == 1.6


def test_kinematics_no_numbers_returns_none() -> None:
    assert (
        _extract_kinematics_intent("A ball is dropped, how long until it hits the ground?") is None
    )


def test_kinematics_equation_defers() -> None:
    """An explicit equation like 'v = u + at' is algebra, not a word problem."""
    assert _extract_kinematics_intent("solve v = u + at for t") is None


# ---------------------------------------------------------------------------
# Projectile
# ---------------------------------------------------------------------------


def test_projectile_launched_at_angle() -> None:
    intent = _extract_projectile_intent(
        "A projectile is launched at 15 m/s at an angle of 45 degrees. What is its range?"
    )
    assert intent is not None
    assert intent.kind == "projectile"
    assert intent.physics_op == "range"
    assert intent.physics_params is not None
    assert intent.physics_params["v0"] == 15.0
    assert intent.physics_params["angle"] == 45.0


def test_projectile_max_height() -> None:
    intent = _extract_projectile_intent(
        "A projectile is launched at 20 m/s at 30 degrees. What is its maximum height?"
    )
    assert intent is not None
    assert intent.physics_op == "max_height"


def test_projectile_missing_angle_returns_none() -> None:
    assert (
        _extract_projectile_intent("A projectile is launched at 15 m/s. What is its range?") is None
    )


def test_projectile_missing_speed_returns_none() -> None:
    assert (
        _extract_projectile_intent("A projectile is launched at 45 degrees. What is its range?")
        is None
    )


# ---------------------------------------------------------------------------
# Force
# ---------------------------------------------------------------------------


def test_force_f_ma_solve_a() -> None:
    intent = _extract_force_intent(
        "A net force of 20 N acts on a 5 kg mass. What is the acceleration?"
    )
    assert intent is not None
    assert intent.kind == "force"
    assert intent.physics_params is not None
    assert intent.physics_params["F"] == 20.0
    assert intent.physics_params["m"] == 5.0


def test_force_f_ma_solve_f() -> None:
    intent = _extract_force_intent("A 5 kg mass accelerates at 2 m/s^2. What is the net force?")
    assert intent is not None
    assert intent.physics_params is not None
    assert intent.physics_params["m"] == 5.0
    assert intent.physics_params["a"] == 2.0


def test_force_only_one_known_returns_none() -> None:
    assert _extract_force_intent("A 5 kg mass is at rest.") is None


# ---------------------------------------------------------------------------
# Energy
# ---------------------------------------------------------------------------


def test_energy_kinetic() -> None:
    intent = _extract_energy_intent("What is the kinetic energy of a 2 kg object moving at 10 m/s?")
    assert intent is not None
    assert intent.kind == "energy"
    assert intent.physics_op == "kinetic_energy"
    assert intent.physics_params is not None
    assert intent.physics_params["m"] == 2.0
    assert intent.physics_params["v"] == 10.0


def test_energy_potential() -> None:
    intent = _extract_energy_intent(
        "What is the potential energy of a 3 kg object at a height of 5 m?"
    )
    assert intent is not None
    assert intent.physics_op == "potential_energy"
    assert intent.physics_params is not None
    assert intent.physics_params["m"] == 3.0
    assert intent.physics_params["h"] == 5.0


def test_energy_work() -> None:
    intent = _extract_energy_intent("How much work is done by a 10 N force over a distance of 4 m?")
    assert intent is not None
    assert intent.physics_op == "work"
    assert intent.physics_params is not None
    assert intent.physics_params["F"] == 10.0
    assert intent.physics_params["d"] == 4.0


def test_energy_no_knowns_returns_none() -> None:
    assert _extract_energy_intent("Tell me about energy conservation.") is None

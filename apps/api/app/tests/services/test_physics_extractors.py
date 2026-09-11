"""Physics extractors — kinematics, projectile, force, energy detection."""

from __future__ import annotations

import pytest

from app.services.math_tools.physics import (
    _VALUE_UNIT_RE,
    _detect_gravity,
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


def test_kinematics_what_does_not_bind_height_as_v0() -> None:
    intent = _extract_kinematics_intent(
        "A ball is dropped from 20m. What is the time to hit the ground?"
    )
    assert intent is not None
    assert intent.physics_params is not None
    assert intent.physics_params["h0"] == 20.0
    assert intent.physics_params["v0"] == 0.0


@pytest.mark.parametrize(
    "text",
    [
        "A ball is thrown down at 15 m/s from 20 m, how long to hit the ground?",
        "A ball is thrown downward at 15 m/s from 20 m, how long to hit the ground?",
        "A ball is launched downward at 15 m/s from 20 m, how long to hit the ground?",
    ],
)
def test_kinematics_downward_negates_v0(text: str) -> None:
    intent = _extract_kinematics_intent(text)
    assert intent is not None
    assert intent.physics_params is not None
    assert intent.physics_params["v0"] == -15.0
    assert intent.physics_params["h0"] == 20.0


def test_kinematics_mass_is_not_drop_height() -> None:
    assert _extract_kinematics_intent("A 5 kg mass is dropped from rest, how long to fall?") is None


def test_kinematics_mass_does_not_override_length_height() -> None:
    intent = _extract_kinematics_intent(
        "A 5 kg ball is dropped from 20 m, how long until it hits the ground?"
    )
    assert intent is not None
    assert intent.physics_params is not None
    assert intent.physics_params["h0"] == 20.0
    assert intent.physics_params["v0"] == 0.0


def test_kinematics_thrown_upward() -> None:
    intent = _extract_kinematics_intent(
        "A ball is thrown upward at 15 m/s, how long to reach the ground?"
    )
    assert intent is not None
    assert intent.kind == "kinematics"
    assert intent.physics_params is not None
    assert intent.physics_params["v0"] == 15.0


def test_kinematics_free_fall_distance_without_from_keyword() -> None:
    """``free fall 20 m`` has no from/height keyword; still a drop height."""
    intent = _extract_kinematics_intent("How long does an object free fall 20 m?")
    assert intent is not None
    assert intent.kind == "kinematics"
    assert intent.physics_op == "time_to_ground"
    assert intent.physics_params is not None
    assert intent.physics_params["h0"] == 20.0
    assert intent.physics_params["v0"] == 0.0
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
    assert intent.physics_params["v0"] == 0.0
    assert intent.physics_params["h0"] == 100.0


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


@pytest.mark.parametrize(
    "text",
    [
        "A ball is dropped from 20 m into a marsh. How long until it hits?",
        "A ball is dropped from 20 m in the moonlight. How long until it hits?",
        "A marshal dropped a ball from 20 m. How long until it hits?",
    ],
)
def test_kinematics_marsh_and_moonlight_are_earth_g(text: str) -> None:
    intent = _extract_kinematics_intent(text)
    assert intent is not None
    assert intent.physics_params is not None
    assert intent.physics_params["g"] == 9.81
    assert _detect_gravity(text) == 9.81


def test_kinematics_thrown_up_not_only_thrown_upward() -> None:
    intent = _extract_kinematics_intent("A ball is thrown up at 15 m/s. How long until it lands?")
    assert intent is not None
    assert intent.kind == "kinematics"
    assert intent.physics_params is not None
    assert intent.physics_params["v0"] == 15.0


def test_kinematics_speed_after_is_speed_op() -> None:
    intent = _extract_kinematics_intent("A ball is dropped from 20 m. What is its speed after 1 s?")
    assert intent is not None
    assert intent.physics_op == "speed"
    assert intent.physics_params is not None
    assert intent.physics_params["t"] == 1.0


def test_kinematics_find_v_when_t_is_velocity_not_impact_time() -> None:
    """``t = 1 s`` is a given; do not strip it and default to time_to_ground."""
    intent = _extract_kinematics_intent("A ball is dropped from 20 m; find v when t = 1 s")
    assert intent is not None
    assert intent.physics_op == "velocity"
    assert intent.physics_params is not None
    assert intent.physics_params["t"] == 1.0
    assert intent.physics_params["h0"] == 20.0


def test_kinematics_unlabeled_free_fall_height() -> None:
    intent = _extract_kinematics_intent("How long does an object free fall 20 m?")
    assert intent is not None
    assert intent.physics_op == "time_to_ground"
    assert intent.physics_params is not None
    assert intent.physics_params["h0"] == 20.0


def test_kinematics_textbook_h_assignment_is_not_algebra() -> None:
    intent = _extract_kinematics_intent(
        "A ball is dropped from h = 20 m. How long until it hits the ground?"
    )
    assert intent is not None
    assert intent.kind == "kinematics"
    assert intent.physics_params is not None
    assert intent.physics_params["h0"] == 20.0


def test_kinematics_v0_h0_assignments_are_not_algebra() -> None:
    intent = _extract_kinematics_intent(
        "A ball is dropped. Given v0 = 0 and h0 = 20 m, how long until it hits?"
    )
    assert intent is not None
    assert intent.kind == "kinematics"
    assert intent.physics_params is not None
    assert intent.physics_params["h0"] == 20.0
    assert intent.physics_params["v0"] == 0.0


def test_kinematics_car_acceleration_is_not_minus_g() -> None:
    assert (
        _extract_kinematics_intent(
            "A car speeds up from 0 to 30 m/s in 5 s. What is the acceleration of the car?"
        )
        is None
    )


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


def test_projectile_stores_cliff_height() -> None:
    intent = _extract_projectile_intent(
        "A projectile is launched at 20 m/s at 30 degrees from a 10 m cliff. What is its range?"
    )
    assert intent is not None
    assert intent.physics_params is not None
    assert intent.physics_params["h0"] == 10.0
    assert intent.physics_params["v0"] == 20.0
    assert intent.physics_params["angle"] == 30.0


def test_projectile_max_height() -> None:
    intent = _extract_projectile_intent(
        "A projectile is launched at 20 m/s at 30 degrees. What is its maximum height?"
    )
    assert intent is not None
    assert intent.physics_op == "max_height"


def test_projectile_wall_away_is_not_launch_height() -> None:
    intent = _extract_projectile_intent(
        "A projectile is launched at 20 m/s at 30 degrees. A wall is 15 m away. What is the range?"
    )
    assert intent is not None
    assert intent.physics_params is not None
    assert "h0" not in intent.physics_params
    assert intent.physics_params["v0"] == 20.0
    assert intent.physics_params["angle"] == 30.0


def test_projectile_fired_at_an_angle() -> None:
    intent = _extract_projectile_intent(
        "A projectile is fired at an angle of 25 degrees at 40 m/s. What is the range?"
    )
    assert intent is not None
    assert intent.physics_params is not None
    assert intent.physics_params["v0"] == 40.0
    assert intent.physics_params["angle"] == 25.0


def test_projectile_textbook_assignments() -> None:
    intent = _extract_projectile_intent(
        "Projectile: v0 = 20 m/s, angle = 30 deg. Find the maximum height."
    )
    assert intent is not None
    assert intent.kind == "projectile"
    assert intent.physics_op == "max_height"
    assert intent.physics_params is not None
    assert intent.physics_params["v0"] == 20.0
    assert intent.physics_params["angle"] == 30.0


def test_projectile_missing_angle_returns_none() -> None:
    assert (
        _extract_projectile_intent("A projectile is launched at 15 m/s. What is its range?") is None
    )


def test_projectile_missing_speed_returns_none() -> None:
    assert (
        _extract_projectile_intent("A projectile is launched at 45 degrees. What is its range?")
        is None
    )


def test_projectile_wall_distance_is_not_launch_height() -> None:
    from app.core.config import Settings
    from app.services import math_tools
    from app.services.math_tools.extract import extract_math_intent

    text = (
        "A projectile is launched at 20 m/s at 30 degrees. The wall is 15 m away. "
        "What is its range?"
    )
    intent = extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "projectile"
    assert intent.physics_params is not None
    assert "h0" not in intent.physics_params
    block = math_tools._build_verified_block(intent, Settings(math_tools_enabled=True))
    assert block is not None
    answer = block.canonical_answer or ""
    assert "52.72" not in answer


def test_projectile_without_wall_still_verifies() -> None:
    from app.core.config import Settings
    from app.services import math_tools
    from app.services.math_tools.extract import extract_math_intent

    text = "A projectile is launched at 20 m/s at 30 degrees. What is its range?"
    intent = extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "projectile"
    block = math_tools._build_verified_block(intent, Settings(math_tools_enabled=True))
    assert block is not None
    assert block.canonical_answer


def test_miles_per_hour_is_not_parsed_as_metres() -> None:
    from app.services.math_tools.physics import _VALUE_UNIT_RE

    hit = _VALUE_UNIT_RE.match("5 miles per hour")
    if hit is not None:
        assert (hit.group(2) or "").lower() != "m"


def test_downward_throw_mph_does_not_verify_as_five_metres_per_second() -> None:
    from app.core.config import Settings
    from app.services import math_tools
    from app.services.math_tools.extract import extract_math_intent

    text = "A ball is thrown down at 5 miles per hour from 20 m, how long to hit the ground?"
    intent = extract_math_intent(text)
    if intent is not None:
        units = intent.physics_units or {}
        params = intent.physics_params or {}
        if "v0" in params:
            assert units.get("v0", "").lower() not in {"m", "meter", "meters", "metres"}
        block = math_tools._build_verified_block(intent, Settings(math_tools_enabled=True))
        if block is not None:
            assert "1.57" not in (block.canonical_answer or "")


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


def test_force_accelerated_what_is_the_force() -> None:
    intent = _extract_force_intent("A 5 kg mass is accelerated at 2 m/s^2. What is the force.")
    assert intent is not None
    assert intent.physics_params is not None
    assert intent.physics_params["m"] == 5.0
    assert intent.physics_params["a"] == 2.0


def test_force_prefers_mass_nearest_mass_label() -> None:
    intent = _extract_force_intent(
        "A 3 kg cart is nearby. A net force of 20 N acts on a 5 kg mass. What is the acceleration?"
    )
    assert intent is not None
    assert intent.physics_params is not None
    assert intent.physics_params["m"] == 5.0
    assert intent.physics_params["F"] == 20.0


def test_force_only_one_known_returns_none() -> None:
    assert _extract_force_intent("A 5 kg mass is at rest.") is None


def test_force_does_not_claim_unsupported_friction_or_tension() -> None:
    assert _extract_force_intent("Find the friction on a 5 kg block with a 10 N load.") is None
    assert (
        _extract_force_intent("Find the tension supporting a 5 kg mass accelerating at 2 m/s^2.")
        is None
    )


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
    assert set(intent.physics_params) == {"m", "v"}


def test_energy_velocity_unit_is_not_parsed_as_length() -> None:
    intent = _extract_energy_intent("What is the kinetic energy of a 2 kg object moving at 10 m/s?")
    assert intent is not None
    assert intent.physics_params is not None
    assert "h" not in intent.physics_params
    assert "d" not in intent.physics_params


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


@pytest.mark.parametrize(
    "text",
    [
        "How much work is done by a 10 N force at an angle of 30 degrees over 4 m?",
        "How much work is done by a 10 N force at 30° over a distance of 4 m?",
        "How much work is done by a 10 N force at an angle over 4 m?",
    ],
)
def test_energy_work_at_angle_is_not_verified(text: str) -> None:
    assert _extract_energy_intent(text) is None


def test_energy_no_knowns_returns_none() -> None:
    assert _extract_energy_intent("Tell me about energy conservation.") is None


def test_energy_does_not_claim_conservation_problem() -> None:
    assert (
        _extract_energy_intent(
            "Use conservation of energy for a 2 kg cart moving at 10 m/s from a height of 5 m."
        )
        is None
    )


def test_energy_what_is_the_power_without_power_of() -> None:
    intent = _extract_energy_intent("A force of 200 N moves an object at 3 m/s. What is the power?")
    assert intent is not None
    assert intent.physics_op == "power"
    assert intent.physics_params is not None
    assert intent.physics_params["F"] == 200.0
    assert intent.physics_params["v"] == 3.0


@pytest.mark.parametrize(
    "text, unit_prefix",
    [
        ("5 miles", "mile"),
        ("20 minutes", "minute"),
        ("3 mi", "mi"),
        ("20 m/s", "m/s"),
        ("7 inches", "in"),
    ],
)
def test_value_unit_re_does_not_read_miles_as_metres(text: str, unit_prefix: str) -> None:
    match = _VALUE_UNIT_RE.match(text)
    assert match is not None
    assert (match.group(2) or "").lower().startswith(unit_prefix)

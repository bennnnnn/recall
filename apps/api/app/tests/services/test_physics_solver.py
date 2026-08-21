"""Physics solvers — SymPy symbolic kinematics/projectile/force/energy."""

from __future__ import annotations

import logging
import math

import pytest

from app.core.config import Settings
from app.models.math_schemas import MathIntent
from app.services import physics_solver
from app.services.math_service import MathServiceError
from app.services.math_tools.block import physics as physics_block

# ---------------------------------------------------------------------------
# Kinematics
# ---------------------------------------------------------------------------


def test_kinematics_time_to_ground() -> None:
    intent = MathIntent(
        kind="kinematics",
        physics_op="time_to_ground",
        physics_params={"h0": 20.0, "v0": 0.0, "g": 9.81},
        physics_units={"h0": "m", "v0": "m/s", "g": "m/s^2"},
        operation="solve",
    )
    result = physics_solver.solve_kinematics(intent)
    # t = sqrt(2*20/9.81) ≈ 2.02 s
    expected = math.sqrt(2 * 20 / 9.81)
    assert abs(float(result.answer_value.split()[0]) - expected) < 0.01
    assert len(result.graph_specs) == 1
    spec = result.graph_specs[0]
    assert spec.type == "trajectory"
    assert spec.trajectory_type == "position_vs_time"
    assert spec.x_label == "Time (s)"
    assert spec.y_label == "Height (m)"
    # First point is at t=0, h=20
    assert spec.points[0] == [0.0, 20.0]
    # Last point is at ground (h=0)
    assert spec.points[-1][1] == 0.0


def test_kinematics_time_to_ground_derivation_includes_initial_velocity() -> None:
    intent = MathIntent(
        kind="kinematics",
        physics_op="time_to_ground",
        physics_params={"h0": 0.0, "v0": 15.0, "g": 9.81},
        physics_units={"h0": "m", "v0": "m/s", "g": "m/s^2"},
        operation="solve",
    )
    result = physics_solver.solve_kinematics(intent)

    assert abs(float(result.answer_value.split()[0]) - (2 * 15.0 / 9.81)) < 0.01
    assert "v_0" in result.answer
    assert "h_0" in result.answer
    assert r"\sqrt{\frac{2 \cdot 0}{9.81}}" not in result.answer


def test_kinematics_velocity_op() -> None:
    intent = MathIntent(
        kind="kinematics",
        physics_op="velocity",
        physics_params={"h0": 20.0, "v0": 0.0, "g": 9.81, "t": 1.0},
        physics_units={"h0": "m", "v0": "m/s", "g": "m/s^2", "t": "s"},
        operation="solve",
    )
    result = physics_solver.solve_kinematics(intent)
    # v = v0 - g*t = 0 - 9.81*1 = -9.81 m/s
    assert abs(float(result.answer_value.split()[0]) - (-9.81)) < 0.01


def test_kinematics_position_op_uses_requested_time() -> None:
    intent = MathIntent(
        kind="kinematics",
        physics_op="position",
        physics_params={"h0": 20.0, "v0": 5.0, "g": 9.81, "t": 2.0},
        physics_units={"h0": "m", "v0": "m/s", "g": "m/s^2", "t": "s"},
        operation="solve",
    )
    result = physics_solver.solve_kinematics(intent)

    expected = 20.0 + 5.0 * 2.0 - 0.5 * 9.81 * 2.0**2
    assert abs(float(result.answer_value.split()[0]) - expected) < 0.01


def test_kinematics_acceleration_is_constant() -> None:
    intent = MathIntent(
        kind="kinematics",
        physics_op="acceleration",
        physics_params={"h0": 20.0, "v0": 0.0, "g": 9.81},
        physics_units={"h0": "m", "v0": "m/s", "g": "m/s^2"},
        operation="solve",
    )
    result = physics_solver.solve_kinematics(intent)
    # a = -g = -9.81 m/s^2, no graph for constant acceleration
    assert "m/s" in result.answer_value
    assert len(result.graph_specs) == 0


# ---------------------------------------------------------------------------
# Projectile
# ---------------------------------------------------------------------------


def test_projectile_range_45_degrees() -> None:
    intent = MathIntent(
        kind="projectile",
        physics_op="range",
        physics_params={"v0": 15.0, "angle": 45.0, "g": 9.81},
        physics_units={"v0": "m/s", "angle": "deg", "g": "m/s^2"},
        operation="solve",
    )
    result = physics_solver.solve_projectile(intent)
    # R = v0^2 * sin(2*45) / g = 225 * 1 / 9.81 ≈ 22.94 m
    expected = 15.0**2 * math.sin(math.radians(90)) / 9.81
    assert abs(float(result.answer_value.split()[0]) - expected) < 0.01
    assert len(result.graph_specs) == 1
    spec = result.graph_specs[0]
    assert spec.type == "trajectory"
    assert spec.trajectory_type == "parametric"
    assert spec.x_label == "Distance (m)"
    assert spec.y_label == "Height (m)"
    # First point at origin
    assert spec.points[0] == [0.0, 0.0]
    # Last point at ground
    assert spec.points[-1][1] == 0.0


def test_projectile_max_height() -> None:
    intent = MathIntent(
        kind="projectile",
        physics_op="max_height",
        physics_params={"v0": 20.0, "angle": 30.0, "g": 9.81},
        physics_units={"v0": "m/s", "angle": "deg", "g": "m/s^2"},
        operation="solve",
    )
    result = physics_solver.solve_projectile(intent)
    # H = v0^2 * sin^2(30) / (2*g) = 400 * 0.25 / 19.62 ≈ 5.10 m
    expected = 20.0**2 * math.sin(math.radians(30)) ** 2 / (2 * 9.81)
    assert abs(float(result.answer_value.split()[0]) - expected) < 0.01


# ---------------------------------------------------------------------------
# Force
# ---------------------------------------------------------------------------


def test_force_solve_acceleration() -> None:
    intent = MathIntent(
        kind="force",
        physics_op="net_force",
        physics_params={"F": 20.0, "m": 5.0},
        physics_units={"F": "N", "m": "kg"},
        operation="solve",
    )
    result = physics_solver.solve_force(intent)
    # a = F/m = 20/5 = 4 m/s^2
    assert abs(float(result.answer_value.split()[0]) - 4.0) < 0.01


def test_force_solve_force() -> None:
    intent = MathIntent(
        kind="force",
        physics_op="net_force",
        physics_params={"m": 5.0, "a": 2.0},
        physics_units={"m": "kg", "a": "m/s^2"},
        operation="solve",
    )
    result = physics_solver.solve_force(intent)
    # F = m*a = 5*2 = 10 N
    assert abs(float(result.answer_value.split()[0]) - 10.0) < 0.01


def test_force_missing_two_knowns_raises() -> None:
    intent = MathIntent(
        kind="force",
        physics_op="net_force",
        physics_params={"F": 20.0, "m": 5.0, "a": 4.0},
        physics_units={"F": "N", "m": "kg", "a": "m/s^2"},
        operation="solve",
    )
    # All three provided — solver expects exactly two.
    try:
        physics_solver.solve_force(intent)
        raise AssertionError("should have raised")
    except MathServiceError:
        pass


# ---------------------------------------------------------------------------
# Energy
# ---------------------------------------------------------------------------


def test_energy_kinetic() -> None:
    intent = MathIntent(
        kind="energy",
        physics_op="kinetic_energy",
        physics_params={"m": 2.0, "v": 10.0, "g": 9.81},
        physics_units={"m": "kg", "v": "m/s", "g": "m/s^2"},
        operation="solve",
    )
    result = physics_solver.solve_energy(intent)
    # KE = 0.5 * 2 * 10^2 = 100 J
    assert abs(float(result.answer_value.split()[0]) - 100.0) < 0.01


def test_energy_potential() -> None:
    intent = MathIntent(
        kind="energy",
        physics_op="potential_energy",
        physics_params={"m": 3.0, "h": 5.0, "g": 9.81},
        physics_units={"m": "kg", "h": "m", "g": "m/s^2"},
        operation="solve",
    )
    result = physics_solver.solve_energy(intent)
    # PE = m*g*h = 3*9.81*5 = 147.15 J
    expected = 3.0 * 9.81 * 5.0
    assert abs(float(result.answer_value.split()[0]) - expected) < 0.01


def test_energy_work() -> None:
    intent = MathIntent(
        kind="energy",
        physics_op="work",
        physics_params={"F": 10.0, "d": 4.0, "g": 9.81},
        physics_units={"F": "N", "d": "m", "g": "m/s^2"},
        operation="solve",
    )
    result = physics_solver.solve_energy(intent)
    # W = F*d = 10*4 = 40 J
    assert abs(float(result.answer_value.split()[0]) - 40.0) < 0.01


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def test_solve_physics_dispatches_by_kind() -> None:
    intent = MathIntent(
        kind="kinematics",
        physics_op="time_to_ground",
        physics_params={"h0": 20.0, "v0": 0.0, "g": 9.81},
        physics_units={"h0": "m", "v0": "m/s", "g": "m/s^2"},
        operation="solve",
    )
    result = physics_solver.solve_physics(intent)
    assert "s" in result.answer_value


def test_solve_physics_unknown_kind_raises() -> None:
    intent = MathIntent(kind="equation", lhs="x", rhs="5", operation="solve")
    try:
        physics_solver.solve_physics(intent)
        raise AssertionError("should have raised")
    except MathServiceError:
        pass


def test_physics_block_logs_expected_solver_rejection(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    intent = MathIntent(
        kind="kinematics",
        physics_op="position",
        physics_params={"h0": 20.0},
        operation="solve",
    )

    def reject(_intent: MathIntent):
        raise MathServiceError("position requires a time t")

    monkeypatch.setattr(physics_block, "solve_physics", reject)
    with caplog.at_level(logging.INFO, logger=physics_block.__name__):
        block = physics_block._build_physics_block(intent, Settings(), [])

    assert block is None
    assert "physics verification skipped" in caplog.text
    assert "position requires a time t" in caplog.text


def test_physics_block_logs_unexpected_solver_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    intent = MathIntent(
        kind="force",
        physics_op="net_force",
        physics_params={"F": 20.0, "m": 5.0},
        operation="solve",
    )

    def fail(_intent: MathIntent):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(physics_block, "solve_physics", fail)
    with caplog.at_level(logging.WARNING, logger=physics_block.__name__):
        block = physics_block._build_physics_block(intent, Settings(), [])

    assert block is None
    assert "physics verification failed" in caplog.text

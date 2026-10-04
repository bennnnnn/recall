"""Native scenes use solved physical time and the graph's sampled motion."""

import math

import pytest
from pydantic import ValidationError

from app.models.schemas.physics import PhysicsIntent, SimulationBlockSpec, SimulationBody
from app.modules.physics import extract_physics_intent
from app.modules.physics.solver import solve_physics


def test_orbit_duration_and_direction_follow_the_given_angular_velocity() -> None:
    def scene(omega: float) -> SimulationBlockSpec:
        intent = PhysicsIntent(
            kind="circular",
            physics_op="centripetal_acceleration",
            physics_params={"r": 2, "omega": omega},
            physics_units={"r": "m", "omega": "rad/s"},
        )
        return solve_physics(intent).simulation_specs[0]

    positive, negative = scene(2), scene(-4)
    assert positive.duration_s == pytest.approx(math.pi)
    assert negative.duration_s == pytest.approx(math.pi / 2)
    assert positive.bodies[0].path[1][1] > 0
    assert negative.bodies[0].path[1][1] < 0
    stationary = scene(0)
    assert stationary.duration_s is None
    assert len({tuple(point) for point in stationary.bodies[0].path}) == 1
    assert stationary.arrows == []


def test_harmonic_scene_and_graph_share_displacements_and_two_periods() -> None:
    intent = PhysicsIntent(
        kind="spring",
        physics_op="shm_max_speed",
        physics_params={"x": 0.000001, "omega": 4},
        physics_units={"x": "m", "omega": "rad/s"},
    )
    result = solve_physics(intent)
    scene, graph = result.simulation_specs[0], result.graph_specs[0]
    assert scene.type == "oscillation"
    assert scene.duration_s == pytest.approx(math.pi)
    assert graph.points is not None
    assert [point[0] for point in scene.bodies[0].path] == [point[1] for point in graph.points]
    assert len({tuple(point) for point in scene.bodies[0].path}) > 50
    assert scene.bodies[0].path[0][0] == pytest.approx(0.000001)
    assert scene.arrows == []


def test_unspecified_harmonic_amplitude_does_not_create_a_scene() -> None:
    intent = PhysicsIntent(
        kind="spring",
        physics_op="shm_period",
        physics_params={"m": 2, "k": 8},
        physics_units={"m": "kg", "k": "N/m"},
    )
    result = solve_physics(intent)
    assert result.graph_specs[0].y_label == "Displacement (normalised)"
    assert result.simulation_specs == []


def test_frequency_animation_uses_the_given_amplitude_in_si() -> None:
    intent = extract_physics_intent("find the frequency with period 2 s and amplitude 5 cm")
    assert intent is not None
    scene = solve_physics(intent).simulation_specs[0]
    assert scene.duration_s == 4
    assert scene.bodies[0].path[0][0] == pytest.approx(0.05)


def test_zero_amplitude_produces_zero_displacement() -> None:
    intent = extract_physics_intent("find the frequency with period 2 s and amplitude 0 cm")
    assert intent is not None
    result = solve_physics(intent)
    graph = result.graph_specs[0]
    assert graph.points is not None and all(point[1] == 0 for point in graph.points)
    assert graph.y_label == "Displacement (m)"
    assert result.simulation_specs == []


@pytest.mark.parametrize(
    "question",
    [
        "a ball is launched at 20 m/s at 45 degrees, find the range",
        "a 2 kg mass and a 3 kg mass hang over a pulley, find the acceleration",
        "in an elastic collision a 2 kg ball at 3 m/s hits a 1 kg ball at rest, "
        "find the final velocities",
        "Find the orbital speed of a satellite 400 km above Earth.",
    ],
)
def test_moving_scenes_carry_positive_finite_physical_duration(question: str) -> None:
    intent = extract_physics_intent(question)
    assert intent is not None
    scenes = solve_physics(intent).simulation_specs
    assert scenes
    for scene in scenes:
        assert scene.duration_s is not None and math.isfinite(scene.duration_s)
        assert scene.duration_s > 0
        assert scene.playback_rate == 1


def test_display_only_incline_motion_has_no_physical_duration() -> None:
    question = (
        "A block is released from rest on a 30 degree incline with coefficient of friction 0.2, "
        "find the acceleration"
    )
    intent = extract_physics_intent(question)
    assert intent is not None
    scene = solve_physics(intent).simulation_specs[0]
    assert scene.type == "incline"
    assert scene.duration_s is None
    assert "duration_s" not in scene.model_dump(exclude_none=True)
    path = scene.bodies[0].path
    assert path[0] != path[-1]
    assert path[-1][0] - path[-2][0] > 2 * (path[1][0] - path[0][0])


@pytest.mark.parametrize("field", ["duration_s", "playback_rate"])
@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_timing_contract_rejects_invalid_values(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        SimulationBlockSpec.model_validate(
            {"type": "orbit", "bodies": [{"path": [[1, 0], [0, 1]]}], field: value}
        )


def test_radius_must_be_finite() -> None:
    with pytest.raises(ValidationError):
        SimulationBody(path=[[0, 0], [0, 0]], radius=float("inf"))

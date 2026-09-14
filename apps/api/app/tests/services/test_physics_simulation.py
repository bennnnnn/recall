"""P14: the `simulation` fence — a scene, not a plot of one.

P3 animated the trajectory *graph*, which shows the shape of a path. Seven of
the eleven verified kinds draw nothing at all, and for several the picture is
the explanation: circular motion is the most natural animation in the subject
and had no visual whatsoever.

`GraphBlockSpec` cannot express a scene. It is an x-y plot with axes and one
curve; a scene needs bodies with sizes, a ground, and force vectors pointing
somewhere in the world rather than along an axis.

This is the first slice the ticket asked for — the spec plus projectile and
orbit. Collisions are the next one, and the spec already carries what they
need (several bodies on one clock), which is asserted here so the shape cannot
drift before they land.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.models.schemas.math import SimulationBlockSpec, SimulationBody
from app.services.math.fence import validate_math_fences
from app.services.math.tools import _build_verified_block, extract_math_intent
from app.services.physics.solver import solve_physics

PROJECTILE_Q = "a ball is thrown at 20 m/s at 30 degrees, what is the range"
CIRCULAR_Q = (
    "what is the centripetal acceleration of a car going 10 m/s around a 20 m radius corner"
)


def _settings() -> Settings:
    return Settings(math_tools_enabled=True)


def _scene(text: str) -> SimulationBlockSpec:
    intent = extract_math_intent(text)
    assert intent is not None
    specs = solve_physics(intent).simulation_specs
    assert len(specs) == 1
    return specs[0]


def _fence_body(text: str, reply: str = "Here you go.") -> dict | None:
    """The scene as it actually reaches the client, through the real pipeline."""
    intent = extract_math_intent(text)
    assert intent is not None
    out = validate_math_fences(reply, verified=_build_verified_block(intent, _settings()))
    if "```simulation" not in out:
        return None
    return json.loads(out.split("```simulation")[1].split("```")[0].strip())


# --- what each kind now draws -----------------------------------------------


def test_a_projectile_answer_carries_a_scene_as_well_as_its_graph() -> None:
    """Both, not either.

    The graph answers "what shape is the path"; the scene answers "what is
    moving, and what is pulling on it". They are different questions and the
    reply can afford both.
    """
    intent = extract_math_intent(PROJECTILE_Q)
    assert intent is not None
    result = solve_physics(intent)

    assert len(result.graph_specs) == 1
    assert len(result.simulation_specs) == 1


def test_the_scene_and_the_graph_share_one_sampled_path() -> None:
    """So the ball can never be somewhere the curve is not.

    Handing the renderer a second, separately derived path is how a picture
    starts disagreeing with itself.
    """
    intent = extract_math_intent(PROJECTILE_Q)
    assert intent is not None
    result = solve_physics(intent)

    assert result.simulation_specs[0].bodies[0].path == result.graph_specs[0].points


def test_circular_motion_finally_draws_something() -> None:
    """The kind the round-2 review found most conspicuously blank."""
    scene = _scene(CIRCULAR_Q)

    assert scene.type == "orbit"
    assert scene.centre == [0.0, 0.0]
    assert "centripetal" in scene.arrows


def test_the_orbit_is_actually_circular() -> None:
    """Every sample the same distance from the centre, at a constant angular
    step — which is what uniform circular motion is, and what makes the index
    the clock here as everywhere else."""
    import math

    scene = _scene(CIRCULAR_Q)
    path = scene.bodies[0].path
    radii = [math.hypot(x, y) for x, y in path]

    assert all(r == pytest.approx(radii[0], rel=1e-3) for r in radii)
    assert radii[0] == pytest.approx(20.0, rel=1e-3)
    # First and last sample coincide: one closed lap.
    assert path[0] == pytest.approx(path[-1], abs=1e-3)


@pytest.mark.parametrize(
    "text,expected",
    [
        (PROJECTILE_Q, "projectile_motion"),
        ("a ball is kicked at 20 m/s at 30 degrees, how high does it go", "projectile_motion"),
        (CIRCULAR_Q, "orbit"),
        ("what is the centripetal force on a 2 kg mass at 5 m/s on a 4 m radius", "orbit"),
        ("what is the period of a car going 10 m/s around a 20 m radius track", "orbit"),
    ],
)
def test_every_projectile_and_circular_op_gets_a_scene(text: str, expected: str) -> None:
    assert _scene(text).type == expected


# --- the scene is honest about what it draws --------------------------------


def test_a_projectile_scene_has_ground_under_it() -> None:
    """A projectile landing on nothing reads as a dot drifting in a box."""
    scene = _scene(PROJECTILE_Q)

    assert scene.ground is True
    assert scene.type == "projectile_motion"


def test_the_projectile_arrows_are_the_two_that_mean_something() -> None:
    """Velocity because it changes, gravity because it does not.

    A centripetal arrow on a parabola would be nonsense, and the scene does not
    carry one.
    """
    assert set(_scene(PROJECTILE_Q).arrows) == {"velocity", "gravity"}


def test_the_scene_leaves_headroom_above_the_apex() -> None:
    """The gravity arrow hangs off the body, so a box that stops at the peak
    clips it exactly where the picture is most interesting."""
    scene = _scene(PROJECTILE_Q)
    peak = max(y for _, y in scene.bodies[0].path)

    assert scene.y_max > peak


def test_the_path_stays_inside_the_scene() -> None:
    """A body leaving the box is drawn outside the SVG and simply vanishes."""
    for text in (PROJECTILE_Q, CIRCULAR_Q):
        scene = _scene(text)
        for x, y in scene.bodies[0].path:
            assert scene.x_min <= x <= scene.x_max
            assert scene.y_min <= y <= scene.y_max


# --- the fence, end to end --------------------------------------------------


def test_the_scene_reaches_the_reply_as_a_simulation_fence() -> None:
    body = _fence_body(PROJECTILE_Q)

    assert body is not None
    assert body["type"] == "projectile_motion"
    assert len(body["bodies"][0]["path"]) == 100


def test_a_circular_answer_gets_a_scene_and_no_graph() -> None:
    """Circular motion has no curve to plot — its picture is the scene."""
    intent = extract_math_intent(CIRCULAR_Q)
    assert intent is not None
    out = validate_math_fences("Here you go.", verified=_build_verified_block(intent, _settings()))

    assert "```simulation" in out
    assert "```graph" not in out


def test_a_clarifying_reply_gets_no_scene_either() -> None:
    """P12 covers every extra, and a scene is one.

    Worth pinning separately: P12 was written when there were two kinds of
    extra, and a third that slipped past the guard would put an animation under
    a question the model just said it could not answer.
    """
    assert _fence_body(PROJECTILE_Q, "Which angle do you mean — launch or elevation?") is None


def test_an_invented_scene_is_never_passed_through() -> None:
    """Server-owned, like geometry and graph. A model that writes its own
    physics animation gets it replaced by the verified one."""
    intent = extract_math_intent(PROJECTILE_Q)
    assert intent is not None
    invented = '```simulation\n{"type":"orbit","bodies":[{"path":[[0,0],[1,1]]}]}\n```'
    out = validate_math_fences(
        f"Here you go.\n\n{invented}",
        verified=_build_verified_block(intent, _settings()),
    )

    assert '"orbit"' not in out
    assert out.count("```simulation") <= 2  # one opener, one closer


def test_an_invented_scene_with_no_verified_block_is_struck_out() -> None:
    out = validate_math_fences('```simulation\n{"type":"orbit","bodies":[]}\n```')

    assert "```simulation" not in out
    assert "Could not render that diagram" in out


# --- the spec's own rules ---------------------------------------------------


def _body(**kwargs: object) -> SimulationBody:
    return SimulationBody(**{"path": [[0.0, 0.0], [1.0, 1.0]], **kwargs})  # type: ignore[arg-type]


def test_a_scene_accepts_several_bodies_on_one_clock() -> None:
    """The shape collisions need, asserted before they land so it cannot drift."""
    scene = SimulationBlockSpec(
        type="projectile_motion",
        bodies=[_body(), _body(role="secondary")],
    )

    assert len(scene.bodies) == 2
    assert scene.bodies[1].role == "secondary"


def test_bodies_sampled_at_different_rates_are_refused() -> None:
    """One clock walks them all, so unequal lengths drift apart on screen — a
    collision shown at the wrong moment, which is worse than no picture."""
    with pytest.raises(ValidationError):
        SimulationBlockSpec(
            type="projectile_motion",
            bodies=[_body(), _body(path=[[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])],
        )


def test_a_centripetal_arrow_requires_a_centre() -> None:
    """ "Toward the centre" is meaningless without one, and would be drawn
    toward the origin of the scene box instead."""
    with pytest.raises(ValidationError):
        SimulationBlockSpec(type="orbit", bodies=[_body()], arrows=["centripetal"])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"x_min": 10.0, "x_max": 0.0},
        {"y_min": 10.0, "y_max": 0.0},
    ],
)
def test_inverted_bounds_are_refused(kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        SimulationBlockSpec(type="orbit", bodies=[_body()], **kwargs)


def test_a_one_sample_path_is_not_motion() -> None:
    with pytest.raises(ValidationError):
        SimulationBlockSpec(type="orbit", bodies=[_body(path=[[0.0, 0.0]])])


def test_a_non_finite_sample_is_refused() -> None:
    with pytest.raises(ValidationError):
        SimulationBlockSpec(type="orbit", bodies=[_body(path=[[0.0, 0.0], [float("inf"), 1.0]])])


def test_the_title_defaults_rather_than_rendering_blank() -> None:
    assert SimulationBlockSpec(type="orbit", bodies=[_body()]).title == "Orbit"
    assert SimulationBlockSpec(type="projectile_motion", bodies=[_body()]).title == "Projectile"

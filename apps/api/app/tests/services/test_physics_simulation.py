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
from app.services.math.fence import _spec_fence_kind, validate_math_fences
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


# --- second slice: collisions and inclines ----------------------------------
#
# The two scenes the ticket named after the orbit. A collision is the case a
# number genuinely cannot carry — "1.00 m/s and 4.00 m/s" is the right answer
# and says nothing about which ball ends up ahead, whether either turns round,
# or that the pair keeps moving together when they stick. An incline is mostly
# a *diagram*: for two of the three friction ops the block never moves, and the
# free-body picture is what the question wanted.

ELASTIC_Q = (
    "in an elastic collision a 2 kg ball at 3 m/s hits a 1 kg ball at rest, "
    "find the final velocities"
)
INELASTIC_Q = (
    "a 2 kg ball at 3 m/s hits a 1 kg ball at rest and they stick together, find the final velocity"
)
SLIDING_Q = (
    "a block slides down a 30 degree incline with a coefficient of friction of 0.2, "
    "what is the acceleration"
)
NORMAL_Q = "what is the normal force on a 5 kg block on a 30 degree incline"
HELD_Q = (
    "a block on a 10 degree incline with a coefficient of friction of 0.5, what is the acceleration"
)


def _verified_answer(text: str) -> str | None:
    intent = extract_math_intent(text)
    if intent is None:
        return None
    block = _build_verified_block(intent, _settings())
    return None if block is None else block.canonical_answer


# Path samples ship rounded to 4 dp to keep the fence small, so one step
# carries up to 1e-4 of error and a ratio of two of them amplifies it well past
# anything worth asserting. Measuring across a long span leaves the same
# absolute error on a displacement twenty times larger.
_SPAN = 20


def _speeds(path: list[list[float]]) -> tuple[float, float]:
    """Displacement per sample well before and well after contact.

    The clock is uniform, so this *is* a speed up to one constant factor —
    which is all these comparisons need.
    """
    return (
        (path[_SPAN][0] - path[0][0]) / _SPAN,
        (path[-1][0] - path[-1 - _SPAN][0]) / _SPAN,
    )


def test_a_collision_answer_carries_two_bodies() -> None:
    scene = _scene(ELASTIC_Q)

    assert scene.type == "collision"
    assert len(scene.bodies) == 2
    assert [b.role for b in scene.bodies] == ["primary", "secondary"]


def test_the_heavier_ball_is_drawn_larger() -> None:
    """Radius from mass by cube root, since a ball's size goes with its volume.

    Two identical circles would make the scene unreadable: which one is the
    2 kg ball is the first thing a viewer needs.
    """
    scene = _scene(ELASTIC_Q)
    heavy, light = scene.bodies

    assert heavy.radius > light.radius
    assert heavy.radius / light.radius == pytest.approx(2 ** (1 / 3), rel=1e-9)


def test_the_bodies_touch_exactly_at_contact() -> None:
    """Their surfaces meet at the midpoint of the clock — neither overlapping
    (which reads as passing through each other) nor short of it."""
    scene = _scene(ELASTIC_Q)
    b1, b2 = scene.bodies
    mid = len(b1.path) // 2

    gap = b2.path[mid][0] - b1.path[mid][0]
    # Tolerance set by the 4 dp the path ships at, not by the geometry.
    assert gap == pytest.approx(b1.radius + b2.radius, abs=1e-3)


def test_the_scene_shows_the_verified_speeds() -> None:
    """2 kg at 3 m/s into 1 kg at rest gives 1 m/s and 4 m/s.

    The scene has to move at those speeds, not at some display-friendly
    approximation, or it contradicts the pill printed above it.
    """
    scene = _scene(ELASTIC_Q)
    before1, after1 = _speeds(scene.bodies[0].path)
    before2, after2 = _speeds(scene.bodies[1].path)

    assert after1 / before1 == pytest.approx(1 / 3, rel=1e-3)  # 3 m/s -> 1 m/s
    assert before2 == pytest.approx(0.0, abs=1e-9)  # at rest
    assert after2 / after1 == pytest.approx(4.0, rel=1e-3)  # 4 m/s vs 1 m/s


def test_an_elastic_collision_separates_as_fast_as_it_approached() -> None:
    """The property that *defines* elastic, visible in the scene itself.

    Relative speed is preserved, so the gap at the start and the gap at the end
    are equal — which is a stronger check than either speed alone and would
    catch the two final velocities being swapped.
    """
    scene = _scene(ELASTIC_Q)
    b1, b2 = scene.bodies

    start_gap = b2.path[0][0] - b1.path[0][0]
    end_gap = b2.path[-1][0] - b1.path[-1][0]

    assert end_gap == pytest.approx(start_gap, abs=1e-3)


def test_an_inelastic_collision_leaves_them_stuck() -> None:
    """The counterpart, and the thing the single number cannot say at all."""
    scene = _scene(INELASTIC_Q)
    b1, b2 = scene.bodies

    start_gap = b2.path[0][0] - b1.path[0][0]
    end_gap = b2.path[-1][0] - b1.path[-1][0]

    assert start_gap > end_gap
    assert end_gap == pytest.approx(b1.radius + b2.radius, abs=1e-3)
    # Moving together means identical steps.
    assert _speeds(b1.path)[1] == pytest.approx(_speeds(b2.path)[1], abs=1e-4)


def test_a_collision_shows_velocity_and_nothing_it_cannot_justify() -> None:
    """Gravity is not acting along the track and there is no centre to orbit."""
    assert _scene(ELASTIC_Q).arrows == ["velocity"]


# --- inclines ---------------------------------------------------------------


@pytest.mark.parametrize("text", [SLIDING_Q, NORMAL_Q, HELD_Q])
def test_every_incline_op_gets_a_scene(text: str) -> None:
    assert _scene(text).type == "incline"


def test_the_incline_carries_its_angle() -> None:
    """The renderer reads normal and friction off the slope, not off the
    motion, so the angle has to travel with the scene."""
    scene = _scene(SLIDING_Q)

    assert scene.incline_deg == pytest.approx(30.0)


def test_the_block_sits_on_the_slope_it_is_given() -> None:
    """Every sample lies on the stated line, so the drawn surface and the drawn
    block cannot disagree about where the slope is."""
    import math

    scene = _scene(SLIDING_Q)
    theta = math.radians(scene.incline_deg or 0.0)
    x0, y0 = scene.bodies[0].path[0]

    for x, y in scene.bodies[0].path:
        assert y == pytest.approx(y0 - (x - x0) * math.tan(theta), abs=1e-3)


def test_a_sliding_block_speeds_up() -> None:
    """s = ½at² sampled uniformly in time, so the acceleration is the thing you
    see — a block moving at a constant rate down a slope would be a lie about
    the very quantity the answer reports."""
    path = _scene(SLIDING_Q).bodies[0].path
    first = path[1][0] - path[0][0]
    last = path[-1][0] - path[-2][0]

    assert last > first * 2


def test_a_block_friction_holds_does_not_move() -> None:
    """tan(10°) < 0.5, so a = 0 — and the scene says so by standing still.

    Showing it slide would contradict the answer directly.
    """
    assert _verified_answer(HELD_Q) == "0.00 m/s^2"
    path = _scene(HELD_Q).bodies[0].path

    assert all(point == path[0] for point in path)


def test_an_incline_shows_weight_normal_and_friction() -> None:
    """The three forces the ticket named."""
    assert set(_scene(SLIDING_Q).arrows) == {"gravity", "normal", "friction"}


def test_a_frictionless_slope_draws_no_friction_arrow() -> None:
    """An arrow for a force that is not acting is worse than a missing one."""
    scene = _scene("a block slides down a frictionless 30 degree incline, what is the acceleration")

    assert "friction" not in scene.arrows
    assert {"gravity", "normal"} <= set(scene.arrows)


def test_a_flat_surface_gets_no_incline_scene() -> None:
    """Weight down and normal up is a true picture and an empty one, and with
    no slope there is no friction direction to draw — the block is not going
    anywhere for friction to oppose."""
    intent = extract_math_intent("what is the normal force on a 5 kg block")
    assert intent is not None

    assert solve_physics(intent).simulation_specs == []


def test_the_angle_ships_without_floating_point_noise() -> None:
    """It arrives here through radians, so 30 comes back as 29.999999999999996
    and would ship in the fence JSON that way."""
    body = _fence_body(SLIDING_Q)

    assert body is not None
    assert body["incline_deg"] == 30.0


# --- the spec's rules for the new fields ------------------------------------


def test_normal_and_friction_arrows_require_a_slope() -> None:
    """Both are read off the slope, and a normal force pointing the wrong way
    is a more confident lie than no arrow at all."""
    for arrow in ("normal", "friction"):
        with pytest.raises(ValidationError):
            SimulationBlockSpec(type="incline", bodies=[_body()], arrows=[arrow])  # type: ignore[list-item]


def test_a_vertical_slope_is_refused() -> None:
    """At 90 degrees it is not an incline, it is a drop."""
    with pytest.raises(ValidationError):
        SimulationBlockSpec(type="incline", bodies=[_body()], incline_deg=90.0)


def test_each_scene_kind_has_its_own_default_title() -> None:
    for kind, title in [
        ("projectile_motion", "Projectile"),
        ("orbit", "Orbit"),
        ("collision", "Collision"),
        ("incline", "Inclined Plane"),
    ]:
        assert SimulationBlockSpec(type=kind, bodies=[_body()]).title == title  # type: ignore[arg-type]


def test_the_fence_layer_knows_every_scene_kind() -> None:
    """The one table both the fence layer and the direct guard read.

    A fifth scene type added to the schema and not to this set would be
    classified as a graph — it carries `x_min` too — and rendered as an empty
    pair of axes.
    """
    import typing

    from app.models.schemas.math.simulation import SIMULATION_SPEC_TYPES, SimulationType

    assert SIMULATION_SPEC_TYPES == set(typing.get_args(SimulationType))
    for kind in SIMULATION_SPEC_TYPES:
        assert _spec_fence_kind({"type": kind}) == "simulation"

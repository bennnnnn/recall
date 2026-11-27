"""Pictures of a long physics question in many parts: its setup's free-body diagram, and its
motion's graphs worked out by the server.

Two Pro questions (2026-11-27), a 10 kg block on a 30° slope with μk 0.20 in ten parts and an
Atwood machine of 5 kg and 3 kg in ten parts, each asked for a free-body diagram and s-t, v-t
and a-t graphs, and drew nothing: the readers read the whole question (its asks, its times
and distances, a list of givens repeating the words) as no one scene; "between the block and
the plane is 0.20", "μₖ = 0.20" and "a frictionless pulley" were read as no coefficient or as
friction; the forces reader took no question over 600 characters; and no block could say a
motion whose speeds are all answers.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.force_pictures import force_picture
from app.modules.physics.scene_drawing.build import physics_fences
from app.modules.physics.scene_drawing.figure_read import _blocks, normalized
from app.modules.physics.solvers.force_scenes import _atwood_scene
from app.services.question_parts import statement_before_parts

pytestmark = pytest.mark.usefixtures("thread_sympy_executor")

_INCLINE = """PHYSICS CHALLENGE: Block on an Inclined Plane with Friction

A block of mass 10 kg rests on an inclined plane angled at 30° above the horizontal.

The coefficient of kinetic friction between the block and the plane is 0.20.

The block is released from rest and slides down the incline.

Given:
- Mass: m = 10 kg
- Incline angle: θ = 30°
- Coefficient of kinetic friction: μₖ = 0.20
- Gravitational acceleration: g = 9.81 m/s²
- Initial velocity: u = 0 m/s

REQUIRED:

1. Draw a free-body diagram showing:
   - Gravitational force (weight).
   - Normal force.
   - Frictional force.
   - Components of gravitational force parallel and perpendicular to the incline.

2. Calculate the weight of the block.

3. Resolve gravitational force into:
   - Parallel component.
   - Perpendicular component.

4. Calculate the normal force acting on the block.

5. Calculate the kinetic friction force.

6. Apply Newton's Second Law to determine the acceleration of the block down the incline.

7. Calculate:
   - Velocity after 2 seconds.
   - Distance traveled after 2 seconds.
   - Time required to travel 5 meters.
   - Velocity after traveling 5 meters.

8. GRAPHING:
   Generate three graphs over the first 5 seconds:
   - Displacement versus time.
   - Velocity versus time.
   - Acceleration versus time.

9. Explain why friction opposes the motion and how it changes the acceleration.

10. Verify the results using conservation of energy, accounting for the work done by friction.
"""

_ATWOOD = r"""# Physics Test: Two-Mass Pulley System (Atwood Machine)

An ideal pulley system consists of two masses connected by a light, inextensible string passing over a frictionless, massless pulley.

- Mass 1: \(m_1 = 5\,\text{kg}\), hanging on the left
- Mass 2: \(m_2 = 3\,\text{kg}\), hanging on the right
- Gravitational acceleration: \(g = 9.81\,\text{m/s}^2\)
- Both masses start from rest.
- Assume no air resistance, no friction, and an ideal string and pulley.

## Required

1. **Free-body diagrams:** Draw a separate, clearly labeled free-body diagram for each mass.
2. **Forces:** Calculate the weight of each mass.
3. **Acceleration:** Calculate the magnitude and direction of the acceleration of both masses.
4. **Motion after 2 seconds:** Calculate the velocity and displacement of each mass after 2 seconds.
5. **Motion over 3 meters:** Calculate how long it takes Mass 1 to descend 3 meters.
6. **Graphs:** Generate actual, labeled graphs for the first 3 seconds:
   - Displacement versus time for both masses.
   - Velocity versus time for both masses.
   - Acceleration versus time for both masses.
"""

_INCLINE_SCENE = {
    "kind": "scene",
    "scene": "incline",
    "values": {"angle": "30°", "friction": "0.20", "mass": "10 kg", "g": "9.81 m/s²"},
    "components": True,
}
_INCLINE_GRAPHS = {
    "kind": "motion",
    "of": "incline",
    "graphs": ["displacement", "velocity", "acceleration"],
    "time": "5 seconds",
}
_ATWOOD_GRAPHS = {
    "kind": "motion",
    "of": "atwood",
    "graphs": ["displacement", "velocity", "acceleration"],
    "time": "3 seconds",
}


def _drawn(question: str, *blocks: dict[str, Any]) -> list[dict[str, Any]]:
    fences = physics_fences([json.dumps(block) for block in blocks], [question, question])
    return [json.loads(fence.split("\n", 1)[1].rsplit("```", 1)[0]) for fence in fences]


def _last(spec: dict[str, Any]) -> list[float]:
    return spec["points"][-1]


@pytest.mark.parametrize(
    ("text", "statement"),
    [
        ("A box on a ramp.\n1. Draw its forces.\n2. Find its acceleration.", "A box on a ramp."),
        ("A ball is thrown. (a) Find the time. (b) Find the range.", "A ball is thrown."),
        # One numbered line is no parts; a decimal at a line's start is no part's number.
        ("A box on a ramp.\n1. Draw its forces.", None),
        ("A box of mass\n1.5 kg\n2.5 kg away", None),
        ("Find the speed of a 2 kg ball.", None),
    ],
)
def test_statement_before_parts(text: str, statement: str | None) -> None:
    assert statement_before_parts(text) == statement


@pytest.mark.parametrize(
    "question",
    [
        "A block slides down a 30° incline. The coefficient of kinetic friction between the "
        "block and the plane is 0.20. Find the acceleration.",
        "A block slides down a 30° incline, μₖ = 0.20. Find the acceleration.",
        "A block slides down a 30° incline. Coefficient of kinetic friction: μₖ = 0.20. Find "
        "the acceleration.",
    ],
)
def test_a_coefficient_in_textbook_wording_is_read(question: str) -> None:
    intent = extract_physics_intent(question)
    assert intent is not None and intent.physics_op == "incline_acceleration"
    assert (intent.physics_params or {})["mu"] == pytest.approx(0.2)


def test_a_zero_starting_speed_beside_from_rest_is_the_same_fact() -> None:
    """ "released from rest ... u = 0 m/s": no unused speed of the situation."""
    intent = extract_physics_intent(
        "A 10 kg block is released from rest on a plane inclined at 30°. The coefficient of "
        "kinetic friction is 0.20. Initial velocity: u = 0 m/s. Find the acceleration."
    )
    assert intent is not None and intent.physics_op == "incline_acceleration"


def test_a_frictionless_pulley_has_no_friction() -> None:
    intent = extract_physics_intent(
        "Two masses, m1 = 5 kg and m2 = 3 kg, hang over a light frictionless pulley with no "
        "friction anywhere. Both start from rest. Find the acceleration."
    )
    assert intent is not None and intent.physics_op == "atwood"


def test_the_incline_s_free_body_diagram_draws_with_its_weight_s_components() -> None:
    (scene,) = _drawn(_INCLINE, _INCLINE_SCENE)
    assert scene["type"] == "incline"
    assert scene["arrow_labels"] == {
        "gravity": "mg = 98.10 N",
        "normal": "N = 84.96 N",
        "friction": "f = 16.99 N",
    }
    labels = [vector["label"] for vector in scene["vectors"]]
    assert labels == ["mg sin 30° = 49.05 N", "mg cos 30° = 84.96 N"]
    # Down the slope, then into it; drawn in that order, after the forces.
    along, across = scene["vectors"]
    assert along["dx"] > 0 > along["dy"] and across["dx"] < 0 and across["dy"] < 0
    assert (along["stage"], across["stage"]) == (0, 1)


def test_the_forces_block_of_a_long_question_reads_its_setup() -> None:
    forces = {"kind": "forces", "body": "block", "forces": ["weight", "normal", "friction"]}
    (scene,) = _drawn(_INCLINE, {**forces, "components": True})
    assert scene["type"] == "incline"
    assert [v["label"] for v in scene["vectors"]] == ["mg sin 30°", "mg cos 30°"]


def test_the_incline_s_motion_graphs_are_the_server_s() -> None:
    """a = g(sin θ - μ cos θ) = 3.21 m/s², from rest over the 5 s asked."""
    s, v, a = _drawn(_INCLINE, _INCLINE_GRAPHS)
    assert [g["title"] for g in (s, v, a)] == ["s–t", "v–t", "a–t"]
    assert _last(s) == pytest.approx([5.0, 40.0732], abs=1e-3)
    assert _last(v) == pytest.approx([5.0, 16.0293], abs=1e-3)
    assert all(point[1] == pytest.approx(3.205858, abs=1e-6) for point in a["points"])
    assert s["points"][0] == [0.0, 0.0] and s["x_label"] == "t (s)" and s["y_label"] == "s (m)"


def test_the_atwood_machine_s_two_masses_each_get_their_graphs() -> None:
    """a = (m₁ - m₂)g/(m₁ + m₂) = 2.4525 m/s²; upward positive, so the 5 kg mass falls."""
    graphs = _drawn(_ATWOOD, _ATWOOD_GRAPHS)
    assert [g["title"] for g in graphs] == [
        "s–t (5 kg)",
        "s–t (3 kg)",
        "v–t (5 kg)",
        "v–t (3 kg)",
        "a–t (5 kg)",
        "a–t (3 kg)",
    ]
    s1, s2, v1, v2, a1, a2 = (_last(g)[1] for g in graphs)
    assert (s1, s2) == (pytest.approx(-11.03625), pytest.approx(11.03625))
    assert (v1, v2) == (pytest.approx(-7.3575), pytest.approx(7.3575))
    assert (a1, a2) == (pytest.approx(-2.4525), pytest.approx(2.4525))


def test_the_atwood_scene_and_forces_of_a_long_question_draw() -> None:
    scene = {"kind": "scene", "scene": "atwood", "values": {"mass1": "5 kg", "mass2": "3 kg"}}
    (drawn,) = _drawn(_ATWOOD, scene)
    labels = {vector.get("label") for vector in drawn["vectors"]}
    assert {"T = 36.79 N", "m₁g = 49.05 N", "m₂g = 29.43 N"} <= labels
    forces = {"kind": "forces", "body": "mass", "forces": ["weight", "tension"]}
    (rig,) = _drawn(_ATWOOD, forces)
    assert [v["label"] for v in rig["vectors"]] == ["T", "m₁g", "T", "m₂g"]


@pytest.mark.parametrize(
    ("question", "block"),
    [
        # Its friction holds it: tan 15° < 0.5, so it never slides.
        (
            "A 4 kg block is released from rest on a 15° incline. The coefficient of kinetic "
            "friction is 0.5. Plot its velocity against time for 3 s.",
            {"kind": "motion", "of": "incline", "graphs": ["velocity"], "time": "3 s"},
        ),
        # Equal masses: no motion.
        (
            "Two equal 4 kg masses hang over a frictionless pulley, released from rest. Plot "
            "their velocity-time graphs for 2 s.",
            {"kind": "motion", "of": "atwood", "graphs": ["velocity"], "time": "2 s"},
        ),
        # A span the question does not give.
        (_INCLINE, {**_INCLINE_GRAPHS, "time": "7 s"}),
        # Not from rest: a starting speed no graph from rest draws.
        (
            "A 2 kg block slides down a 30° incline at 3 m/s. The coefficient of kinetic "
            "friction is 0.2. Plot its velocity over 4 s.",
            {"kind": "motion", "of": "incline", "graphs": ["velocity"], "time": "4 s"},
        ),
        # Another situation than the scene named.
        (
            _ATWOOD,
            {"kind": "motion", "of": "incline", "graphs": ["velocity"], "time": "3 seconds"},
        ),
    ],
    ids=["held-by-friction", "equal-masses", "unstated-span", "not-from-rest", "other-scene"],
)
def test_a_setup_motion_the_server_cannot_be_sure_of_draws_nothing(
    question: str, block: dict[str, Any]
) -> None:
    assert _drawn(question, block) == []


def test_free_body_diagrams_for_each_mass_of_a_pulley_draw_the_rig() -> None:
    picture = force_picture(
        "Draw free-body diagrams for each mass of an Atwood machine with masses of 5 kg and 3 kg."
    )
    assert picture is not None and len(picture.spec.bodies) == 2
    # Several diagrams of one body (at several moments) are still none this file draws.
    assert (
        force_picture("Draw free-body diagrams of a ball at the start and end of its fall.") is None
    )


def test_a_pulley_with_a_body_on_each_side_is_a_pair() -> None:
    picture = force_picture(
        "I have a pulley with a 3 kg bucket on one side and a 5 kg sandbag on the other, let "
        "go from rest. Show me the forces on each."
    )
    assert picture is not None and len(picture.spec.bodies) == 2
    # "on a pulley" names the pulley, which is no body of this picture.
    assert force_picture("Show the forces on a pulley.") is None


def test_the_atwood_scene_shows_each_mass_s_weight_to_scale() -> None:
    (spec,) = _atwood_scene(5.0, 3.0, 2.4525, 36.7875, 9.81)
    sizes = {vector.label: vector.dy for vector in spec.vectors if vector.label}
    assert sizes["m₁g = 49.05 N"] == pytest.approx(-1.0)
    assert sizes["m₂g = 29.43 N"] == pytest.approx(-0.6)
    assert sizes["T = 36.79 N"] == pytest.approx(36.7875 / 49.05)


def test_the_figure_read_may_name_several_pictures() -> None:
    assert _blocks(None) == [] and _blocks({"kind": "none"}) == []
    assert _blocks({"kind": "forces"}) == [{"kind": "forces"}]
    many: list[dict[str, Any]] = [
        {"kind": "forces"},
        {"kind": "motion"},
        {"kind": None},
        {"kind": "beam"},
        {"kind": "x"},
    ]
    assert [b["kind"] for b in _blocks(many)] == ["forces", "motion", "beam"]
    flagged = normalized({"kind": "incline", "angle": "30°", "components": True})
    assert flagged["components"] is True and "components" not in flagged["values"]

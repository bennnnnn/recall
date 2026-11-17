"""A physics scene a reply describes: each value held to the question's, drawn by the
builder its solver draws with (the owner's round of 30 hard problems, 2026-11-16: 29 had no
picture, as no solver reads a question in parts)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.modules.physics.scene_drawing.build import physics_fences, scene_fences

pytestmark = pytest.mark.usefixtures("thread_sympy_executor")

_CLIFF = (
    "A stone is thrown from the top of a 45 m high cliff with a speed of 20 m/s at 30 "
    "degrees above the horizontal. Find (a) the time of flight, (b) how far from the base "
    "of the cliff it lands, and (c) its speed just before it hits the ground."
)
_INCLINE = (
    "A 5 kg block starts from rest at the top of a 4 m long incline at 35 degrees. The "
    "coefficient of kinetic friction is 0.25. Find (a) its acceleration, (b) its speed at "
    "the bottom, and (c) the time to reach the bottom."
)
_ATWOOD = (
    "Two masses of 3 kg and 5 kg hang on either side of a light frictionless pulley and are "
    "released from rest. Find (a) the acceleration and (b) the tension in the string."
)
_BULLET = (
    "A 10 g bullet moving at 400 m/s embeds itself in a 2 kg wooden block hanging from a "
    "long string. Find (a) the speed of the block and bullet just after the collision."
)
_SPRING = (
    "A 0.5 kg mass on a horizontal frictionless surface is attached to a spring with "
    "k = 200 N/m. Find (a) the period and (b) the maximum speed."
)
_PENDULUM = "A simple pendulum of length 1.5 m is pulled aside and released. Find its period."
_ORBIT = (
    "A satellite moves in a circular orbit 600 km above the Earth's surface. Take the "
    "Earth's mass as 5.97 x 10^24 kg and its radius as 6370 km. Find its orbital speed."
)
_SLAB = (
    "A light ray in air strikes a glass slab of refractive index 1.52 at an angle of "
    "incidence of 40 degrees. Find the angle of refraction."
)
_LENS = (
    "An object 2 cm tall is placed 15 cm in front of a converging lens of focal length "
    "10 cm. Find the image position."
)
_STRING = (
    "A string 1.2 m long is fixed at both ends under a tension of 80 N. Find (a) the "
    "fundamental frequency and (b) the third harmonic."
)
_BANKED = (
    "A curve of radius 80 m is banked at 15 degrees. At what speed can a car take the curve "
    "with no friction needed?"
)


def _scene(**description: Any) -> str:
    return json.dumps({"kind": "scene", **description})


def _types(fences: list[str]) -> list[str]:
    return [json.loads(fence.split("\n", 1)[1].rsplit("\n```", 1)[0])["type"] for fence in fences]


@pytest.mark.parametrize(
    ("question", "description", "drawn"),
    [
        (
            _CLIFF,
            _scene(
                scene="projectile",
                values={"speed": "20 m/s", "angle": "30 degrees", "height": "45 m"},
            ),
            "projectile_motion",
        ),
        (
            _INCLINE,
            _scene(scene="incline", values={"angle": "35°", "friction": "0.25", "mass": "5 kg"}),
            "incline",
        ),
        (_ATWOOD, _scene(scene="atwood", values={"mass1": "3 kg", "mass2": "5 kg"}), "free_body"),
        (
            _BULLET,
            _scene(
                scene="collision",
                sticks=True,
                values={"mass1": "10 g", "speed1": "400 m/s", "mass2": "2 kg"},
            ),
            "collision",
        ),
        (
            _SPRING,
            _scene(scene="spring", values={"spring_constant": "200 N/m", "mass": "0.5 kg"}),
            "spring",
        ),
        (_PENDULUM, _scene(scene="pendulum", values={"length": "1.5 m"}), "pendulum"),
        (
            _ORBIT,
            _scene(
                scene="orbit",
                values={
                    "altitude": "600 km",
                    "planet_mass": "5.97 x 10^24 kg",
                    "planet_radius": "6370 km",
                },
            ),
            "orbit",
        ),
        (
            _SLAB,
            _scene(scene="refraction", values={"angle": "40 degrees", "index": "1.52"}),
            "rays",
        ),
        (
            _LENS,
            _scene(
                scene="lens",
                values={
                    "focal_length": "10 cm",
                    "object_distance": "15 cm",
                    "object_height": "2 cm",
                },
            ),
            "rays",
        ),
        (_STRING, _scene(scene="standing_wave", harmonic=3, values={"length": "1.2 m"}), "wave"),
        (_BANKED, _scene(scene="banked_curve", values={"angle": "15 degrees"}), "incline"),
    ],
)
def test_a_described_scene_is_drawn_by_its_solvers_builder(
    question: str, description: str, drawn: str
) -> None:
    assert _types(scene_fences([description], [question])) == [drawn]


@pytest.mark.parametrize(
    ("question", "description"),
    [
        # A value the question does not state, or not of the part's kind.
        (_ATWOOD, _scene(scene="atwood", values={"mass1": "3 kg", "mass2": "6 kg"})),
        (_ATWOOD, _scene(scene="atwood", values={"mass1": "3 kg", "mass2": "5 m"})),
        # One stated value used twice.
        (_ATWOOD, _scene(scene="atwood", values={"mass1": "3 kg", "mass2": "3 kg"})),
        # A part the scene needs, missing; a part it does not take.
        (_CLIFF, _scene(scene="projectile", values={"speed": "20 m/s"})),
        (
            _CLIFF,
            _scene(scene="projectile", values={"speed": "20 m/s", "angle": "30°", "x": "45 m"}),
        ),
        # A speed written beside the other body's mass.
        (
            _BULLET,
            _scene(
                scene="collision",
                sticks=True,
                values={"mass1": "2 kg", "speed1": "400 m/s", "mass2": "10 g"},
            ),
        ),
        # A collision needs its one claim: stick or bounce elastically, never both or none.
        (
            _BULLET,
            _scene(
                scene="collision", values={"mass1": "10 g", "speed1": "400 m/s", "mass2": "2 kg"}
            ),
        ),
        (_ATWOOD, _scene(scene="atwood", sticks=True, values={"mass1": "3 kg", "mass2": "5 kg"})),
        # A harmonic the question does not name; a scene not in the vocabulary.
        (_STRING, _scene(scene="standing_wave", harmonic=4, values={"length": "1.2 m"})),
        (_CLIFF, _scene(scene="conical_pendulum", values={"angle": "30°"})),
        ("Not physics at all.", "not json"),
        # A stated value of the scene's kinds left out: the question is another situation.
        (
            "A ball is kicked from the ground at 25 m/s at 40 degrees above the horizontal "
            "toward a vertical wall 30 m away. At what height does it hit the wall?",
            _scene(scene="projectile", values={"speed": "25 m/s", "angle": "40 degrees"}),
        ),
        (
            _LENS + " A second converging lens of focal length 20 cm is placed 40 cm behind it.",
            _scene(
                scene="lens",
                values={
                    "focal_length": "10 cm",
                    "object_distance": "15 cm",
                    "object_height": "2 cm",
                },
            ),
        ),
    ],
)
def test_a_scene_that_does_not_check_draws_nothing(question: str, description: str) -> None:
    assert scene_fences([description], [question]) == []


def test_one_setup_gets_one_scene_and_field_blocks_are_the_fields() -> None:
    first = _scene(scene="atwood", values={"mass1": "3 kg", "mass2": "5 kg"})
    second = _scene(scene="atwood", values={"mass1": "5 kg", "mass2": "3 kg"})
    assert len(scene_fences([first, second], [_ATWOOD])) == 1
    field = json.dumps({"kind": "field", "charges": [{"sign": "+"}]})
    assert _types(
        physics_fences(
            [field, first],
            [
                "Draw the field of a positive charge.",
            ],
        )
    ) == ["field"]

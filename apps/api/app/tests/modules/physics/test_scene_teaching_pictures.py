"""The pictures a physics question is taught from, asked for or not: a bar's moments, the
forces on one body and vectors written by their components, each held to the question by the
server (textbook round, 2026-11-25: 66 of 77 questions that needed a picture drew none)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.core.config import Settings
from app.modules.physics.scene_drawing import figure_read
from app.modules.physics.scene_drawing.beam import described_beam
from app.modules.physics.scene_drawing.build import physics_fences
from app.modules.physics.scene_drawing.forces import described_forces
from app.modules.physics.scene_drawing.vectors import described_vectors

_BAR = (
    "A horizontal bar has a 6 N force acting downwards at its left end. Point P is 4 cm to "
    "the right of the left end. A 9 N force acts downwards 12 cm to the right of P, and Q is "
    "8 cm further on, at the right end. Find the moments about P and Q."
)
_BAR_MARKS: list[dict[str, Any]] = [
    {"forces": [{"size": "6 N", "direction": "down"}]},
    {"name": "P", "gap": "4 cm"},
    {"gap": "12 cm", "forces": [{"size": "9 N", "direction": "down"}]},
    {"name": "Q", "gap": "8 cm"},
]
_SEESAW = (
    "A light rod rests on a pivot. A 3 kg mass hangs 1.5 m to the left of the pivot and a "
    "4 kg mass hangs a distance x to the right. Find x."
)
_UPS = (
    "Three forces act on a rod with points A, B and C from left to right; AB = 10 cm and BC "
    "= 20 cm. 40 N acts downwards at A, 70 N acts upwards at B, and 30 N acts downwards at C."
)
_PULLED = (
    "A crate is pulled along a rough level floor by a rope with a force of 12 N. Its mass "
    "is 3 kg. Find the coefficient of friction."
)
_LADDER = (
    "A ladder of mass 15 kg leans against a smooth wall at 70° to the ground. Find the "
    "friction and normal forces that act on the ladder."
)
_FORCES = "Are these forces in equilibrium? P [3 4] N, Q [-1 -2] N and R [-2 -2] N."


def _beam(question: str, marks: list[dict[str, Any]]) -> list[Any]:
    return described_beam(json.dumps({"kind": "beam", "marks": marks}), [question])


def test_a_bar_is_drawn_to_scale_with_each_force_where_the_question_puts_it() -> None:
    (spec,) = _beam(_BAR, _BAR_MARKS)
    assert spec.type == "lever" and spec.beam == pytest.approx([-0.12, 0.0, 0.12, 0.0])
    forces = [v for v in spec.vectors if v.role == "force"]
    assert [(f.anchor[0], f.dy, f.label) for f in forces] == [
        (pytest.approx(-0.12), -6.0, "6 N"),
        (pytest.approx(0.04), -9.0, "9 N"),
    ]
    measures = [(v.dx, v.label) for v in spec.vectors if v.role == "measure"]
    assert measures == [
        (pytest.approx(0.04), "4 cm"),
        (pytest.approx(0.12), "12 cm"),
        (pytest.approx(0.08), "8 cm"),
    ]
    assert [(body.label, body.path[0][0]) for body in spec.bodies] == [
        ("P", pytest.approx(-0.08)),
        ("Q", pytest.approx(0.12)),
    ]


@pytest.mark.parametrize(
    "marks",
    [
        # A force the question does not state, a distance it does not, a direction it
        # does not give the force, and a stated force left off the bar.
        [*_BAR_MARKS[:2], {"gap": "12 cm", "forces": [{"size": "10 N", "direction": "down"}]}],
        [*_BAR_MARKS[:3], {"name": "Q", "gap": "9 cm"}],
        [*_BAR_MARKS[:2], {"gap": "12 cm", "forces": [{"size": "9 N", "direction": "up"}]}],
        # Every distance stated, the 9 N left off (review of #2603: the case before also
        # held an unstated 20 cm, refused before this check ran).
        [_BAR_MARKS[0], _BAR_MARKS[1], {"name": "Q", "gap": "12 cm"}],
        [{"gap": "4 cm", "forces": [{"size": "6 N", "direction": "down"}]}, _BAR_MARKS[1]],
        # Each force and distance stated, each force at the wrong mark, or the gaps swapped.
        [
            {"forces": [{"size": "9 N", "direction": "down"}]},
            _BAR_MARKS[1],
            {"gap": "12 cm", "forces": [{"size": "6 N", "direction": "down"}]},
            _BAR_MARKS[3],
        ],
        [
            _BAR_MARKS[0],
            {"name": "P", "gap": "12 cm"},
            {"gap": "4 cm", "forces": [{"size": "9 N", "direction": "down"}]},
            _BAR_MARKS[3],
        ],
    ],
    ids=[
        "unstated-force",
        "unstated-distance",
        "wrong-way",
        "force-left-out",
        "first-gap",
        "forces-swapped",
        "gaps-swapped",
    ],
)
def test_a_bar_that_does_not_hold_draws_nothing(marks: list[dict[str, Any]]) -> None:
    assert _beam(_BAR, marks) == []


def test_each_force_takes_the_direction_of_its_own_clause() -> None:
    marks: list[dict[str, Any]] = [
        {"name": "A", "forces": [{"size": "40 N", "direction": "down"}]},
        {"name": "B", "gap": "10 cm", "forces": [{"size": "70 N", "direction": "up"}]},
        {"name": "C", "gap": "20 cm", "forces": [{"size": "30 N", "direction": "down"}]},
    ]
    (spec,) = _beam(_UPS, marks)
    assert [v.dy for v in spec.vectors if v.role == "force"] == [-40.0, 70.0, -30.0]
    flipped = [marks[0], {**marks[1], "forces": [{"size": "70 N", "direction": "down"}]}, marks[2]]
    assert _beam(_UPS, flipped) == []


def _seesaw(left: str, right: str) -> list[dict[str, Any]]:
    return [
        {"forces": [{"size": left, "direction": "down"}]},
        {"gap": "1.5 m", "pivot": True},
        {"gap": "x", "forces": [{"size": right, "direction": "down"}]},
    ]


_SEESAWS = [
    _SEESAW,
    "On a see-saw a 4 kg mass sits x to the right of the fulcrum while a 3 kg mass sits "
    "1.5 m to its left. Find x.",
]


@pytest.mark.parametrize("question", _SEESAWS)
def test_a_see_saw_s_masses_are_held_to_their_sides(question: str) -> None:
    """Both masses share one clause: each is the mark its nearest distance is measured to,
    the 3 kg 1.5 m to the left, the 4 kg x to the right; swapped, nothing is drawn (review
    of #2603, round 2)."""
    (spec,) = _beam(question, _seesaw("3 kg", "4 kg"))
    assert [(v.anchor[0] < 0, v.label) for v in spec.vectors if v.role == "force"] == [
        (True, "3 kg"),
        (False, "4 kg"),
    ]
    assert _beam(question, _seesaw("4 kg", "3 kg")) == []


_ENDS = [
    "A rod 30 cm long has a 6 N force acting downwards at its left end and a 9 N force "
    "acting upwards at its right end.",
    "A 9 N force pushes up on the right-hand end of a 30 cm rod, and a 6 N force pulls "
    "down on its left-hand end.",
]


@pytest.mark.parametrize("question", _ENDS)
def test_forces_at_the_ends_are_held_to_the_end_they_act_at(question: str) -> None:
    def marks(left: str, right: str) -> list[dict[str, Any]]:
        down, up = ("down", "up") if left == "6 N" else ("up", "down")
        return [
            {"forces": [{"size": left, "direction": down}]},
            {"gap": "30 cm", "forces": [{"size": right, "direction": up}]},
        ]

    assert len(_beam(question, marks("6 N", "9 N"))) == 1
    assert _beam(question, marks("9 N", "6 N")) == []


def test_hung_masses_pull_down_and_an_asked_distance_is_its_letter() -> None:
    marks: list[dict[str, Any]] = [
        {"forces": [{"size": "3 kg", "direction": "down"}]},
        {"gap": "1.5 m", "pivot": True},
        {"gap": "x", "forces": [{"size": "4 kg", "direction": "down"}]},
    ]
    (spec,) = _beam(_SEESAW, marks)
    assert spec.pivot is not None
    assert [v.label for v in spec.vectors if v.role == "measure"] == ["1.5 m", "x"]
    assert _beam(_SEESAW, [marks[0], marks[1], {**marks[2], "gap": "2 m"}]) == []
    up = {"gap": "x", "forces": [{"size": "4 kg", "direction": "up"}]}
    assert _beam(_SEESAW, [marks[0], marks[1], up]) == []


def _forces(question: str, *forces: str, body: str = "crate") -> list[Any]:
    block = {"kind": "forces", "body": body, "forces": list(forces)}
    return described_forces(json.dumps(block), [question])


def test_the_forces_on_a_body_are_drawn_when_the_server_reads_the_same_ones() -> None:
    (spec,) = _forces(_PULLED, "weight", "normal", "tension", "friction")
    assert spec.type == "free_body"
    assert {v.label for v in spec.vectors} == {"mg", "N", "T", "f"}


def test_a_read_that_names_only_the_forces_along_the_motion_still_agrees() -> None:
    """A lorry's driving force and friction: its weight and the road's push are the server's
    to add, and friction is drawn in one arrow with air resistance."""
    question = (
        "A driving force of 20 kN acts forwards on a lorry and a friction force of 8 kN "
        "acts backwards. What happens to the lorry?"
    )
    (spec,) = _forces(question, "push", "friction", body="lorry")
    assert {v.label for v in spec.vectors} == {"mg", "N", "F", "f"}


@pytest.mark.parametrize(
    ("question", "forces", "body"),
    [
        (_PULLED, ("weight", "normal", "tension"), "crate"),  # friction left out
        (_PULLED, ("weight", "normal", "tension", "friction"), "box"),  # no such body
        (_LADDER, ("weight", "normal", "friction"), "ladder"),  # a body the server lacks
        (
            "Draw free-body diagrams for a ball at the start, the middle and the end of "
            "its fall through air.",
            ("weight",),
            "ball",
        ),
        (
            "A string wound round a cylinder on a rough table comes off its top and is "
            "pulled with 6 N. Find the friction.",
            ("weight", "normal", "tension", "friction"),
            "cylinder",
        ),
    ],
    ids=["other-forces", "other-body", "ladder", "several-diagrams", "rolls"],
)
def test_forces_that_do_not_agree_draw_nothing(
    question: str, forces: tuple[str, ...], body: str
) -> None:
    assert _forces(question, *forces, body=body) == []


@pytest.mark.parametrize(
    ("question", "body", "drawn", "refused"),
    [
        (
            "A block is held at rest on a rough 30° slope by a push of 20 N up the slope. "
            "Find the friction.",
            "block",
            ("weight", "normal", "push"),
            ("weight", "normal", "push", "friction"),
        ),
        (
            "A car goes round a curve on a road banked at 15°. Find its speed.",
            "car",
            ("weight", "normal"),
            ("weight", "normal", "friction"),
        ),
    ],
    ids=["held-by-a-push", "banked-curve"],
)
def test_the_forces_agreed_are_the_arrows_drawn(
    question: str, body: str, drawn: tuple[str, ...], refused: tuple[str, ...]
) -> None:
    """Review of #2603, round 2: the server's forces were read from its prose, whose note
    "(friction acts along the slope ...)" agreed with a read naming friction, and the
    picture was drawn with no friction arrow. The forces are its arrows."""
    assert len(_forces(question, *drawn, body=body)) == 1
    assert _forces(question, *refused, body=body) == []


def test_one_body_slowing_down_is_not_drawn_as_two_bodies() -> None:
    question = "A car travelling at 15 m/s due East brakes and slows to 3 m/s due East."
    arrows = [
        {"size": "15 m/s", "direction": "due East"},
        {"size": "3 m/s", "direction": "due East"},
    ]
    block = {"kind": "vectors", "layout": "bodies", "quantity": "velocity", "arrows": arrows}
    assert described_vectors(json.dumps(block), [question]) == []


def test_a_relative_velocity_gets_no_resultant_of_the_sum() -> None:
    question = (
        "A runs east at 6 km/h while B runs north at 8 km/h. What is the velocity of A "
        "relative to B?"
    )
    arrows = [
        {"name": "A", "size": "6 km/h", "direction": "east"},
        {"name": "B", "size": "8 km/h", "direction": "north"},
    ]
    block = {
        "kind": "vectors",
        "layout": "tail",
        "quantity": "velocity",
        "arrows": arrows,
        "resultant": True,
    }
    (spec,) = described_vectors(json.dumps(block), [question])
    assert len(spec.vectors) == 2 and all(v.role != "result" for v in spec.vectors)


@pytest.mark.parametrize(
    ("question", "names"),
    [
        (
            "Car A travels north at 20 m/s and car B east at 15 m/s. Find the velocity of A "
            "relative to B.",
            ("Car A", "Car B"),
        ),
        (
            "Car A travels north at 20 m/s and car B east at 15 m/s. What is the velocity of "
            "car A with respect to car B?",
            ("Car A", "Car B"),
        ),
        (
            "Car A travels north at 20 m/s and car B east at 15 m/s. Find A's velocity as seen "
            "by B.",
            ("A", "B"),
        ),
        (
            "Car A travels north at 20 m/s and car B east at 15 m/s. Find the relative velocity "
            "of A and B.",
            (None, None),
        ),
    ],
    ids=["label", "with-respect-to", "as-seen-by", "unnamed-arrows"],
)
def test_every_phrasing_of_a_relative_velocity_drops_the_sum(
    question: str, names: tuple[str | None, str | None]
) -> None:
    """Review of #2603, round 2: "velocity of A relative to B" beside arrows named "Car A"
    and "Car B" kept the sum, and "with respect to" was not read."""
    arrows = [
        {"size": "20 m/s", "direction": "north"},
        {"size": "15 m/s", "direction": "east"},
    ]
    for arrow, name in zip(arrows, names, strict=True):
        if name:
            arrow["name"] = name
    block = {
        "kind": "vectors",
        "layout": "tail",
        "quantity": "velocity",
        "arrows": arrows,
        "resultant": True,
    }
    (spec,) = described_vectors(json.dumps(block), [question])
    assert len(spec.vectors) == 2 and all(v.role != "result" for v in spec.vectors)


@pytest.mark.parametrize(
    "question",
    [
        "A boat heads due north at 4 m/s relative to the water; the river flows due east at "
        "3 m/s. Find the resultant velocity.",
        "A plane flies due north at 4 m/s relative to the air in a wind blowing due east at "
        "3 m/s. What is the velocity of the plane relative to the ground?",
    ],
)
def test_a_velocity_relative_to_a_medium_keeps_its_resultant(question: str) -> None:
    """ "relative to the water": the boat's and the current's sum is the answer, relative to
    the ground (review of #2603)."""
    arrows = [
        {
            "name": "boat" if "boat" in question else "plane",
            "size": "4 m/s",
            "direction": "due north",
        },
        {"name": "current", "size": "3 m/s", "direction": "due east"},
    ]
    block = {
        "kind": "vectors",
        "layout": "tail",
        "quantity": "velocity",
        "arrows": arrows,
        "resultant": True,
    }
    (spec,) = described_vectors(json.dumps(block), [question])
    (result,) = [v for v in spec.vectors if v.role == "result"]
    assert (round(result.dx, 6), round(result.dy, 6)) == (3.0, 4.0)


def _components(*arrows: dict[str, str], layout: str = "chain") -> list[Any]:
    block = {
        "kind": "vectors",
        "layout": layout,
        "quantity": "force",
        "arrows": list(arrows),
        "resultant": True,
    }
    return described_vectors(json.dumps(block), [_FORCES])


def test_vectors_written_by_their_components_are_drawn_head_to_tail() -> None:
    (spec,) = _components(
        {"name": "P", "components": "[3 4]"},
        {"name": "Q", "components": "[-1 -2]"},
        {"name": "R", "components": "[-2 -2]"},
    )
    arrows = [(round(v.dx, 6), round(v.dy, 6), v.label) for v in spec.vectors]
    assert arrows[:3] == [(3.0, 4.0, "P = [3, 4] N"), (-1.0, -2.0, "Q = [-1, -2] N"),
                          (-2.0, -2.0, "R = [-2, -2] N")]  # fmt: skip
    # The resultant is worked out here: [0, 0], so the forces are in equilibrium.
    assert len(spec.vectors) == 3 or (spec.vectors[3].dx, spec.vectors[3].dy) == (0.0, 0.0)


@pytest.mark.parametrize(
    "arrows",
    [
        ({"name": "P", "components": "[3 4]"}, {"name": "Q", "components": "[-1 -2]"}),
        (
            {"name": "P", "components": "[3 5]"},
            {"name": "Q", "components": "[-1 -2]"},
            {"name": "R", "components": "[-2 -2]"},
        ),
    ],
    ids=["one-left-out", "not-written"],
)
def test_components_that_do_not_hold_draw_nothing(arrows: tuple[dict[str, str], ...]) -> None:
    assert _components(*arrows) == []


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


@pytest.mark.usefixtures("thread_sympy_executor")
async def test_the_figure_read_s_block_is_drawn_only_when_it_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocks: list[dict[str, Any] | None] = [
        {"kind": "beam", "marks": _BAR_MARKS},
        # Every value stated, the 9 N left off: drawn by nothing.
        {"kind": "beam", "marks": [_BAR_MARKS[0], _BAR_MARKS[1], {"name": "Q", "gap": "12 cm"}]},
        None,
    ]
    modes: list[bool] = []

    async def read(settings: Settings, question: str, earlier: Any, *, asked: bool) -> Any:
        modes.append(asked)
        block = blocks.pop(0)
        return [block] if block is not None else []

    monkeypatch.setattr(figure_read, "read_physics_picture", read)
    fence = await figure_read.draw_physics_figure(_BAR, [], _settings(), asked=False)
    assert fence is not None and fence.startswith("```simulation\n")
    assert await figure_read.draw_physics_figure(_BAR, [], _settings(), asked=False) is None
    assert await figure_read.draw_physics_figure(_BAR, [], _settings(), asked=True) is None
    assert modes == [False, False, True]
    off = _settings(teaching_figures_enabled=False)
    assert await figure_read.draw_physics_figure(_BAR, [], off, asked=False) is None
    assert modes == [False, False, True]


def test_the_read_s_scene_is_put_in_the_reply_s_form_and_still_checked() -> None:
    assert figure_read.normalized({"kind": "banked_curve", "angle": "10°"}) == {
        "kind": "scene",
        "scene": "banked_curve",
        "values": {"angle": "10°"},
    }
    flagged = {
        "kind": "scene",
        "scene": "projectile",
        "values": {"speed": "9 m/s", "horizontal": True},
    }
    assert figure_read.normalized(flagged)["horizontal"] is True
    assert figure_read.normalized({"kind": "beam", "marks": []}) == {"kind": "beam", "marks": []}


@pytest.mark.usefixtures("thread_sympy_executor")
def test_a_value_the_question_asks_to_show_is_no_given_the_scene_must_use() -> None:
    question = (
        "A stone is thrown at 20 m/s at 30° above the horizontal. a) Show that the vertical "
        "component of its velocity is 10 m/s. b) How long is it in the air?"
    )
    block = {"kind": "scene", "scene": "projectile", "values": {"speed": "20 m/s", "angle": "30°"}}
    fences = physics_fences([json.dumps(block)], [question], None)
    assert len(fences) == 1 and "projectile" in fences[0]


async def test_no_figure_read_past_the_spend_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import quota as quota_service

    async def capped(*_: Any) -> bool:
        return True

    async def never(**_: Any) -> Any:
        raise AssertionError("no model call past the cap")

    monkeypatch.setattr(quota_service, "global_spend_exceeded", capped)
    monkeypatch.setattr("app.gateways.structured_completion.complete_structured", never)
    monkeypatch.setattr("app.core.redis.get_redis_client", lambda: None)
    read = await figure_read.read_physics_picture(_settings(), _BAR, [], asked=False)
    assert read == []


def test_a_follow_up_is_held_to_the_whole_problem() -> None:
    """ "What if the mass is 5 kg?" after a box on a 30° ramp states a number of its own, yet
    its picture is still of the box on the ramp (review of #2603, round 2)."""
    problem = "A 2 kg box rests on a 30° ramp. Find the friction."
    follow = "What if the mass is 5 kg?"
    assert figure_read.problem_text(follow, [problem]) == f"{problem}\n{follow}"
    assert figure_read.problem_text("draw it", [_SEESAW]) == f"{_SEESAW}\ndraw it"
    assert figure_read.problem_text(_BAR, []) == _BAR
    (spec,) = _forces(f"{problem}\n{follow}", "weight", "normal", "friction", body="box")
    assert spec.incline_deg == 30.0


def test_the_teaching_read_offers_no_field_and_the_asked_one_does() -> None:
    assert "field lines" not in figure_read._prompt(asked=False)
    assert "field lines" in figure_read._prompt(asked=True)


@pytest.mark.usefixtures("thread_sympy_executor")
def test_every_new_block_draws_through_the_one_build() -> None:
    fences = physics_fences([json.dumps({"kind": "beam", "marks": _BAR_MARKS})], [_BAR], None)
    assert len(fences) == 1 and '"type":"lever"' in fences[0]

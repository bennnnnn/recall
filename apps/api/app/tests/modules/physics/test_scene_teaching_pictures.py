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
        [_BAR_MARKS[0], {"name": "P", "gap": "4 cm"}, {"name": "Q", "gap": "20 cm"}],
        [{"gap": "4 cm", "forces": [{"size": "6 N", "direction": "down"}]}, _BAR_MARKS[1]],
    ],
    ids=["unstated-force", "unstated-distance", "wrong-way", "force-left-out", "first-gap"],
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
    ],
    ids=["other-forces", "other-body", "ladder", "several-diagrams"],
)
def test_forces_that_do_not_agree_draw_nothing(
    question: str, forces: tuple[str, ...], body: str
) -> None:
    assert _forces(question, *forces, body=body) == []


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
        {"kind": "beam", "marks": [_BAR_MARKS[0], {"name": "P", "gap": "5 cm"}]},
        None,
    ]
    modes: list[bool] = []

    async def read(settings: Settings, question: str, earlier: Any, *, asked: bool) -> Any:
        modes.append(asked)
        return blocks.pop(0)

    monkeypatch.setattr(figure_read, "read_physics_picture", read)
    fence = await figure_read.draw_physics_figure(_BAR, [], _settings(), asked=False)
    assert fence is not None and fence.startswith("```simulation\n")
    assert await figure_read.draw_physics_figure(_BAR, [], _settings(), asked=False) is None
    assert await figure_read.draw_physics_figure(_BAR, [], _settings(), asked=True) is None
    assert modes == [False, False, True]
    off = _settings(teaching_figures_enabled=False)
    assert await figure_read.draw_physics_figure(_BAR, [], off, asked=False) is None
    assert modes == [False, False, True]


def test_a_follow_up_with_no_number_is_held_to_the_problem_before_it() -> None:
    assert figure_read.problem_text("draw it", [_SEESAW]) == _SEESAW
    assert figure_read.problem_text(_BAR, [_SEESAW]) == _BAR


def test_the_teaching_read_offers_no_field_and_the_asked_one_does() -> None:
    assert "field lines" not in figure_read._prompt(asked=False)
    assert "field lines" in figure_read._prompt(asked=True)


@pytest.mark.usefixtures("thread_sympy_executor")
def test_every_new_block_draws_through_the_one_build() -> None:
    fences = physics_fences([json.dumps({"kind": "beam", "marks": _BAR_MARKS})], [_BAR], None)
    assert len(fences) == 1 and '"type":"lever"' in fences[0]

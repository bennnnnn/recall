"""Every STEM sweep question is answered right or left to the model, never wrong.

The STEM sweep (``stem_sweep.py``) runs homework questions through the real
chat path and reads the verified answer card. A wrong number, a misread turn, a
reply out of shape or a broken picture fails its own test. Questions the solver
declines, and pictures it does not draw, are coverage: held by floors that only
go up. Raise a floor when a change answers more. A ``gap`` entry is a known
miss: a strict expected failure, so the fix deletes its ``gap`` line.
"""

from __future__ import annotations

import json

import pytest

from app.modules.physics.solvers.motion_scenes import vertical_scene
from app.tests.behavior.stem_sweep import (
    SUBJECT_NAMES,
    Entry,
    answered,
    check_visuals,
    drawn,
    load,
    run,
    run_entry,
)

# subject -> (answered, drawn) on the current corpus
FLOORS = {"physics": (574, 162), "math": (358, 0), "chemistry": (166, 0)}
EXPECTS = {"answer", "explain", "decline", "not_subject"}

ENTRIES = [(subject, entry) for subject in FLOORS for entry in load(subject)]


def _param(subject: str, entry: Entry) -> object:
    marks = [pytest.mark.xfail(reason=entry.gap, strict=True)] if entry.gap else []
    return pytest.param(subject, entry, id=f"{subject}:{entry.id}", marks=marks)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("subject", "entry"), [_param(subject, entry) for subject, entry in ENTRIES]
)
async def test_stem_turn_is_never_wrong(
    subject: str, entry: Entry, thread_sympy_executor: None
) -> None:
    outcome = await run_entry(entry, SUBJECT_NAMES[subject])
    assert not outcome.critical, f"{entry.prompt!r}: " + "; ".join(
        f"{problem.kind}: {problem.text}" for problem in outcome.critical
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("subject", sorted(FLOORS))
async def test_stem_coverage_holds_its_floor(subject: str, thread_sympy_executor: None) -> None:
    outcomes = await run(load(subject), SUBJECT_NAMES[subject])
    floor_answered, floor_drawn = FLOORS[subject]
    assert len(answered(outcomes)) >= floor_answered
    assert len(drawn(outcomes)) >= floor_drawn


@pytest.mark.parametrize("subject", sorted(FLOORS))
def test_stem_corpus_is_well_formed(subject: str) -> None:
    entries = load(subject)
    ids = [entry.id for entry in entries]
    assert len(ids) == len(set(ids)), "entry ids repeat"
    for entry in entries:
        assert entry.expect in EXPECTS, entry.id
        assert entry.prompt.strip(), entry.id
        assert entry.checked == (entry.expect == "answer"), entry.id
        assert entry.shared in {None, *SUBJECT_NAMES} - {subject}, entry.id


@pytest.mark.parametrize(
    ("trajectory_type", "duplicate"),
    [("velocity_vs_time", False), ("position_vs_time", True), ("parametric", True)],
)
def test_only_a_path_graph_beside_a_fall_is_the_same_picture_twice(
    trajectory_type: str, duplicate: bool
) -> None:
    """A v-t line says something the fall does not (its slope is g); a path curve does not."""
    scene = vertical_scene(10.0, 0.0, 9.81, 1.43, ground=True)
    assert scene is not None
    graph = {"type": "trajectory", "trajectory_type": trajectory_type, "points": [[0, 0], [1, 1]]}
    reply = f"```simulation\n{scene.model_dump_json()}\n```\n\n```graph\n{json.dumps(graph)}\n```"
    _kinds, problems = check_visuals(reply)
    assert any(problem.kind == "duplicate_visual" for problem in problems) is duplicate

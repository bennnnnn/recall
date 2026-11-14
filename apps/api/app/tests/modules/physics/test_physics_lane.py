"""Auto's physics lane reads its cues as words, never inside another word (review, 2026-11-12)."""

from __future__ import annotations

import pytest

from app.modules.physics.lane import _looks_like_physics_homework


@pytest.mark.parametrize(
    ("text", "homework"),
    [
        ("A 2 kg box rests on a 30° incline. Find its acceleration.", True),
        ("A block slides down a plane inclined at 25 degrees for 3 s.", True),
        ("Two inclines meet at 40 degrees.", True),
        ("Two pendulums of 1 m swing side by side.", True),
        ("Derive the period of a simple pendulum.", True),
        ("Draw the Atwood's machine with 3 kg and 5 kg.", True),
        # "incline" inside another word is no cue.
        ("I'm disinclined to answer 3 emails today.", False),
        # An everyday word needs a quantity beside it.
        ("The project has momentum.", False),
    ],
)
def test_looks_like_physics_homework_reads_cues_as_words(text: str, homework: bool) -> None:
    assert _looks_like_physics_homework(text) is homework

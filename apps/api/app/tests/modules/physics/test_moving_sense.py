"""A body's direction along a line, read once (``extractors.launch_direction.moving_sense``)."""

from __future__ import annotations

import pytest

from app.modules.physics.extractors.launch_direction import TWO_WAYS, moving_sense


@pytest.mark.parametrize(
    ("words", "sense"),
    [
        ("moving east at 4 m/s", ("east-west", 1)),
        ("moving west at 4 m/s", ("east-west", -1)),
        ("moving left", ("left-right", -1)),
        ("moving in the +x direction at 4.00 m/s", ("x", 1)),
        ("moving in the −x direction at 2.00 m/s", ("x", -1)),
        ("moving in the –x direction", ("x", -1)),
        ("moving in the -x direction", ("x", -1)),
        ("moving in the positive x direction", ("x", 1)),
        ("moving along the negative y-axis", ("y", -1)),
        ("moving at 4 m/s", None),
        ("moving east and then north", TWO_WAYS),
        # A sign inside a value is no direction: "x = 2.5 m".
        ("at x = 2.5 m", None),
    ],
)
def test_a_body_s_sense_on_its_line(words: str, sense: tuple[str, int] | None) -> None:
    assert moving_sense(words, 0, len(words)) == sense

"""A motion graph's title and axes are symbols and units, never English words
(``physics.graph_labels``): the phone draws them as written, under a reply in any language."""

from __future__ import annotations

import re

import pytest

from app.modules.math.schemas import GraphBlockSpec
from app.modules.physics.solvers.motion_scenes import _velocity_time_graph
from app.modules.physics.solvers.oscillations import _oscillation_curve

_WORD = re.compile(r"[A-Za-z]{3,}")


@pytest.mark.parametrize(
    "spec",
    [
        _velocity_time_graph(0.0, 9.81, 2.0, True),
        _velocity_time_graph(5.0, 9.81, 2.0, False),
        _oscillation_curve(2.0, 0.1),
        _oscillation_curve(2.0, None),
    ],
)
def test_a_motion_graph_names_its_axes_in_symbols(spec: GraphBlockSpec) -> None:
    for text in (spec.title, spec.x_label, spec.y_label):
        assert text and not _WORD.search(text), text


def test_a_speed_graph_is_named_apart_from_a_velocity_graph() -> None:
    speed = _velocity_time_graph(0.0, 9.81, 2.0, True)
    velocity = _velocity_time_graph(0.0, 9.81, 2.0, False)
    assert (speed.title, speed.y_label) == ("|v|–t", "|v| (m/s)")
    assert (velocity.title, velocity.y_label) == ("v–t", "v (m/s)")
    assert speed.x_label == velocity.x_label == "t (s)"
    # A screen reader says the quantity by name on the phone, never "vertical bar v".
    assert (speed.quantity, velocity.quantity) == ("speed", "velocity")


def test_an_oscillation_is_spoken_as_a_displacement() -> None:
    assert _oscillation_curve(2.0, 0.1).quantity == "displacement"

"""A circuit or a plane mirror a reply describes is drawn by the server only when the
question states every value and the physics readers read the same setup (Grade 8 round,
2026-11-18: "draw the circuit diagram for this" got a Mermaid flowchart)."""

from __future__ import annotations

import json

import pytest

from app.modules.physics.scene_drawing.apparatus import described_apparatus

_SERIES = (
    "Two resistors of 40Ω each are connected in series across a 120V supply.\n"
    "a) What is the total resistance of the circuit?\n"
    "b) What is the current through the circuit?\n"
    "c) What is the potential difference across each resistor?"
)
_MIRROR = (
    "Construct a ray diagram to find the image of a burning candle in front of a plane mirror."
)


def _circuit(**fields: object) -> str:
    return json.dumps(
        {"kind": "circuit", "arrangement": "series", "supply": "120 V",
         "resistors": ["40 Ω", "40 Ω"], **fields}
    )  # fmt: skip


def test_a_follow_up_draws_the_earlier_circuit_with_the_server_s_current() -> None:
    (spec,) = described_apparatus(_circuit(), ["draw the circuit diagram for this", _SERIES])
    assert spec.type == "circuit" and spec.circuit is not None
    assert spec.circuit.source.label == "120 V"
    assert spec.circuit.current == "I = 1.5 A"
    assert [part.label for part in spec.circuit.load.series or []] == ["R₁ = 40 Ω", "R₂ = 40 Ω"]


@pytest.mark.parametrize(
    "body",
    [
        _circuit(arrangement="parallel"),  # the question wires them in series
        _circuit(resistors=["40 Ω", "40 Ω", "40 Ω"]),  # a resistor the reader does not read
        _circuit(supply="12 V"),  # a value the question does not state
        _circuit(resistors=["40 Ω", "4 Ω"]),
        json.dumps({"kind": "circuit", "arrangement": "series", "resistors": ["40 Ω"]}),
        "not json",
    ],
)
def test_a_circuit_that_does_not_check_draws_nothing(body: str) -> None:
    assert described_apparatus(body, ["draw it", _SERIES]) == []


def test_a_plane_mirror_s_image_is_virtual_and_as_far_behind() -> None:
    (spec,) = described_apparatus(json.dumps({"kind": "plane_mirror"}), [_MIRROR])
    assert spec.type == "rays" and spec.optics is not None
    assert spec.optics.element == "plane_mirror"
    assert spec.optics.object is not None and spec.optics.image is not None
    assert spec.optics.image.virtual and spec.optics.image.x == -spec.optics.object.x
    assert any(ray.virtual for ray in spec.optics.rays)


@pytest.mark.parametrize(
    "body, text",
    [
        (
            {"kind": "plane_mirror"},
            "An object is 20 cm from a concave mirror of focal length 10 cm.",
        ),
        ({"kind": "plane_mirror", "object_distance": "30 cm"}, _MIRROR),
        ({"kind": "plane_mirror"}, "Why do mirrors reverse left and right?"),
    ],
)
def test_a_mirror_that_does_not_check_draws_nothing(body: dict[str, str], text: str) -> None:
    assert described_apparatus(json.dumps(body), [text]) == []


def test_a_stated_distance_labels_both_arrows() -> None:
    text = "A candle stands 30 cm in front of a plane mirror. Draw a ray diagram."
    body = json.dumps({"kind": "plane_mirror", "object_distance": "30 cm"})
    (spec,) = described_apparatus(body, [text])
    assert spec.optics is not None and spec.optics.object is not None
    assert spec.optics.object.label == "dₒ = 30 cm"


_RIDE = (
    "I rode my bicycle to grandmother's house at 6 km/h in a flat road for 5 min before reach "
    "a hill. I went at 2 km/h up the hill for 3minutes. I met a friend and stopped to talk for "
    "5 minutes. Draw (plot) the v against t graph for this motion."
)
_TURN_BACK = (
    "A car traveling due north at 60 km/hr increased its velocity to 80 m/s due south in 20 "
    "seconds.\nDraw\ni) speed against time graph,\nii) acceleration against time graph."
)


def _motion(graphs: list[str], stages: list[dict[str, str]]) -> str:
    return json.dumps({"kind": "motion", "graphs": graphs, "stages": stages})


def test_a_ride_in_stages_is_drawn_in_the_question_s_units() -> None:
    """Grade 8 round, t15: the v-t graph of a ride in stages, its stop included."""
    from app.modules.physics.scene_drawing.motion_graph import described_motion

    stages = [
        {"speed": "6 km/h", "time": "5 min"},
        {"speed": "2 km/h", "time": "3 min"},
        {"speed": "0", "time": "5 min"},
    ]
    velocity, distance = described_motion(_motion(["velocity", "distance"], stages), [_RIDE])
    assert (velocity.x_label, velocity.y_label, velocity.x_max) == (
        "Time (min)",
        "Velocity (km/h)",
        13.0,
    )
    assert velocity.points[0] == [0.0, 6.0] and velocity.points[-1] == [13.0, 0.0]
    assert distance.points[-1] == [13.0, 600.0]  # 500 m, then 100 m, then none


def test_a_turn_back_is_drawn_through_zero_with_its_one_acceleration() -> None:
    """t16: speed falls to 0 where the car turns and rises to 80 m/s; the acceleration is one
    value, the server's: (-80 - 16.67) / 20."""
    from app.modules.physics.scene_drawing.motion_graph import described_motion

    stages = [{"from": "60 km/h", "to": "-80 m/s", "time": "20 s"}]
    speed, acceleration = described_motion(_motion(["speed", "acceleration"], stages), [_TURN_BACK])
    assert speed.y_label == "Speed (m/s)" and min(p[1] for p in speed.points) == 0.0
    assert speed.points[-1] == [20.0, 80.0]
    assert {round(p[1], 3) for p in acceleration.points} == {-4.833}


@pytest.mark.parametrize(
    "stages, text",
    [
        ([{"speed": "7 km/h", "time": "5 min"}], _RIDE),  # a speed the question never states
        ([{"speed": "6 km/h"}], _RIDE),  # a stage with no time
        ([{"speed": "0", "time": "5 min"}], "A car drives at 6 km/h for 5 min."),  # no rest
        ([{"from": "6 km/h", "to": "-2 km/h", "time": "5 min"}], _RIDE),  # no other way
    ],
)
def test_a_motion_that_does_not_check_draws_nothing(
    stages: list[dict[str, str]], text: str
) -> None:
    from app.modules.physics.scene_drawing.motion_graph import described_motion

    assert described_motion(_motion(["speed"], stages), [text]) == []


def test_a_stage_takes_the_question_s_values_in_order() -> None:
    """A last stretch the question gives no time for borrows none: "5 min" was the flat
    road's (r01 drew "the default 5 minutes"); stages out of order draw nothing."""
    from app.modules.physics.scene_drawing.motion_graph import described_motion

    ride = f"{_RIDE} I went on at 2 km/h to my grandmother's house."
    stages = [
        {"speed": "6 km/h", "time": "5 min"},
        {"speed": "2 km/h", "time": "3 min"},
        {"speed": "0", "time": "5 min"},
        {"speed": "2 km/h", "time": "5 min"},
    ]
    (graph,) = described_motion(_motion(["speed"], stages), [ride])
    assert graph.x_max == 13.0  # the stretch with no time is left out
    swapped = [stages[1], stages[0], *stages[2:]]
    assert described_motion(_motion(["speed"], swapped), [ride]) == []

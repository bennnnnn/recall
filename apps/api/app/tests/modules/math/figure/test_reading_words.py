"""A reading that names a value by a word or writes it with its unit keeps the value: the
word says what the value is of, the number is the value. Both used to lose the measure,
and the picture one of the question's values."""

from __future__ import annotations

from app.modules.math.figure.request import FigureRequest, Measure

from .figure_support import figure, labels


def test_reading_a_word_name_says_what_the_value_is_of() -> None:
    measure = Measure.model_validate({"what": "height", "name": "lighthouse", "value": 60})
    assert (measure.name, measure.of, measure.value) == ("", "lighthouse", 60)


def test_reading_point_letters_stay_a_name() -> None:
    measure = Measure.model_validate({"what": "side", "name": "AB", "value": 5})
    assert (measure.name, measure.of) == ("AB", "")


def test_reading_a_value_with_its_unit_is_its_number() -> None:
    request = FigureRequest.model_validate(
        {"kind": "polygon", "measures": [{"what": "distance", "value": "50 m"}]}
    )
    assert request.measures[0].value == 50


def test_reading_a_lighthouse_by_name_draws_its_height() -> None:
    question = "A lighthouse is 60 m tall. From its top, the angle of depression of a ship is 18°."
    reading = {
        "kind": "polygon",
        "shape": "depression",
        "measures": [
            {"what": "height", "name": "lighthouse", "value": 60},
            {"what": "angle", "name": "ship", "value": 18},
        ],
        "unit": "m",
    }
    assert labels(figure(question, reading)) == ["18°", "60 m"]


def test_reading_shadows_are_drawn_whatever_shape_the_reading_names() -> None:
    question = "A building casts a 36 m shadow when a 1.8 m man casts a 2.4 m shadow."
    reading = {
        "kind": "polygon",
        "shape": "elevation",
        "attached": "shadows",
        "measures": [
            {"what": "shadow", "name": "building", "value": 36},
            {"what": "height", "name": "man", "value": 1.8},
            {"what": "shadow", "name": "man", "value": 2.4},
        ],
        "unit": "m",
    }
    assert labels(figure(question, reading)) == ["1.8 m", "2.4 m", "36 m"]


def test_reading_an_exterior_angle_read_twice_is_drawn_once() -> None:
    question = "In triangle ABC, BC is produced to D. Angle ACD = 115° and angle BAC = 45°."
    reading = {
        "kind": "polygon",
        "shape": "triangle",
        "vertices": "ABC",
        "measures": [
            {"what": "angle", "name": "ACD", "value": 115},
            {"what": "angle", "name": "BAC", "value": 45},
            {"what": "exterior_angle", "name": "ACD", "value": 115},
        ],
    }
    assert labels(figure(question, reading)) == ["115°", "45°"]

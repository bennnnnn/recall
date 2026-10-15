"""The follow-up shapes physics and chemistry share read only what they can name."""

import pytest

from app.services.problem_followup import asked_unit, new_value, scaled_given, scaled_value


@pytest.mark.parametrize(
    ("line", "unit"),
    [
        ("in km/h", "km/h"),
        ("in km/h please", "km/h"),
        ("what is that in mph", "mph"),
        ("convert it to feet", "feet"),
        ("give the answer in kN", "kN"),
        ("why", None),
        ("in 10 s", None),
    ],
)
def test_asked_unit_reads_the_unit_alone(line: str, unit: str | None) -> None:
    assert asked_unit(line) == unit


@pytest.mark.parametrize(
    ("line", "found"),
    [
        ("what if the mass doubles", ("mass", 2.0)),
        ("what if the height is halved", ("height", 0.5)),
        ("and if the speed triples", ("speed", 3.0)),
        ("what if the mass was 4 kg", None),
        ("double it", None),
    ],
)
def test_scaled_given_reads_the_named_quantity_and_factor(
    line: str, found: tuple[str, float] | None
) -> None:
    assert scaled_given(line) == found


@pytest.mark.parametrize(
    ("line", "found"),
    [
        ("and after 10 s", ("10", "s")),
        ("what if it's dropped from 80 m", ("80", "m")),
        ("and 0.001 M", ("0.001", "M")),
        # A clock time is not a quantity.
        ("and at 5 pm", None),
        ("what about tomorrow at 9 am", None),
        # Two values, or no unit, is not one replaced given.
        ("what if it was 5 apples and 3 pears", None),
        ("and 10", None),
    ],
)
def test_new_value_reads_one_value_with_its_unit(line: str, found: tuple[str, str] | None) -> None:
    assert new_value(line) == found


@pytest.mark.parametrize(
    ("value", "factor", "written"), [(2.0, 2.0, "4"), (20.0, 0.5, "10"), (0.01, 2.0, "0.02")]
)
def test_scaled_value_writes_the_number_a_student_would(
    value: float, factor: float, written: str
) -> None:
    assert scaled_value(value, factor) == written

"""Unit tails are checked once per number, without regex search retries."""

from unittest.mock import patch

import pytest

from app.services.math_text_match.units import unit_after_quantity
from app.services.math_tools.school import _extract_average_speed_intent


@pytest.mark.parametrize("digits", [100, 10000])
def test_failed_unit_tail_is_attempted_once_for_a_whole_digit_run(digits: int) -> None:
    # Two numeric tokens reach unit parsing. The first has no unit, so its
    # complete digit run must produce exactly one check, independent of size.
    prompt = "average speed " + "9" * digits + " ??? 2 s"
    with patch(
        "app.services.math_text_match.units.unit_after_quantity", wraps=unit_after_quantity
    ) as read_unit:
        assert _extract_average_speed_intent(prompt) is None
    assert read_unit.call_count == 1
    assert read_unit.call_args.args[1] == len("average speed ") + digits


def test_two_measurements_have_exactly_two_unit_checks() -> None:
    with patch(
        "app.services.math_text_match.units.unit_after_quantity", wraps=unit_after_quantity
    ) as read_unit:
        intent = _extract_average_speed_intent("average speed .5 km in 2 hours")
    assert intent is not None
    assert (intent.unit_from, intent.unit_to) == ("km", "h")
    assert read_unit.call_count == 2


@pytest.mark.parametrize("tail", [" m/s", " m^2", " m2", " cm/s", " bananas"])
def test_compound_or_unsupported_units_are_still_rejected(tail: str) -> None:
    assert _extract_average_speed_intent(f"average speed 100{tail} in 20 s") is None

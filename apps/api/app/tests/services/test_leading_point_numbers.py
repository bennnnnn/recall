"""A number written with a leading point (".5") is one half in every reader of a reply's or a
message's numbers, never a 5 (``services.number_text.DECIMAL``)."""

from __future__ import annotations

from collections import Counter

from app.services.part.place import _picture_numbers
from app.services.problem_followup import stated_numbers


def test_stated_numbers_read_a_leading_point_as_a_fraction() -> None:
    assert stated_numbers("A wheel of radius .5 m turns 3 times.") == Counter({"0.5": 1, "3": 1})
    # Written either way, it is one number.
    assert stated_numbers("r = 0.5") == stated_numbers("r = .5")


def test_a_pictures_numbers_read_a_leading_point_as_a_fraction() -> None:
    assert _picture_numbers({"label": "r = .5 m"}, written=True) == [0.5]
    assert _picture_numbers({"label": "v = -.25"}, written=True) == [-0.25]

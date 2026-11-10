"""A request to see something (``turn_reading.see_request``): only its words are read."""

from __future__ import annotations

import pytest

from app.modules.turn_reading.see_request import (
    asks_for_a_drawing,
    asks_to_see,
    see_request_object,
)


@pytest.mark.parametrize(
    ("line", "named"),
    [
        ("Draw it", "it"),
        ("please graph this", "this"),
        ("can you plot that please?", "that"),
        ("Plot", ""),
        ("graph the curve", "the curve"),
        ("draw me a cat", "me a cat"),
        ("show me", None),
        ("what is a graph", None),
    ],
)
def test_a_request_to_see_names_what_it_draws(line: str, named: str | None) -> None:
    assert see_request_object(line) == named


@pytest.mark.parametrize(
    ("line", "asks"),
    [
        ("Draw it", True),
        ("Plot", True),
        ("show it", True),
        ("show me that", True),
        ("can I see it?", True),
        ("a picture of it", True),
        ("Show me a photo of it please", True),
        ("draw a picture of it", True),
        # A subject of its own, the working, or an offer accepted: no request to see "it".
        ("show me", False),
        ("show me how", False),
        ("show me the steps", False),
        ("show me a picture of the Eiffel Tower", False),
        ("show it at night", False),
        ("show that sin(x)^2 + cos(x)^2 = 1", False),
        ("a picture of a cat", False),
        ("show me her image", False),
        ("give me that", False),
        ("send me that", False),
        # Another script: the words read here are English.
        ("画出来", False),
        ("нарисуй это", False),
    ],
)
def test_a_request_to_see_it_names_nothing_of_its_own(line: str, asks: bool) -> None:
    assert asks_to_see(line) is asks


@pytest.mark.parametrize(
    "line, drawing",
    [
        ("Draw it", True),
        ("graph this please", True),
        ("can you sketch that", True),
        ("a picture of it", True),
        ("Show me that", False),
        ("show it", False),
        ("can I see it?", False),
    ],
)
def test_a_drawing_is_asked_for_in_drawing_words(line: str, drawing: bool) -> None:
    """ "Show me that" after a solve asks for the working; only drawing words ask for the
    figure alone (review, 2026-11-10)."""
    assert asks_for_a_drawing(line) is drawing

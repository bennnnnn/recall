"""The conversation's latest subject (``turn_reading.latest_subject``).

Live (2026-11-09): a triangle typed in pieces ("Triangle are with sides 5, 4,", "3", "The
area", "Do it properly"), then "Draw it" drew sin(x²)cos(x²) from six messages back. A walk
back passes over lines that lean on the one before and stops at the newest line with a
subject of its own; nothing older is reached.
"""

from __future__ import annotations

import pytest

from app.modules.turn_reading.latest_subject import (
    LatestSubject,
    adds_to_subject,
    asks_to_see,
    continued_subject,
    latest_subject,
    leans_on_earlier,
    see_request_object,
)

_OWNERS_CHAT = [
    "Differentiate sin(x^2)cos(x^2)",
    "What if $x^2 = x^3$?",
    "What if $x^2 = 2x$?",
    "How does this relate to sin(2x)?",
    "Triangle are with sides 5, 4,",
    "3",
    "The area",
    "Do it properly",
]


@pytest.mark.parametrize(
    "line",
    [
        "3",
        "x",
        "for x",
        "$\\theta$",
        "The area",
        "and its perimeter?",
        "what's the third side?",
        "find the hypotenuse",
        "Do it properly",
        "Draw it",
        "can you plot this for me?",
        "now factor it",
        "show me the steps",
        "why?",
        "explain",
        "Is that true?",
        "thanks",
        "ok cool",
    ],
)
def test_a_line_that_names_nothing_of_its_own_leans_on_the_one_before(line: str) -> None:
    assert leans_on_earlier(line)


@pytest.mark.parametrize(
    "line",
    [
        "Triangle are with sides 5, 4,",
        "What's the capital of France?",
        "How does this relate to sin(2x)?",
        "What if $x^2 = 2x$?",
        "what about dinner?",
        "is that fast for a car?",
        "translate it to french",
        "the eiffel tower",
        "I asked for the triangle",
        "Paris",
    ],
)
def test_a_line_with_a_subject_of_its_own_ends_the_walk(line: str) -> None:
    assert not leans_on_earlier(line)


def test_the_owners_chat_is_on_the_triangle_with_its_third_side_and_its_question() -> None:
    subject = latest_subject(_OWNERS_CHAT)

    assert subject == LatestSubject("Triangle are with sides 5, 4, 3", "The area")
    assert subject.problem == "Triangle are with sides 5, 4, 3. The area"


def test_a_subject_in_between_ends_the_walk_before_an_older_one() -> None:
    lines = ["y = 2x + 3", "What's the capital of France?", "thanks"]

    assert latest_subject(lines) == LatestSubject("What's the capital of France?")


@pytest.mark.parametrize(
    ("lines", "setup"),
    [
        # Only a list left open takes the number: "= 5" then "x" names the unknown.
        (["3x^2 + 3 = 5", "x"], "3x^2 + 3 = 5"),
        (["rectangle 3 by", "5"], "rectangle 3 by 5"),
        (["sides 5, 4 and", "3"], "sides 5, 4 and 3"),
    ],
)
def test_a_number_joins_only_a_list_left_open(lines: list[str], setup: str) -> None:
    subject = latest_subject(lines)

    assert subject is not None and subject.setup == setup


def test_the_newest_quantity_asked_is_the_question() -> None:
    subject = latest_subject(["Triangle with sides 5, 4, 3", "the area", "and the perimeter?"])

    assert subject is not None
    assert subject.problem == "Triangle with sides 5, 4, 3. and the perimeter?"


@pytest.mark.parametrize(
    ("line", "earlier", "problem"),
    [
        ("3", ["Triangle are with sides 5, 4,"], "Triangle are with sides 5, 4, 3"),
        (
            "The area",
            ["Triangle are with sides 5, 4,", "3"],
            "Triangle are with sides 5, 4, 3. The area",
        ),
        # Adds nothing, or is a subject of its own.
        ("draw it", ["Triangle with sides 5, 4, 3"], None),
        ("thanks", ["Triangle with sides 5, 4, 3"], None),
        ("y = x^2", ["Triangle with sides 5, 4, 3"], None),
        ("the area", [], None),
    ],
)
def test_a_line_that_adds_to_the_subject_continues_it(
    line: str, earlier: list[str], problem: str | None
) -> None:
    assert continued_subject(line, earlier) == problem


@pytest.mark.parametrize(
    ("line", "adds"),
    [
        ("3", True),
        ("$5$", True),
        ("The area", True),
        ("and its perimeter?", True),
        ("draw it", False),
        ("Do it properly", False),
        ("x", False),
        ("thanks", False),
    ],
)
def test_a_number_or_a_quantity_adds_to_the_subject(line: str, adds: bool) -> None:
    assert adds_to_subject(line) is adds


def test_a_chat_of_only_leaning_lines_has_no_subject() -> None:
    assert latest_subject(["thanks", "draw it"]) is None
    assert latest_subject([]) is None


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
    assert asks_to_see(line) is (named in {"", "it", "this", "that"})

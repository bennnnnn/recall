"""A line a subject solves is that subject's problem before it is a question about the user's
place: "A ball is dropped from a height of 20 m. How long does it take to reach the ground?"
was answered "I don't have your location yet" (2026-11-01). The turn's reading, read in the
pool, says which subject reads a request out of the message; every reader of the user's place
defers to it (``web_search.weather.is_worked_problem``).
"""

from __future__ import annotations

import contextvars

import pytest

from app.core.config import Settings
from app.core.readings import begin_turn
from app.modules.chat.turn_prep.reading import ask_turn_readings, read_turn
from app.modules.turn_reading.turn import TurnReading, reads_a_problem
from app.modules.web_search.geo_intent import (
    is_distance_query,
    is_geo_query,
    is_places_list_query,
)
from app.services.text_normalize import collapse_ws

_SETTINGS = Settings.model_validate({})


def _read_as_turn(text: str) -> TurnReading:
    """``text`` read as the turn's message, as the pool reads it."""
    begin_turn()
    ask_turn_readings(
        text,
        prior_user=None,
        prior_model=None,
        lesson_active=False,
        has_image_attachment=False,
        settings=_SETTINGS,
    )
    return read_turn(text, _SETTINGS, has_image_attachment=False)


def _in_turn(text: str) -> tuple[TurnReading, bool, bool, bool]:
    def run() -> tuple[TurnReading, bool, bool, bool]:
        reading = _read_as_turn(text)
        return (
            reading,
            is_geo_query(text),
            is_geo_query(collapse_ws(text)),
            is_distance_query(text),
        )

    return contextvars.copy_context().run(run)


@pytest.mark.parametrize(
    "text",
    [
        "A ball is dropped from a height of 20 m. How long does it take to reach the ground?",
        "A stone falls from the top of a cliff 45 m high. How long does it take to reach the bottom?",
        "A coin is dropped from a height of 1.8 m. How long does it take to reach the floor?",
        "A rock is dropped from a bridge 30 m above the river. How long does it take to reach "
        "the water?",
        "If a ball is dropped from 10 m, how long does it take to get to the ground?",
        "A stone is dropped down a well and hits the water after 2 s. How far down is the water?",
    ],
)
def test_a_problem_its_subject_reads_asks_nothing_about_the_users_place(text: str) -> None:
    # Without the turn's reading the place readers claim it, as they did.
    assert is_geo_query(text)

    reading, geo, geo_collapsed, distance = _in_turn(text)

    assert reading.problem == "physics"
    assert not geo and not geo_collapsed and not distance


@pytest.mark.parametrize(
    "text",
    [
        "How long does it take to reach the airport?",
        "how long to get to the beach?",
        "How far is the nearest hospital?",
        "How long does it take to reach the top of the nearest mountain?",
        # Physics claims the line ("30 mpg") and reads no problem in it.
        "How far is the nearest gas station? My car does 30 mpg",
        "What's the weather like here today?",
        "coffee shops near me",
    ],
)
def test_a_real_location_ask_still_asks_for_the_place(text: str) -> None:
    reading, geo, geo_collapsed, _ = _in_turn(text)

    assert reading.problem is None
    assert geo and geo_collapsed


def test_a_search_around_the_user_outweighs_a_problem() -> None:
    text = "Find coffee shops near me within 2 km, max 5 km"

    def run() -> tuple[bool, bool]:
        _read_as_turn(text)
        return is_geo_query(text), is_places_list_query(text)

    assert contextvars.copy_context().run(run) == (True, True)


def test_only_the_turns_own_message_is_known() -> None:
    problem = "A ball is dropped from a height of 20 m. How long does it take to reach the ground?"

    def run() -> tuple[bool, bool, bool]:
        _read_as_turn(problem)
        return (
            reads_a_problem(problem),
            reads_a_problem(f"  {problem}\n"),
            reads_a_problem("How long does it take to reach the airport?"),
        )

    assert contextvars.copy_context().run(run) == (True, True, False)
    # Outside a turn nothing is read.
    assert contextvars.Context().run(reads_a_problem, problem) is False

"""The chain reaches a launch at an angle and a lens image's size from catalog data.

Live (2026-11-04): "i kick a ball at 20 m/s at 30 degrees, how far does it land and
whats the max height" got the height alone, and "an object is 30 cm from a convex lens
with focal length 10 cm. where is the image and how big is it" the distance alone. The
projectile laws now bind from level ground at a stated angle, and the lens laws share
their distances, so the image distance one law works out is the one magnification reads.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics.binding import bind_physics_intent
from app.modules.physics.prompt import solve_physics_request

_SETTINGS = Settings()


def _answers(question: str) -> list[str] | None:
    outcome, block = solve_physics_request(question, _SETTINGS, None)
    if outcome != "verified" or block is None:
        return None
    if block.physics_parts:
        return [part.answer for part in block.physics_parts]
    return [block.canonical_answer] if block.canonical_answer else None


@pytest.mark.parametrize(
    ("question", "answers"),
    [
        (
            "i kick a ball at 20 m/s at 30 degrees, how far does it land and whats the max height",
            ["35.3 m", "5.1 m"],
        ),
        (
            "A stone is thrown at 12 m/s at 60 degrees. How long is it in the air and how far "
            "does it go?",
            ["2.12 s", "12.7 m"],
        ),
        (
            "an object is 30 cm from a convex lens with focal length 10 cm. where is the image "
            "and how big is it",
            ["15 cm", "-0.5"],
        ),
        (
            "An object is 30 cm from a concave mirror with focal length 10 cm. Find the image "
            "distance and the magnification.",
            ["15 cm", "-0.5"],
        ),
    ],
)
def test_two_asks_are_both_answered_by_catalog_laws(question: str, answers: list[str]) -> None:
    assert _answers(question) == answers


@pytest.mark.parametrize(
    "question",
    [
        # A virtual image's distance carries no certified sign: never chained into m.
        "an object is 5 cm from a convex lens with focal length 10 cm. where is the image "
        "and how big is it",
        # The 30 m is a wall's distance, not a launch height (it was answered 35.1 m).
        "A ball is kicked at 20 m/s at 30 degrees toward a wall 30 m away. How high is it when "
        "it reaches the wall?",
        # An angle on a slope is no launch (it was answered with a range, 2.21 m).
        "A block slides up a frictionless 30 degree incline at 5 m/s. How far up the incline "
        "does it go before stopping?",
    ],
)
def test_a_situation_the_laws_do_not_cover_gets_no_verified_number(question: str) -> None:
    assert _answers(question) is None


@pytest.mark.parametrize(
    "question",
    [
        "A ball is kicked at 20 m/s at 30 degrees. How long does it take to reach the top?",
        "A projectile is launched at 20 m/s at 30 degrees. Find the time to reach maximum height.",
    ],
)
def test_the_time_to_the_top_is_not_the_whole_flight(question: str) -> None:
    # "how long" alone names the flight (2.04 s); the top is half of it.
    assert _answers(question) == ["1.02 s"]
    assert _answers(
        "I kick a ball at 20 m/s at 30 degrees, how far does it land and how long does it take "
        "to reach the top"
    ) == ["35.3 m", "1.02 s"]


def test_the_speed_at_the_top_is_not_the_impact_speed() -> None:
    # From level ground no law gives the speed at the top; it was answered 20 m/s.
    assert (
        _answers("A ball is kicked at 20 m/s at 30 degrees. How fast is it moving at the top?")
        is None
    )


def test_a_length_is_a_launch_height_only_when_the_words_say_so() -> None:
    from_a_cliff = bind_physics_intent(
        "A ball is kicked at 15 m/s at 40 degrees from the top of a 10 m high cliff. How far "
        "from the base of the cliff does it land?"
    )
    assert from_a_cliff is not None and from_a_cliff.physics_params is not None
    assert from_a_cliff.physics_params["h0"] == 10.0
    # "drops a package from 200 m": a horizontal launch's height, named by "from".
    assert _answers(
        "A plane flying horizontally at 70 m/s drops a package from 200 m. How far ahead does "
        "the package land?"
    ) == ["447 m"]


def test_a_level_launch_with_no_height_is_not_answered_from_the_ground() -> None:
    # Rolled off horizontally with no height: from level ground it would fly for no time.
    assert _answers("a ball rolls off a table horizontally at 2 m/s. how far does it land") is None


def test_an_image_size_is_a_height_when_one_is_stated() -> None:
    assert _answers(
        "A 4 cm tall object is 30 cm from a convex lens with focal length 10 cm. How big is "
        "the image?"
    ) == ["2 cm (inverted)"]

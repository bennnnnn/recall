"""One quantity asked at several places: each place by its own law, or no check at all
(the owner's chat, 2026-11-20: the tension at the bottom, top and halfway got the bottom's
104 N alone, verified)."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.modules.physics.parts import asks_count
from app.modules.physics.place_parts import asked_places, solve_at_places
from app.modules.physics.prompt import solve_physics_request

_OWNER = (
    "An object is moving in a vertical circle attached to a piece of rope anchored in the "
    "centre of the circle. The circle has a radius of 1 m and the object is moving at a steady "
    "speed of 5 m/s. The mass of the object is 3 kg. Work out the tension in the rope at the "
    "bottom, top and halfway between the bottom and top of the circle."
)
_CIRCLE = "A 3 kg object moves in a vertical circle of radius 1 m at {v} m/s. "


@pytest.mark.parametrize(
    ("text", "places"),
    [
        (_OWNER, 3),
        (_CIRCLE.format(v=5) + "Find the tension at the bottom and at the top.", 2),
        (_CIRCLE.format(v=5) + "What is the tension at the highest point and the lowest point?", 2),
        (_CIRCLE.format(v=5) + "Find the tension at the top.", 0),
        # Two quantities, not two places: "the speed at the top" is an ask (``parts``).
        (_CIRCLE.format(v=5) + "What is the tension in the string and the speed at the top?", 0),
        (
            "A tank is 2 m deep. Find the pressure at the bottom of the tank and the force on the base.",
            0,
        ),
        # A comma before a clause, no list: "at the bottom, where …".
        (_CIRCLE.format(v=5) + "Find the tension at the bottom, where the rope is longest.", 0),
        # A list of times or units is no list of a law's places.
        ("A car accelerates at 2 m/s^2 from rest. How far does it go in 3 s and in 5 s?", 0),
        (_CIRCLE.format(v=5) + "Calculate the tension at the top & bottom.", 2),
        (_CIRCLE.format(v=5) + "Find the tension at the top/bottom.", 2),
        # Conditions another law is cued by are no places (review: "frictionless").
        (
            "Find the momentum of a 3 kg ball moving at 4 m/s on a frictionless surface and "
            "in a straight line.",
            0,
        ),
        ("Find the tension " + "in " * 3000 + "the rope.", 0),
    ],
)
def test_asked_places(text: str, places: int) -> None:
    assert asked_places(text) == places


def test_every_place_is_answered_by_its_own_law() -> None:
    block = solve_at_places(_OWNER, get_settings())
    assert block is not None
    assert [part.op for part in block.physics_parts] == [
        "vertical_circle_tension_bottom",
        "vertical_circle_tension_top",
        "vertical_circle_tension_side",
    ]
    assert [part.title for part in block.physics_parts] == [
        "Tension at the bottom",
        "Tension at the top",
        "Tension halfway between the bottom and top of the circle",
    ]
    outcome, verified = solve_physics_request(_OWNER, get_settings(), True)
    assert outcome == "verified" and verified is not None and not verified.partial
    assert len(verified.physics_parts) == 3


@pytest.mark.parametrize(
    "text",
    [
        # Below √(rg) the rope is slack at the top: no tension there is any answer.
        _CIRCLE.format(v=2) + "Find the tension at the bottom and at the top.",
        # A place no law is written for.
        _CIRCLE.format(v=5) + "Find the tension at the bottom and at 30 degrees past the bottom.",
        # The speed is the bottom's: the top's tension is no m(v^2/r - g) with it (review).
        "A 0.5 kg ball on a 1 m string is whirled in a vertical circle. It passes the bottom "
        "with a speed of 8 m/s. Find the tension at the bottom and at the top.",
    ],
)
def test_a_place_no_law_answers_leaves_no_check(text: str) -> None:
    assert solve_at_places(text, get_settings()) is None
    assert asks_count(text) == 2
    outcome, verified = solve_physics_request(text, get_settings(), True)
    assert outcome != "verified" or (verified is not None and verified.partial)


@pytest.mark.parametrize(
    "text",
    [
        "A 0.5 kg ball on a 1 m string is whirled in a vertical circle. It is projected from "
        "the bottom with speed 8 m/s. Find the tension at the top.",
        "A 0.5 kg ball on a 1 m string is whirled in a vertical circle. It goes over the top "
        "with a speed of 4 m/s. Find the tension at the bottom.",
        "A 0.5 kg ball on a 1 m string is whirled in a vertical circle. It passes the bottom "
        "at 8 m/s. Find the tension when the string is horizontal.",
    ],
)
def test_a_speed_stated_at_another_place_verifies_nothing(text: str) -> None:
    """Review of the place fix (2026-11-20): the top's 27.1 N for 7.5 N was verified."""
    outcome, verified = solve_physics_request(text, get_settings(), True)
    assert outcome != "verified" or verified is None or verified.partial


def test_a_steady_speed_holds_at_every_place() -> None:
    text = (
        "A 0.5 kg ball on a 1 m string moves in a vertical circle at a constant speed of 8 m/s. "
        "Find the tension at the bottom and at the top."
    )
    block = solve_at_places(text, get_settings())
    assert block is not None and len(block.physics_parts) == 2

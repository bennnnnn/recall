"""One reader of how a body's speed behaves, for every law that depends on it (2026-11-07).

Three readers each kept their own words for "it stops", and a stop said a fourth way was
answered d = vt and verified. ``read_motion`` is the one reader; these hold its words and
its look-alikes.
"""

from __future__ import annotations

import pytest

from app.modules.physics.motion import constant_speed_laws_hold, read_motion


@pytest.mark.parametrize(
    "text",
    [
        "A car moving at 20 m/s stops after 5 s.",
        "A car travels at 20 m/s and takes 5 seconds to stop.",
        "It comes to a complete stop in 4 s.",
        "A car brakes from 30 m/s to a standstill in 6 s.",
        "A train moving at 25 m/s halts after 10 s.",
        "A bus travelling at 15 m/s becomes stationary 6 s later.",
        "Its speed falls to zero in 3 s.",
        "The driver reduces its speed to zero.",
        "The bus stops after 5 s.",
        "It slams on the brakes. What is the stopping distance?",
    ],
)
def test_it_ends_at_rest(text: str) -> None:
    motion = read_motion(text)
    assert motion.ends_at_rest and motion.changes_speed


@pytest.mark.parametrize(
    "text",
    [
        "A car starts from rest and reaches 20 m/s.",
        "It accelerates from a standstill.",
        "A cyclist is initially stationary.",
        "A sprinter at rest at first sets off.",
    ],
)
def test_it_starts_at_rest(text: str) -> None:
    motion = read_motion(text)
    assert motion.starts_at_rest and motion.changes_speed


@pytest.mark.parametrize(
    "text",
    [
        "It accelerates at 2 m/s².",
        "It decelerates uniformly.",
        "The car slows down.",
        "The runner speeds up.",
        "The car brakes.",
    ],
)
def test_its_speed_changes(text: str) -> None:
    assert read_motion(text).changes_speed


@pytest.mark.parametrize(
    "text",
    [
        "A car travels at a constant speed of 20 m/s for 5 seconds.",
        "A bus travels between two stops 3 km apart at 30 km/h.",
        "The next stop is 2 km away.",
        "A runner covers 400 m in 50 s.",
    ],
)
def test_a_steady_speed_or_a_place_called_a_stop_is_not_a_change(text: str) -> None:
    motion = read_motion(text)
    assert not motion.changes_speed and not motion.ends_at_rest


@pytest.mark.parametrize(
    ("text", "brakes"),
    [
        ("A car at 20 m/s brakes at 2 m/s².", True),
        ("A train decelerates at 1.5 m/s².", True),
        ("The car slows down at 3 m/s².", True),
        # Gravity turns a throw back: it does not brake it to rest.
        ("A ball is thrown straight up at 15 m/s.", False),
        ("A car accelerates at 2 m/s².", False),
    ],
)
def test_braking_brings_it_to_rest_and_a_throw_does_not(text: str, brakes: bool) -> None:
    assert read_motion(text).brakes is brakes


@pytest.mark.parametrize(
    ("text", "hold"),
    [
        ("A sprinter starts from rest and covers 100 m in 12 s. What is her average speed?", True),
        ("A cyclist accelerates and travels 300 m in 20 s. What is her average velocity?", True),
        ("A bus travels 120 km in 2 hours. What is its speed?", True),
        ("A car moving at 15 m/s brakes to a stop in 3 s. How far does it travel?", False),
        (
            "A runner accelerates from rest and covers 100 m in 10 s. What is her final speed?",
            False,
        ),
    ],
)
def test_constant_speed_laws_hold_for_an_average(text: str, hold: bool) -> None:
    # Review of #2333: an average speed is distance over time however the speed changes.
    assert constant_speed_laws_hold(text) is hold


@pytest.mark.parametrize(
    ("text", "halts"),
    [
        ("A car moving at 15 m/s brakes to a stop in 3 s. How far does it travel?", True),
        ("A train moving at 30 m/s slows down at 2 m/s². What is its speed after 20 s?", True),
        # Review of #2333: gravity slows a body only to turn it back.
        ("A ball is thrown up at 20 m/s and decelerates at 9.8 m/s² under gravity.", False),
        (
            "A stone is thrown vertically upward and decelerates. Find its velocity after 3 s.",
            False,
        ),
        ("A block slides up a frictionless incline at 6 m/s and decelerates at 4.9 m/s².", False),
        ("A rocket rises at 50 m/s and decelerates at 9.81 m/s once its engine cuts out.", False),
    ],
)
def test_only_brakes_keep_a_body_stopped(text: str, halts: bool) -> None:
    assert read_motion(text).halts is halts

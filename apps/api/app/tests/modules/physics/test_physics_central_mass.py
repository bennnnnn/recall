"""The mass of what orbits a body, or stands on it, is never the body's own mass.

"A 500 kg satellite orbits the earth at a radius of 7000 km. Find its orbital speed."
was verified as 6.9e-8 m/s: the satellite's 500 kg was read as the mass it orbits.
v = sqrt(GM/r) with Earth's mass is 7.55 km/s. Answers below are worked by hand with
G = 6.674e-11 and the masses and radii every school table gives.
"""

from __future__ import annotations

import math

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.tests.modules.physics.support import answer_number

_SETTINGS = Settings(math_tools_enabled=True)
_G = 6.674e-11
_EARTH = (5.972e24, 6.371e6)
_MARS = (6.417e23, 3.3895e6)
_MOON = 7.342e22


def _answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


def _orbit_speed(mass: float, radius: float) -> float:
    return math.sqrt(_G * mass / radius)


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        (
            "A 500 kg satellite orbits the earth at a radius of 7000 km. Find its orbital speed.",
            _orbit_speed(_EARTH[0], 7.0e6),
            "m/s",
        ),
        # No satellite mass at all: the named body still gives its mass.
        (
            "A satellite orbits the earth at a radius of 7000 km. Find its orbital speed.",
            _orbit_speed(_EARTH[0], 7.0e6),
            "m/s",
        ),
        (
            "A satellite of mass 800 kg orbits Earth at a radius of 8000 km. Find its orbital speed.",
            _orbit_speed(_EARTH[0], 8.0e6),
            "m/s",
        ),
        (
            "A 1000 kg satellite orbits Mars at a radius of 4000 km. Find its orbital speed.",
            _orbit_speed(_MARS[0], 4.0e6),
            "m/s",
        ),
        (
            "A 2000 kg probe orbits the Moon at a radius of 2000 km. What is its orbital speed?",
            _orbit_speed(_MOON, 2.0e6),
            "m/s",
        ),
        # A stated central mass is named by its body.
        (
            "A 500 kg satellite orbits a planet of mass 6e24 kg at a radius of 7000 km. "
            "Find its orbital speed.",
            _orbit_speed(6e24, 7.0e6),
            "m/s",
        ),
        # T = 2 pi r / v.
        (
            "A 500 kg satellite orbits the Earth at a radius of 7000 km. What is its orbital period?",
            2 * math.pi * 7.0e6 / _orbit_speed(_EARTH[0], 7.0e6),
            "s",
        ),
        # From the centre: R + h.
        (
            "A 500 kg satellite orbits 400 km above the Earth. What is its orbital speed?",
            _orbit_speed(_EARTH[0], _EARTH[1] + 4.0e5),
            "m/s",
        ),
        # The rocket's mass changes no escape speed: sqrt(2GM/R).
        (
            "A 1000 kg rocket leaves the Earth. What is the escape velocity?",
            math.sqrt(2 * _G * _EARTH[0] / _EARTH[1]),
            "m/s",
        ),
        # g = GM/R^2 on Mars; read as M, the astronaut's 70 kg gave 4.07e-22 m/s².
        (
            "A 70 kg astronaut stands on the surface of Mars. What is the gravitational "
            "acceleration there?",
            _G * _MARS[0] / _MARS[1] ** 2,
            "m/s",
        ),
        (
            "A 70 kg astronaut lands on a planet of mass 6e24 kg and radius 6.4e6 m. "
            "What is the surface gravity?",
            _G * 6e24 / 6.4e6**2,
            "m/s",
        ),
        # Look-alikes: a law that does take the small body's mass still reads it.
        (
            "A 70 kg astronaut is 400 km above the Earth. What is his weight?",
            _G * _EARTH[0] * 70 / (_EARTH[1] + 4.0e5) ** 2,
            "N",
        ),
        (
            "What is the gravitational force between two 1000 kg masses 10 m apart?",
            _G * 1000 * 1000 / 100,
            "N",
        ),
        # An asteroid's own mass is the central mass: sqrt(2GM/R).
        (
            "What is the escape velocity from the surface of a 1000 kg asteroid of radius 5 m?",
            math.sqrt(2 * _G * 1000 / 5),
            "m/s",
        ),
    ],
)
def test_the_central_mass_is_the_bodys_own(text: str, value: float, unit: str) -> None:
    answer = _answer(text)
    assert answer is not None, f"no verified answer for {text!r}"
    assert math.isclose(answer_number(answer), value, rel_tol=0.01), (text, answer, value)
    assert unit in answer, (text, answer)


_SUN = 1.989e30


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        # With two bodies named, the one orbited is the central one; the orbiter never is.
        (
            "The Earth orbits the Sun at a radius of 1.5e11 m. Find its orbital speed.",
            _orbit_speed(_SUN, 1.5e11),
            "m/s",
        ),
        (
            "Mars orbits the Sun at a radius of 2.28e11 m. Find its orbital speed.",
            _orbit_speed(_SUN, 2.28e11),
            "m/s",
        ),
        (
            "The Moon orbits the Earth at a radius of 3.84e8 m. Find its orbital speed.",
            _orbit_speed(_EARTH[0], 3.84e8),
            "m/s",
        ),
        # Kepler on main: 579 years.
        (
            "The Earth orbits the Sun at a radius of 1.5e11 m. What is its orbital period?",
            2 * math.pi * 1.5e11 / _orbit_speed(_SUN, 1.5e11),
            "s",
        ),
        (
            "A probe sent from Earth orbits Mars at a radius of 4000 km. Find its orbital speed.",
            _orbit_speed(_MARS[0], 4.0e6),
            "m/s",
        ),
        (
            "A spacecraft leaves Earth and goes into orbit around the Moon at a radius of 2000 km. "
            "Find its orbital speed.",
            _orbit_speed(_MOON, 2.0e6),
            "m/s",
        ),
        (
            "A satellite orbits a body of mass 6e24 kg at a radius of 8000 km. Find its orbital speed.",
            _orbit_speed(6e24, 8.0e6),
            "m/s",
        ),
        # The force between two bodies takes both masses, whatever they are called.
        (
            "A 5 kg ball and a 10 kg ball are 2 m apart. Find the gravitational force between them.",
            _G * 50 / 4,
            "N",
        ),
        (
            "A rock of mass 2 kg and a stone of mass 3 kg are 0.5 m apart. Find the gravitational "
            "force between them.",
            _G * 6 / 0.25,
            "N",
        ),
        (
            "A 70 kg man stands on Earth. The planet has a mass of 6e24 kg and a radius of 6.4e6 m. "
            "Find the gravitational force on him.",
            _G * 70 * 6e24 / 6.4e6**2,
            "N",
        ),
    ],
)
def test_the_orbited_body_gives_the_mass(text: str, value: float, unit: str) -> None:
    answer = _answer(text)
    assert answer is not None, f"no verified answer for {text!r}"
    assert math.isclose(answer_number(answer), value, rel_tol=0.01), (text, answer, value)
    assert unit in answer, (text, answer)


@pytest.mark.parametrize(
    "text",
    [
        # Venus has no numbers in the table: Earth's mass answered 7546 m/s.
        "A probe from Earth orbits Venus at a radius of 7000 km. Find its orbital speed.",
        # The orbiting Moon's own mass is not the Earth's (113 m/s for 1019).
        "The Moon orbits the Earth at a radius of 3.84e8 m. The Moon's mass is 7.35e22 kg. "
        "Find its orbital speed.",
        "The Moon, of mass 7.35e22 kg, orbits the Earth at a radius of 3.84e8 m. Find its orbital speed.",
        # mgh is no orbit's energy (3.43e10 J with h = 7000 km).
        "A satellite orbits Earth at a radius of 7000 km. Find the gravitational potential energy "
        "of the 500 kg satellite.",
        # No mass for the planet at all.
        "A 500 kg satellite orbits a planet at a radius of 7000 km. Find its orbital speed.",
    ],
)
def test_no_central_mass_is_guessed(text: str) -> None:
    assert _answer(text) is None, (text, _answer(text))

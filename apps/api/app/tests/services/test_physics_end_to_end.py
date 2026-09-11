"""Physics path: message → gate → extract → verified block.

Extractor-only tests cannot see a gate that is a subset of the cue lists,
or algebra stealing textbook ``h = 20 m`` assignments.
"""

from __future__ import annotations

import math

import pytest

from app.core.config import Settings
from app.services.math_tools import (
    _build_verified_block,
    extract_math_intent,
    maybe_direct_math_reply,
    needs_symbolic_math,
)

_SETTINGS = Settings(math_tools_enabled=True)


def _answer_number(answer: str) -> float:
    return float(answer.split()[0])


@pytest.mark.parametrize(
    "message, kind, expected",
    [
        (
            "A ball is dropped from 20 m. How long until it hits the ground?",
            "kinematics",
            ("2.02 s", math.sqrt(2 * 20 / 9.81)),
        ),
        (
            "A ball is dropped from 20 m on the moon. How long until it hits the ground?",
            "kinematics",
            ("4.97 s", math.sqrt(2 * 20 / 1.62)),
        ),
        (
            "A ball is dropped from 20 m into a marsh. How long until it hits the ground?",
            "kinematics",
            ("2.02 s", math.sqrt(2 * 20 / 9.81)),
        ),
        (
            "A ball is dropped from 20 m in the moonlight. How long until it hits the ground?",
            "kinematics",
            ("2.02 s", math.sqrt(2 * 20 / 9.81)),
        ),
        (
            "A ball is thrown up at 15 m/s. How long until it lands?",
            "kinematics",
            ("3.06 s", 2 * 15 / 9.81),
        ),
        (
            "A stone falls off a 30 m ledge. How long until it lands?",
            "kinematics",
            ("2.47 s", math.sqrt(2 * 30 / 9.81)),
        ),
        (
            "A ball rolls off a 30 m ledge. How long to reach the ground?",
            "kinematics",
            ("2.47 s", math.sqrt(2 * 30 / 9.81)),
        ),
        (
            "A ball is dropped from h = 20 m. How long until it hits the ground?",
            "kinematics",
            ("2.02 s", math.sqrt(2 * 20 / 9.81)),
        ),
        (
            "A ball is dropped. Given v0 = 0 and h0 = 20 m, how long until it hits?",
            "kinematics",
            ("2.02 s", math.sqrt(2 * 20 / 9.81)),
        ),
        (
            "A ball is dropped from 20 m. What is its speed after 1 s?",
            "kinematics",
            ("9.81 m/s", 9.81),
        ),
        (
            "A ball is dropped from 20 m. What is its velocity after 1 s?",
            "kinematics",
            ("-9.81 m/s", -9.81),
        ),
        (
            "What is the range of a ball launched at 20 m/s at 30°?",
            "projectile",
            ("35.31 m", 20.0**2 * math.sin(math.radians(60)) / 9.81),
        ),
        (
            "What is the trajectory of a ball launched at 20 m/s at 30°?",
            "projectile",
            ("35.31 m", 20.0**2 * math.sin(math.radians(60)) / 9.81),
        ),
        (
            "A projectile is launched at 20 m/s at 30 degrees from a 10 m cliff. What is its range?",
            "projectile",
            ("48.04 m", None),
        ),
        (
            "A projectile is launched at 20 m/s at 30 degrees. What is its maximum height?",
            "projectile",
            ("5.10 m", 20.0**2 * math.sin(math.radians(30)) ** 2 / (2 * 9.81)),
        ),
        (
            "A projectile is launched at 20 m/s at 30 degrees. A wall is 15 m away. What is the range?",
            "projectile",
            ("35.31 m", 20.0**2 * math.sin(math.radians(60)) / 9.81),
        ),
        (
            "A projectile is fired at an angle of 25 degrees at 40 m/s. What is the range?",
            "projectile",
            ("124.85 m", 40.0**2 * math.sin(math.radians(50)) / 9.81),
        ),
        (
            "What is the energy of a 2 kg object moving at 3 m/s?",
            "energy",
            ("9.00 J", 0.5 * 2 * 9),
        ),
        (
            "What is the potential energy of a 3 kg object at a height of 5 m?",
            "energy",
            ("147.15 J", 3 * 9.81 * 5),
        ),
        (
            "How much work is done by a 10 N force over a distance of 5 m?",
            "energy",
            ("50.00 J", 50.0),
        ),
        (
            "What is the power of a 200 N force at 3 m/s?",
            "energy",
            ("600.00 W", 600.0),
        ),
        (
            "A force of 200 N moves an object at 3 m/s. What is the power?",
            "energy",
            ("600.00 W", 600.0),
        ),
        (
            "A net force of 10 N acts on a 2 kg mass. What is the acceleration?",
            "force",
            ("5.00 m/s^2", 5.0),
        ),
    ],
)
def test_physics_gate_extract_block_answer(
    message: str,
    kind: str,
    expected: tuple[str, float | None],
) -> None:
    _display, expected_value = expected
    assert needs_symbolic_math(message) is True
    intent = extract_math_intent(message)
    assert intent is not None
    assert intent.kind == kind
    block = _build_verified_block(intent, _SETTINGS)
    assert block is not None
    assert block.canonical_answer is not None
    assert "m = 0" not in block.canonical_answer
    got = _answer_number(block.canonical_answer)
    if expected_value is None:
        assert abs(got - 48.04) < 0.05
    else:
        assert abs(got - expected_value) < 0.02


def test_car_acceleration_is_not_verified_minus_g() -> None:
    message = "A car speeds up from 0 to 30 m/s in 5 s. What is the acceleration of the car?"
    assert needs_symbolic_math(message) is True
    intent = extract_math_intent(message)
    assert intent is None or intent.kind != "kinematics" or intent.physics_op != "acceleration"
    if intent is not None:
        block = _build_verified_block(intent, _SETTINGS)
        if block is not None and block.canonical_answer:
            assert "-9.81" not in block.canonical_answer


def test_force_energy_do_not_direct_reply() -> None:
    message = "A net force of 10 N acts on a 2 kg mass. What is the acceleration?"
    intent = extract_math_intent(message)
    assert intent is not None
    block = _build_verified_block(intent, _SETTINGS)
    assert block is not None
    assert block.allow_direct is False
    assert maybe_direct_math_reply(block, message) is None

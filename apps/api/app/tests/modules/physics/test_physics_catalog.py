"""The formula catalog is the verified-operation list, and the new mechanics stay closed."""

from __future__ import annotations

import types
from pathlib import Path
from typing import Union, get_args, get_origin

import pytest

from app.core.config import Settings
from app.models.schemas.physics.intent import PhysicsIntent
from app.modules.physics.catalog import CATALOG
from app.modules.physics.extract import _ADVANCED_PHYSICS_RE, _UNVERIFIED_PHYSICS_PHRASES
from app.tests.modules.physics.support import (
    build_verified_physics_block,
    extract_physics_intent,
    maybe_direct_physics_reply,
)

_SETTINGS = Settings(math_tools_enabled=True)

_FEATURES_MARKERS = (
    "Schrödinger",
    "quantum harmonic oscillator",
    "Rydberg",
    "Planck's distribution",
    "binding energy",
    "mass defect",
    "general relativity",
)


def _features_text() -> str:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "FEATURES.md"
        if candidate.is_file():
            return candidate.read_text()
    raise AssertionError("FEATURES.md is missing")


def _answer(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


def _reply(text: str) -> str | None:
    intent = extract_physics_intent(text)
    if intent is None:
        return None
    block = build_verified_physics_block(intent, _SETTINGS)
    if block is None:
        return None
    return maybe_direct_physics_reply(block, text)


def _literal_values(annotation: object) -> set[str]:
    """Strings inside a Literal, including ``Literal[...] | None``."""
    if annotation is type(None):
        return set()
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        values: set[str] = set()
        for arg in get_args(annotation):
            values.update(_literal_values(arg))
        return values
    return {arg for arg in get_args(annotation) if isinstance(arg, str)}


def test_catalog_ids_match_the_physics_op_literal() -> None:
    literal = _literal_values(PhysicsIntent.model_fields["physics_op"].annotation)
    kinds = _literal_values(PhysicsIntent.model_fields["kind"].annotation)
    assert literal == set(CATALOG)
    assert all(spec.kind in kinds for spec in CATALOG.values())
    assert all(
        spec.law_name.strip() and spec.law_name != "Physics formula" for spec in CATALOG.values()
    )


def test_unverified_topics_stay_out_of_the_catalog_and_the_docs() -> None:
    features = " ".join(_features_text().split())
    assert "not twenty formulas" in features
    assert "relativity, quantum states, alternating current" not in features
    for phrase in _UNVERIFIED_PHYSICS_PHRASES:
        assert _ADVANCED_PHYSICS_RE.search(phrase), phrase
        slug = phrase.replace("'", "").replace(" ", "_")
        assert slug not in CATALOG
    for marker in _FEATURES_MARKERS:
        assert marker in features
        assert marker.lower().replace(" ", "_").replace("'", "") not in CATALOG


@pytest.mark.parametrize(
    ("text", "op", "answer"),
    [
        (
            "Find the work done by a force of 10 N at 60 degrees over a distance of 3 m.",
            "work",
            "15 J",
        ),
        (
            "How much work is done by a 10 N force at an angle of 30 degrees over 4 m?",
            "work",
            "34.6 J",
        ),
        (
            "A force of 10 N at 60 degrees moves an object at 4 m/s. What is the power?",
            "power",
            "20 W",
        ),
        (
            "A 3 kg block speeds up from 2 m/s to 6 m/s. Find the net work.",
            "work_energy",
            "48 J",
        ),
        (
            "The net work on a 2 kg object is 40 J. It has an initial speed of 3 m/s. "
            "Find the final speed.",
            "work_energy",
            "7 m/s",
        ),
        (
            "Using conservation of energy, an object starts from rest at an initial height "
            "of 20 m. Find its speed at a final height of 5 m.",
            "mechanical_energy_gravity",
            "17.2 m/s",
        ),
        (
            "Using conservation of energy, a 0.4 kg mass on a spring of constant 100 N/m "
            "is released from rest with an initial compression of 0.2 m. "
            "Find its speed at equilibrium.",
            "mechanical_energy_spring",
            "3.16 m/s",
        ),
        (
            "A wheel has initial angular velocity 2 rad/s and angular acceleration "
            "3 rad/s^2. Find the angular velocity after 4 s.",
            "rotational_omega",
            "14 rad/s",
        ),
        (
            "A disk starts from rest with angular acceleration 2 rad/s^2. "
            "Find the angular displacement after 3 s.",
            "rotational_theta",
            "9 rad",
        ),
        (
            "Angular velocity increases from 4 rad/s to 10 rad/s in 2 s. "
            "Find the angular acceleration.",
            "rotational_alpha",
            "3 rad/s²",
        ),
        (
            "A torque of 6 N m acts on a moment of inertia of 2 kg m^2. "
            "Find the angular acceleration.",
            "torque_inertia",
            "3 rad/s²",
        ),
        (
            "Angular momentum changes from 4 to 10 kg m^2/s in 3 s. Find the torque.",
            "torque_angular_impulse",
            "2 N·m",
        ),
        (
            "An isolated skater with moment of inertia 4 kg m^2 spins at 2 rad/s. "
            "The moment of inertia becomes 1 kg m^2. Find the final angular velocity.",
            "angular_momentum_conservation",
            "8 rad/s",
        ),
        (
            "A wheel of radius 0.5 m rolls without slipping at 4 rad/s. Find the speed.",
            "rolling_speed",
            "2 m/s",
        ),
        (
            "A wheel of radius 0.25 m rolls without slipping with acceleration 2 m/s^2. "
            "Find the angular acceleration.",
            "rolling_acceleration",
            "8 rad/s²",
        ),
        (
            "A 3 kg solid cylinder of radius 0.2 m rolls without slipping at 4 m/s. "
            "Its moment of inertia is 0.06 kg m^2. Find the total kinetic energy.",
            "rolling_kinetic_energy",
            "36 J",
        ),
        (
            "A body's moment of inertia about its center of mass is 2 kg m^2. "
            "Its mass is 4 kg and the axis is 0.5 m away. "
            "Find the moment of inertia by the parallel-axis theorem.",
            "parallel_axis",
            "3 kg·m²",
        ),
    ],
)
def test_new_mechanics_operations_verify(text: str, op: str, answer: str) -> None:
    intent = extract_physics_intent(text)
    assert intent is not None
    assert intent.physics_op == op
    assert _answer(text) == answer


@pytest.mark.parametrize(
    "text",
    [
        "How much work is done by a 10 N force at an angle over 4 m?",
        "Use conservation of energy for a 2 kg cart moving at 10 m/s from a height of 5 m.",
        "Using conservation of energy, a rough 2 kg block slides from rest at an initial "
        "height of 5 m. Find its speed at the ground.",
        "Tell me about energy conservation.",
    ],
)
def test_open_mechanics_requests_stay_unverified(text: str) -> None:
    assert extract_physics_intent(text) is None


@pytest.mark.parametrize(
    ("text", "present", "absent"),
    [
        (
            "period of a 2 m pendulum",
            "small-angle approximation",
            None,
        ),
        (
            "a ball is thrown at 20 m/s at 30 degrees, what is the range?",
            "same launch and landing height",
            None,
        ),
        (
            "A projectile is launched at 20 m/s at 30 degrees from a 10 m cliff. "
            "What is its range?",
            None,
            "same launch and landing height",
        ),
        (
            "How much work is done by a 10 N force over a distance of 4 m?",
            "force parallel to the displacement",
            None,
        ),
        (
            "Find the work done by a force of 10 N at 60 degrees over a distance of 3 m.",
            None,
            "force parallel to the displacement",
        ),
        (
            "power of a 10 N force moving at 3 m/s",
            "force parallel to the velocity",
            None,
        ),
        (
            "what power is needed to do 100 J of work in 5 s",
            None,
            "force parallel to the velocity",
        ),
        (
            "what is the pressure at 3 m depth in water",
            "gauge pressure, not absolute",
            None,
        ),
        (
            "what is the force on a charge of 2 C moving at 10 m/s in a 0.4 T magnetic field",
            "velocity is perpendicular to the field",
            None,
        ),
        (
            "what is the force on a charge of 2 C moving at 10 m/s "
            "in a 0.4 T magnetic field at 30 degrees",
            None,
            "velocity is perpendicular to the field",
        ),
    ],
)
def test_assumptions_appear_once_in_the_formula_section(
    text: str, present: str | None, absent: str | None
) -> None:
    reply = _reply(text)
    assert reply is not None
    if present is not None:
        assert reply.count(present) == 1
        assert reply.count("Assumption:") >= 1
    if absent is not None:
        assert absent not in reply

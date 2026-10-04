"""Keep real solver payloads in the mobile renderer contract fixture current."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.models.schemas.physics.simulation import SIMULATION_SPEC_TYPES
from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.solver import solve_physics

_FIXTURE = (
    Path(__file__).resolve().parents[6]
    / "apps/mobile/lib/__tests__/fixtures/physicsNativeScenes.json"
)


def _assert_same_payload(actual: Any, expected: Any) -> None:
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            _assert_same_payload(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for got, want in zip(actual, expected, strict=True):
            _assert_same_payload(got, want)
    elif type(expected) is float:
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
    else:
        assert actual == expected


def test_all_native_scene_types_have_real_solver_payloads_in_mobile_tests() -> None:
    fixtures = json.loads(_FIXTURE.read_text())
    assert {fixture["scene"]["type"] for fixture in fixtures} == SIMULATION_SPEC_TYPES
    for fixture in fixtures:
        intent = extract_physics_intent(fixture["problem"])
        assert intent is not None, fixture["name"]
        scenes = solve_physics(intent).simulation_specs
        assert len(scenes) == 1, fixture["name"]
        _assert_same_payload(scenes[0].model_dump(exclude_none=True), fixture["scene"])

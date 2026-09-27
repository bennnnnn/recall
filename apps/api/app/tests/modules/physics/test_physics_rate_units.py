"""Distance-speed-time quantities preserve their actual supplied units."""

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent


@pytest.mark.parametrize(
    "prompt, answer",
    [
        ("Find the average speed for 100 m in 20 s.", "5 m/s"),
        ("A car travels 180 meters in 12 seconds. What is its average speed?", "15 m/s"),
        ("Find the average speed for 20 s over 100 m.", "5 m/s"),
        ("average speed 120 km in 2 hours", "60 km/h"),
        ("average speed 100 cm in 20 seconds", "5 cm/s"),
        ("average speed 100 feet in 20 minutes", "5 ft/min"),
        ("average speed .5 m in 2 s", "0.25 m/s"),
        ("average speed 0.5 m in 2 s", "0.25 m/s"),
        ("average speed 1.5 m in .5 s", "3 m/s"),
        ("average speed +.5 m in 2 s", "0.25 m/s"),
    ],
)
def test_rate_answer_retains_supplied_units(prompt: str, answer: str) -> None:
    intent = extract_physics_intent(prompt)
    assert intent is not None and intent.kind == "kinematics"
    block = build_verified_physics_block(intent, Settings())
    assert block is not None and block.canonical_answer == answer


@pytest.mark.parametrize(
    "prompt",
    [
        "Find the average speed for 100 kg in 20 s.",
        "Find the average speed for 100 m in 20 bananas.",
        "Find the average speed for 100 m/s in 20 s.",
        "Find the average speed for 100 m in 20 s and then 50 m in 10 s.",
        "Find the average speed for 100 m in 20 s and tell me a joke.",
        "Find the average speed for 100 m in 20 s in km/h.",
        "average speed .5 m in -.5 s",
        "average speed -.5 m in 2 s",
    ],
)
def test_invalid_or_compound_rate_request_fails_closed(prompt: str) -> None:
    assert extract_physics_intent(prompt) is None

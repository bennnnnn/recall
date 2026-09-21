"""Physics preflight must not reject mathematical uses of its broad cues."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.models.schemas.physics import PhysicsIntent
from app.services.math.tools import _build_verified_block, extract_math_intent


@pytest.mark.parametrize(
    "text,expected",
    [
        ("range of 1,2,3,4", [1, 2, 3, 4]),
        ("find the range of 1, 2, 3, 4", [1, 2, 3, 4]),
        ("range of 1/2,3/2", [0.5, 1.5]),
        ("range of 1e3,3e3", [1000, 3000]),
        ("range of -.5,.5", [-0.5, 0.5]),
    ],
)
def test_statistical_range_keeps_its_data_grammar(text: str, expected: list[float]) -> None:
    intent = extract_math_intent(text)
    assert isinstance(intent, MathIntent)
    assert intent.kind == "statistics"
    assert intent.stats_op == "range"
    assert intent.stats_numbers == expected
    block = _build_verified_block(intent, Settings(math_tools_enabled=True))
    assert block is not None and block.canonical_answer is not None
    assert float(block.canonical_answer) == pytest.approx(max(expected) - min(expected))


@pytest.mark.parametrize("order", [1, 2, 3])
def test_find_f_primes_is_a_derivative_not_a_force(order: int) -> None:
    primes = "'" * order
    text = f"f(x) = x^3 - 3x, find f{primes}(x)"
    intent = extract_math_intent(text)
    assert isinstance(intent, MathIntent)
    assert intent.kind == "calculus"
    assert intent.operation == "differentiate"
    assert intent.derivative_order == order
    block = _build_verified_block(intent, Settings(math_tools_enabled=True))
    assert block is not None and block.canonical_answer is not None
    assert block.canonical_answer == {1: "3 x^{2} - 3", 2: "6 x", 3: "6"}[order]


def test_find_f_without_primes_still_normalizes_physics_quantities() -> None:
    text = "find f for a .5 kg object with acceleration 2 m/s^2"
    intent = extract_math_intent(text)
    assert isinstance(intent, PhysicsIntent)
    assert intent.kind == "force"
    assert intent.physics_params == {"m": 0.5, "a": 2.0}
    block = _build_verified_block(intent, Settings(math_tools_enabled=True))
    assert block is not None and block.canonical_answer == "1 N"


@pytest.mark.parametrize(
    "text",
    [
        "find f for a 1/2 kg object with acceleration 2 m/s^2",
        "find f for a 1.2.3 kg object with acceleration 2 m/s^2",
        "range of a projectile launched at 1,00 m/s at 30 degrees",
        "range of a projectile launched at 1e+ m/s at 30 degrees",
    ],
)
def test_shared_words_do_not_bypass_malformed_physics_rejection(text: str) -> None:
    assert extract_math_intent(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "kinetic energy of a 1/2 kg object at 2 m/s, find f''(x)",
        "a 2 kg ball at 3 m/s hits a 1 kg ball elastically; find f''(x)",
        "kinetic energy of a 1/2 kg object at 2 m/s; range of 1,2,3,4",
    ],
)
def test_math_fragments_do_not_override_physics_refusals(text: str) -> None:
    assert extract_math_intent(text) is None

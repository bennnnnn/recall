"""A lesson states a rule once: under its name, not again beside the step that uses it.

"Find the derivative of ln(x^2 + 1)" printed the chain rule as the Formula and again beside
step 1, and "Integrate x sin x dx" integration by parts the same way (2026-11-08).
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.math.tools.block import _build_verified_block
from app.modules.math.tools.direct import maybe_direct_math_reply
from app.modules.math.tools.extract import extract_math_intent


def _reply(prompt: str) -> str:
    intent = extract_math_intent(prompt)
    assert intent is not None
    verified = _build_verified_block(intent, Settings(math_tools_enabled=True))
    assert verified is not None
    reply = maybe_direct_math_reply(verified, prompt)
    assert reply is not None
    return reply


@pytest.mark.parametrize(
    "prompt",
    [
        "Find the derivative of ln(x^2 + 1)",
        "Find the derivative of sin(3x^2)",
        "Integrate x sin x dx",
    ],
)
def test_a_rule_the_formula_states_is_not_written_beside_its_step(prompt: str) -> None:
    reply = _reply(prompt)
    assert "Chain rule:" not in reply
    assert "Integration by parts: $" not in reply

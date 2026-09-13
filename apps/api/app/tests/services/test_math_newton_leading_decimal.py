"""Newton's recorded initial value must retain a signed leading decimal."""

import pytest

from app.core.config import Settings
from app.services.math_fence import validate_math_fences
from app.services.math_tools.block import _build_verified_block
from app.services.math_tools.direct import maybe_direct_math_reply
from app.services.math_tools.extract import extract_math_intent
from app.services.math_tools.helpers import _parse_newton_guess


@pytest.mark.parametrize(
    "literal, expected", [(".5", 0.5), ("-.5", -0.5), ("+.5", 0.5), ("1", 1.0)]
)
def test_signed_leading_decimal_is_one_complete_newton_guess(literal: str, expected: float) -> None:
    query = f"Use Newton method to solve x^2-2=0 starting at {literal}"
    guess, equation = _parse_newton_guess(query)
    assert guess == expected
    assert equation == "Use Newton method to solve x^2-2=0"
    intent = extract_math_intent(query)
    assert intent is not None
    assert intent.newton_guess == expected
    block = _build_verified_block(intent, Settings(math_tools_enabled=True))
    assert block is not None and block.newton_input is not None and block.newton_result is not None
    assert block.newton_input.initial_guess == expected
    assert block.newton_result.iterations[0].x_n == expected
    assert block.newton_result.converged
    assert block.newton_result.root is not None
    assert block.newton_result.root * expected > 0
    reply = maybe_direct_math_reply(block, query)
    assert reply is not None
    assert f"| 0 | {expected:g} |" in reply
    assert validate_math_fences(reply, verified=block) == reply

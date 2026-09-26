"""A physics turn must not be labeled or wrapped as math."""

from app.core.config import Settings
from app.modules.math.reply_policy import MATH_REPLY_POLICY
from app.modules.math.tools import _build_verified_block, extract_math_intent
from app.services.chat.prompt_builder import _physics_turn, _style_format_hints
from app.services.chat.prompt_constants import (
    MATH_INTENT_HINT,
    MATH_TUTORING_HINT,
    PHYSICS_INTENT_HINT,
    PHYSICS_REPLY_POLICY,
)
from app.services.solving import strip_verified_math_markers

_DROP = "A ball is dropped from a height of 20 m. Find the time to ground. Use g=10."
_ALGEBRA = "Solve 2x + 3 = 7"


def test_physics_turn_is_not_labeled_as_math() -> None:
    assert _physics_turn(_DROP)
    assert not _physics_turn(_ALGEBRA)


def test_physics_prompt_uses_physics_hints() -> None:
    hints = _style_format_hints(
        query_text=_DROP,
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
    )
    assert PHYSICS_INTENT_HINT in hints
    assert PHYSICS_REPLY_POLICY in hints
    assert MATH_INTENT_HINT not in hints
    assert MATH_TUTORING_HINT not in hints
    assert MATH_REPLY_POLICY not in hints
    joined = "\n".join(hints)
    assert "Math / algebra" not in joined
    assert "Math tutoring" not in joined
    assert "[BEGIN VERIFIED PHYSICS]" in joined


def test_verified_physics_block_is_not_wrapped_as_math() -> None:
    intent = extract_math_intent(_DROP)
    assert intent is not None
    block = _build_verified_block(intent, Settings(math_tools_enabled=True))
    assert block is not None
    assert block.text.startswith("[BEGIN VERIFIED PHYSICS]")
    assert "[BEGIN VERIFIED MATH]" not in block.text
    assert "2 s" in strip_verified_math_markers(block.text)
    assert "[BEGIN VERIFIED PHYSICS]" not in strip_verified_math_markers(block.text)

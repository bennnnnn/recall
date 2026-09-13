"""Unknown notation needs clarification even when math intent does not match."""

from __future__ import annotations

import pytest

from app.services.chat.prompt_builder import _style_format_hints
from app.services.chat.prompt_constants.math import (
    MATH_FENCE_SAFETY_HINT,
    MATH_NOTATION_CLARIFICATION_HINT,
)
from app.services.math_text_match import needs_symbolic


@pytest.mark.parametrize("style", ["balanced", "short"])
@pytest.mark.parametrize("compact", [False, True])
def test_unknown_notation_gets_clarification_without_math_intent(style: str, compact: bool) -> None:
    query = "What is frad{64}?"
    assert not needs_symbolic(query)
    hints = _style_format_hints(
        query_text=query,
        style=style,
        is_day_plan=False,
        minimal_personal_context=False,
        compact=compact,
    )
    assert MATH_FENCE_SAFETY_HINT in hints
    assert "\n".join(hints).count(MATH_NOTATION_CLARIFICATION_HINT) == 1


@pytest.mark.parametrize(
    "style,compact", [("balanced", False), ("short", False), ("balanced", True)]
)
def test_recognized_math_turn_keeps_clarification_guard_and_standard_aliases(
    style: str, compact: bool
) -> None:
    hints = _style_format_hints(
        query_text="Solve x + 1 = 3",
        style=style,
        is_day_plan=False,
        minimal_personal_context=False,
        compact=compact,
    )
    joined = "\n".join(hints)
    assert joined.count(MATH_NOTATION_CLARIFICATION_HINT) == 1
    assert "ask one brief clarification" in joined
    assert "Do not invent a named mathematical concept or silently change the expression" in joined
    assert "Standard, unambiguous notation aliases are fine." in joined

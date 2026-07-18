"""_style_format_hints: SHORT style must keep math safety guardrails.

BUG FIX regression: SHORT response style used to append only
SHORT_RESPONSE_FORMAT_HINT, skipping MATH_SOLVER_HINT and the math half of
INTENT_FORMAT_HINT entirely — a user on Short style got no guardrail against
raw ```latex/```tex/```copy fences for math and no instruction to use
```answer for the final result.
"""

from __future__ import annotations

from app.services.chat.prompt_builder import _style_format_hints
from app.services.chat.prompt_constants import SHORT_MATH_SAFETY_HINT


def _hints(style: str) -> list[str]:
    return _style_format_hints(
        query_text="Solve 2x + 3 = 7",
        style=style,
        is_day_plan=False,
        minimal_personal_context=False,
    )


def test_short_style_still_includes_math_safety_guardrails():
    parts = _hints("short")
    assert SHORT_MATH_SAFETY_HINT in parts
    joined = "\n".join(parts)
    assert "```answer" in joined
    assert "```latex" in joined


def test_balanced_style_keeps_full_math_solver_hint():
    parts = _hints("balanced")
    joined = "\n".join(parts)
    # Full hint set still present for non-short styles — unaffected by the fix.
    assert "Math diagrams and plots" in joined
    assert SHORT_MATH_SAFETY_HINT not in parts

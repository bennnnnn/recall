"""_style_format_hints: SHORT style must keep math safety guardrails.

BUG FIX regression: SHORT response style used to append only
SHORT_RESPONSE_FORMAT_HINT, skipping MATH_SOLVER_HINT and the math half of
INTENT_FORMAT_HINT entirely — a user on Short style got no guardrail against
raw ```latex/```tex/```copy fences for math so verified math still has latex/fence guardrails.
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


def _day_plan_hints() -> list[str]:
    return _style_format_hints(
        query_text="plan my day",
        style="balanced",
        is_day_plan=True,
        minimal_personal_context=False,
    )


def test_day_plan_keeps_math_safety_guardrails():
    """BUG FIX (MATH-BE-033): day-plan turns used to get only
    RESPONSE_FORMAT_HINT, so a math question that landed in day-plan mode
    lost every guardrail against raw ```latex/```copy fences. The compact
    math safety hint now ships on day-plan turns too."""
    parts = _day_plan_hints()
    assert SHORT_MATH_SAFETY_HINT in parts
    joined = "\n".join(parts)
    assert "Do NOT emit ```answer" in joined
    assert "```latex" in joined


def test_short_style_still_includes_math_safety_guardrails():
    parts = _hints("short")
    assert SHORT_MATH_SAFETY_HINT in parts
    joined = "\n".join(parts)
    assert "Do NOT emit ```answer" in joined
    assert "```latex" in joined


def test_balanced_style_injects_universal_format_baseline():
    from app.services.chat.prompt_constants import UNIVERSAL_FORMAT_BASELINE

    parts = _hints("balanced")
    assert UNIVERSAL_FORMAT_BASELINE in parts
    joined = "\n".join(parts)
    assert "Lead with the answer; explanation after." in joined
    assert "Do not decorate with emoji unless the user used them." in joined
    assert "[OpenAI docs](url)" in joined
    assert "do not add sections just to look structured" in joined


def test_closed_form_math_prompt_is_instance_first_not_a_lecture():
    """4! used to get 'start with n! definition + numbered steps + You can check'
    plus a fun-fact callout. Prompt now matches a one-line identity."""
    from app.services.chat.prompt_constants import MATH_INTENT_HINT, SHORT_MATH_SAFETY_HINT

    assert "Closed-form" in SHORT_MATH_SAFETY_HINT
    assert "$3 + 0 = 3$" in MATH_INTENT_HINT
    assert "$4! = 4 \\times 3 \\times 2 \\times 1 = 24$" in MATH_INTENT_HINT
    assert "no general" in MATH_INTENT_HINT
    assert "Skip that block on n!" in MATH_INTENT_HINT
    assert "Never mention SymPy" in MATH_INTENT_HINT
    # Old tutor shape must not return.
    assert "3! begins with" not in MATH_INTENT_HINT
    assert "Do not jump straight to the instance" not in MATH_INTENT_HINT


def test_funny_tone_does_not_pad_one_line_arithmetic() -> None:
    from app.services.response_tone import TONE_HINTS

    funny = TONE_HINTS["funny"]
    assert "3+0" in funny
    assert "one line" in funny
    assert "```tip" in funny


def test_balanced_style_keeps_full_math_solver_hint():
    parts = _hints("balanced")
    joined = "\n".join(parts)
    # Full hint set still present for non-short styles — unaffected by the fix.
    assert "Math diagrams and plots" in joined
    assert SHORT_MATH_SAFETY_HINT not in parts


def test_balanced_style_includes_math_tutoring_hint():
    """BUG FIX (MATH-E2E-004): the model used to just re-ask or hand over the
    answer when a user gave a wrong math answer. The tutoring hint now tells
    it to point to the wrong step and give a small hint first."""
    parts = _hints("balanced")
    joined = "\n".join(parts)
    assert "Math tutoring" in joined
    assert "wrong" in joined.lower()


def test_slim_casual_turn_uses_compact_math_safety_not_viz_pack():
    """Help-me-think / slim chat must not dump the format+viz+solver bible."""
    from app.services.chat.prompt_constants import (
        FORMAT_CONTRACT,
        MATH_SOLVER_HINT,
        VISUALIZATION_HINTS,
    )

    parts = _style_format_hints(
        query_text="I want to talk something through — ask me a good opening question.",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert SHORT_MATH_SAFETY_HINT in parts
    assert FORMAT_CONTRACT not in parts
    assert MATH_SOLVER_HINT not in parts
    assert VISUALIZATION_HINTS not in parts
    joined = "\n".join(parts)
    assert "Do NOT emit ```answer" in joined
    assert "Math diagrams and plots" not in joined


def test_rich_turn_injects_format_contract_once_and_keeps_math():
    from app.services.chat.prompt_constants import (
        COMPARISON_FORMAT_HINT,
        FORMAT_CONTRACT,
        MATH_INTENT_HINT,
        MATH_SOLVER_HINT,
    )

    parts = _hints("balanced")
    assert parts.count(FORMAT_CONTRACT) == 1
    assert MATH_INTENT_HINT in parts
    assert MATH_SOLVER_HINT in parts
    assert COMPARISON_FORMAT_HINT not in parts


def test_chart_query_gets_vega_fence_layout():
    from app.services.chat.prompt_constants import (
        CHART_FORMAT_HINT,
        COMPACT_RESPONSE_FORMAT_HINT,
    )

    slim = _style_format_hints(
        query_text="Make a bar chart of average monthly rainfall in Seattle",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert CHART_FORMAT_HINT in slim
    assert COMPACT_RESPONSE_FORMAT_HINT not in slim

    rich = _style_format_hints(
        query_text="Make a bar chart of average monthly rainfall in Seattle",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=False,
    )
    assert CHART_FORMAT_HINT in rich


def test_mermaid_query_gets_flowchart_fence_layout():
    from app.services.chat.prompt_constants import (
        COMPACT_RESPONSE_FORMAT_HINT,
        MERMAID_FORMAT_HINT,
    )

    slim = _style_format_hints(
        query_text="Draw a mermaid flowchart of making a cup of coffee",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert MERMAID_FORMAT_HINT in slim
    assert COMPACT_RESPONSE_FORMAT_HINT not in slim

    rich = _style_format_hints(
        query_text="Draw a mermaid flowchart of making a cup of coffee",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=False,
    )
    assert MERMAID_FORMAT_HINT in rich


def test_callout_query_gets_blockquote_layout():
    from app.services.chat.prompt_constants import (
        CALLOUT_FORMAT_HINT,
        COMPACT_RESPONSE_FORMAT_HINT,
    )

    query = (
        "Give me 3 tips for staying focused while studying. Include a warning about all-nighters."
    )
    slim = _style_format_hints(
        query_text=query,
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert CALLOUT_FORMAT_HINT in slim
    assert COMPACT_RESPONSE_FORMAT_HINT not in slim

    rich = _style_format_hints(
        query_text=query,
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=False,
    )
    assert CALLOUT_FORMAT_HINT in rich


def test_howto_query_gets_headings_and_lists_layout():
    from app.services.chat.prompt_constants import (
        COMPACT_RESPONSE_FORMAT_HINT,
        HOWTO_FORMAT_HINT,
    )

    query = "Give me a 4-week plan to learn Spanish for travel."
    slim = _style_format_hints(
        query_text=query,
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert HOWTO_FORMAT_HINT in slim
    assert COMPACT_RESPONSE_FORMAT_HINT not in slim

    rich = _style_format_hints(
        query_text=query,
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=False,
    )
    assert HOWTO_FORMAT_HINT in rich


def test_vs_query_gets_table_then_code_card_layout():
    from app.services.chat.prompt_constants import (
        COMPACT_RESPONSE_FORMAT_HINT,
        COMPARISON_FORMAT_HINT,
    )

    rich = _style_format_hints(
        query_text="Python vs Java",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=False,
    )
    assert COMPARISON_FORMAT_HINT in rich
    assert "code cards" in COMPARISON_FORMAT_HINT

    slim = _style_format_hints(
        query_text="Compare Python vs Java for a beginner. Side by side on typing, syntax, and use cases.",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert COMPARISON_FORMAT_HINT in slim
    assert COMPACT_RESPONSE_FORMAT_HINT not in slim
    joined = "\n".join(slim)
    assert "No ## headings" not in joined


def test_integration_hints_wraps_todos_section():
    from app.core.config import Settings
    from app.services.chat.prompt_builder import _integration_hints

    parts = _integration_hints(
        settings=Settings(
            web_search_enabled=False,
            google_calendar_enabled=False,
            gmail_enabled=False,
        ),
        query_text=None,
        local_tz="UTC",
        user_locale="en",
        location_for_context=None,
        prompt_location=None,
        memory_block="",
        attachment_rag_block="",
        todos_section="User Lists\n## Groceries\n- ○ Milk (open)",
        is_day_plan=False,
        projects_block="",
        summary=None,
    )
    joined = "\n".join(parts)
    assert "[BEGIN UNTRUSTED CONTENT — reminders and lists]" in joined
    assert "○ Milk" in joined

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
    assert "```tip" not in funny
    assert "occasional emoji" not in funny
    assert "Do not add emoji" in funny


def test_balanced_style_keeps_full_math_solver_hint():
    parts = _hints("balanced")
    joined = "\n".join(parts)
    # Solve 2x+3=7 is math intent — full solver pack plus compact safety.
    assert "Math diagrams and plots" in joined
    assert SHORT_MATH_SAFETY_HINT in parts


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


def test_one_sentence_skips_chart_and_compare_layout():
    from app.services.chat.prompt_constants import (
        BREVITY_REQUEST_HINT,
        CHART_FORMAT_HINT,
        COMPACT_RESPONSE_FORMAT_HINT,
        COMPARISON_FORMAT_HINT,
        is_brevity_request,
    )

    query = "In one sentence, make a bar chart of monthly rainfall"
    assert is_brevity_request(query)
    slim = _style_format_hints(
        query_text=query,
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert CHART_FORMAT_HINT not in slim
    assert COMPARISON_FORMAT_HINT not in slim
    assert BREVITY_REQUEST_HINT in slim
    assert COMPACT_RESPONSE_FORMAT_HINT in slim

    compare = _style_format_hints(
        query_text="tea versus coffee in one sentence",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert COMPARISON_FORMAT_HINT not in compare
    assert BREVITY_REQUEST_HINT in compare


def test_sequence_diagram_uses_sequence_hint_not_flowchart():
    from app.services.chat.prompt_constants import (
        MERMAID_FORMAT_HINT,
        SEQUENCE_FORMAT_HINT,
        is_sequence_diagram_question,
    )

    query = "sequence diagram of HTTP request"
    assert is_sequence_diagram_question(query)
    parts = _style_format_hints(
        query_text=query,
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert SEQUENCE_FORMAT_HINT in parts
    assert MERMAID_FORMAT_HINT not in parts
    assert "sequenceDiagram" in SEQUENCE_FORMAT_HINT
    joined = "\n".join(parts)
    assert "This turn is a flowchart" not in joined


def test_casual_tea_vs_coffee_skips_code_card_compare():
    from app.services.chat.prompt_constants import (
        COMPACT_RESPONSE_FORMAT_HINT,
        COMPARISON_FORMAT_HINT,
        is_structured_comparison_question,
    )

    query = "tea versus coffee"
    assert is_structured_comparison_question(query) is False
    parts = _style_format_hints(
        query_text=query,
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert COMPARISON_FORMAT_HINT not in parts
    assert COMPACT_RESPONSE_FORMAT_HINT in parts


def test_bare_rainfall_chart_still_gets_chart_hint():
    from app.services.chat.prompt_constants import CHART_FORMAT_HINT

    parts = _style_format_hints(
        query_text="make a bar chart of monthly rainfall",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert CHART_FORMAT_HINT in parts
    assert "sample data" in CHART_FORMAT_HINT
    assert "ask ONE question for the values" in CHART_FORMAT_HINT


def test_bare_email_asks_purpose_instead_of_inventing_a_draft():
    from app.services.chat.prompt_constants import (
        EMAIL_ASK_PURPOSE_HINT,
        EMAIL_DRAFT_HINT,
    )

    parts = _style_format_hints(
        query_text="escribeme un correo",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert EMAIL_ASK_PURPOSE_HINT in parts
    assert EMAIL_DRAFT_HINT not in parts
    assert "escribeme un correo" in EMAIL_ASK_PURPOSE_HINT


def test_specified_email_still_drafts_now():
    from app.services.chat.prompt_constants import (
        EMAIL_ASK_PURPOSE_HINT,
        EMAIL_DRAFT_HINT,
    )

    parts = _style_format_hints(
        query_text="email my boss about PTO",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert EMAIL_DRAFT_HINT in parts
    assert EMAIL_ASK_PURPOSE_HINT not in parts


def test_flowchart_of_making_coffee_gets_mermaid_hint():
    from app.services.chat.prompt_constants import MERMAID_FORMAT_HINT

    parts = _style_format_hints(
        query_text="flowchart of making coffee",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert MERMAID_FORMAT_HINT in parts
    assert 'E["Grind beans"]' in MERMAID_FORMAT_HINT


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


def test_vs_query_gets_table_with_conditional_code_examples():
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
    assert "tagged code fences" in COMPARISON_FORMAT_HINT
    assert "materially help" in COMPARISON_FORMAT_HINT

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


def test_quote_query_gets_blockquote_layout():
    from app.services.chat.prompt_constants import (
        COMPACT_RESPONSE_FORMAT_HINT,
        QUOTE_FORMAT_HINT,
    )

    query = "Give me a famous quote by Maya Angelou about courage, with attribution."
    slim = _style_format_hints(
        query_text=query,
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert QUOTE_FORMAT_HINT in slim
    assert COMPACT_RESPONSE_FORMAT_HINT not in slim

    rich = _style_format_hints(
        query_text=query,
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=False,
    )
    assert QUOTE_FORMAT_HINT in rich


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
        todos_section="User Schedule\n### Today\n- ○ Milk at 09:00 (open, topic: Reminders)",
        is_day_plan=False,
        projects_block="",
        summary=None,
    )
    joined = "\n".join(parts)
    assert "[BEGIN UNTRUSTED CONTENT — schedule]" in joined
    assert "○ Milk" in joined


def test_integration_hints_wraps_gmail_reminders_as_third_party():
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
        todos_section="User Schedule\n### Today\n- ○ Milk at 09:00 (open, topic: Reminders)",
        gmail_todos_section="### Today\n- ○ Pay invoice at 09:00 (open, topic: Reminders)",
        is_day_plan=False,
        projects_block="",
        summary=None,
    )
    joined = "\n".join(parts)
    gmail_start = joined.index("[BEGIN UNTRUSTED CONTENT — gmail reminders]")
    gmail_chunk = joined[gmail_start : gmail_start + 500]
    assert "Pay invoice" in gmail_chunk
    assert "external sources" in gmail_chunk
    assert "user-saved notes" not in gmail_chunk


def test_explain_transformers_gets_format_contract_not_compact():
    from app.services.chat.prompt_constants import (
        COMPACT_RESPONSE_FORMAT_HINT,
        FORMAT_CONTRACT,
        MATH_SOLVER_HINT,
        VISUALIZATION_HINTS,
    )

    parts = _style_format_hints(
        query_text="explain how transformers work",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
    )
    assert FORMAT_CONTRACT in parts
    assert COMPACT_RESPONSE_FORMAT_HINT not in parts
    assert MATH_SOLVER_HINT not in parts
    assert VISUALIZATION_HINTS not in parts
    joined = "\n".join(parts)
    assert "No ## headings" not in joined


def test_top_10_tips_gets_format_contract_not_compact():
    from app.services.chat.prompt_constants import (
        COMPACT_RESPONSE_FORMAT_HINT,
        FORMAT_CONTRACT,
        MATH_SOLVER_HINT,
    )

    parts = _style_format_hints(
        query_text="give me the top 10 productivity tips",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
    )
    assert FORMAT_CONTRACT in parts
    assert COMPACT_RESPONSE_FORMAT_HINT not in parts
    assert MATH_SOLVER_HINT not in parts
    joined = "\n".join(parts)
    assert "No ## headings" not in joined


def test_pasted_fragment_still_uses_compact():
    from app.services.chat.prompt_constants import (
        COMPACT_RESPONSE_FORMAT_HINT,
        FORMAT_CONTRACT,
    )

    parts = _style_format_hints(
        query_text="Whoever made the best decision for me",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert COMPACT_RESPONSE_FORMAT_HINT in parts
    assert FORMAT_CONTRACT not in parts

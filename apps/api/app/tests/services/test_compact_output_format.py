"""Casual/slim turns must stay ChatGPT-shaped — not a funny table essay."""

from app.services.chat.prompt_builder import _style_format_hints
from app.services.chat.prompt_constants import (
    COMPACT_RESPONSE_FORMAT_HINT,
    RESPONSE_FORMAT_HINT,
    SHORT_MATH_SAFETY_HINT,
    TONE_FORMAT_GUARD,
    UNIVERSAL_FORMAT_BASELINE,
    WRITING_LINE_HINT,
    is_bare_writing_line,
)


def test_compact_turn_skips_rich_format_pack():
    parts = _style_format_hints(
        query_text="Whoever made the best decision for me",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert COMPACT_RESPONSE_FORMAT_HINT in parts
    assert RESPONSE_FORMAT_HINT not in parts
    assert SHORT_MATH_SAFETY_HINT in parts
    joined = "\n".join(parts)
    assert "Make answers visually clear" not in joined
    assert "do not invent a topic essay" in joined.lower()


def test_compact_compare_turn_uses_table_then_code_cards_not_plain_prose():
    from app.services.chat.prompt_constants import COMPARISON_FORMAT_HINT

    parts = _style_format_hints(
        query_text="Compare Python vs Java for a beginner. Side by side on typing, syntax, and use cases.",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert COMPARISON_FORMAT_HINT in parts
    assert COMPACT_RESPONSE_FORMAT_HINT not in parts
    joined = "\n".join(parts)
    assert "code cards" in joined
    assert "No ## headings" not in joined


def test_compact_chart_turn_uses_vega_fence_not_plain_prose():
    from app.services.chat.prompt_constants import CHART_FORMAT_HINT

    parts = _style_format_hints(
        query_text=(
            "Make a bar chart of average monthly rainfall in Seattle: "
            "Jan 5.7, Feb 3.5, Mar 3.7, Apr 2.4, May 1.8, Jun 1.5 inches."
        ),
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert CHART_FORMAT_HINT in parts
    assert COMPACT_RESPONSE_FORMAT_HINT not in parts
    joined = "\n".join(parts)
    assert "you CAN draw this chart" in joined
    assert "NEVER substitute a markdown table" in joined
    assert "No ## headings" not in joined


def test_compact_mermaid_turn_uses_flowchart_fence_not_plain_prose():
    from app.services.chat.prompt_constants import MERMAID_FORMAT_HINT

    parts = _style_format_hints(
        query_text=(
            "Draw a mermaid flowchart of making a cup of coffee, "
            "from grinding beans to drinking. Keep it to about 8 steps."
        ),
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert MERMAID_FORMAT_HINT in parts
    assert COMPACT_RESPONSE_FORMAT_HINT not in parts
    joined = "\n".join(parts)
    assert "joke setup" in joined
    assert "No ## headings" not in joined


def test_day_plan_still_uses_richer_format_hint():
    parts = _style_format_hints(
        query_text="plan my day",
        style="balanced",
        is_day_plan=True,
        minimal_personal_context=False,
    )
    assert RESPONSE_FORMAT_HINT in parts
    assert COMPACT_RESPONSE_FORMAT_HINT not in parts


def test_fragment_gets_writing_line_hint():
    assert is_bare_writing_line("Whoever made the best decision for me")
    assert is_bare_writing_line("Because I said so yesterday")
    assert is_bare_writing_line("correct this sentence: I goes to store")
    assert not is_bare_writing_line("What is 2+2?")
    assert not is_bare_writing_line("Tell me about mitochondria")
    assert not is_bare_writing_line("Python vs Java")

    parts = _style_format_hints(
        query_text="Whoever made the best decision for me",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert WRITING_LINE_HINT in parts


def test_universal_baseline_bans_invented_tables_and_hooks():
    assert "Never invent a pipe table" in UNIVERSAL_FORMAT_BASELINE
    assert "schedules" in UNIVERSAL_FORMAT_BASELINE
    assert "Ah, the eternal question" in UNIVERSAL_FORMAT_BASELINE
    assert "word choice only" in TONE_FORMAT_GUARD

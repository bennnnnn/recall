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

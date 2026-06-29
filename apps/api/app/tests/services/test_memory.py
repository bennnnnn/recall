from unittest.mock import AsyncMock

from app.core.config import Settings
from app.services.memory import (
    normalize_memory_text,
    section_needs_consolidation,
    sections_need_consolidation,
    select_memories_for_prompt,
)


def _memory(type_: str, text: str, confidence: float | None):
    m = AsyncMock()
    m.type = type_
    m.text = text
    m.confidence = confidence
    m.updated_at = 0
    return m


def test_normalize_memory_text_strips_trailing_period():
    assert normalize_memory_text("User's name is Bini.") == "User's name is Bini"


def test_section_needs_consolidation_detects_repetition():
    text = (
        "User's name is Binalfew. User's name is Bini. User is a software engineer. "
        "User is a developer."
    )
    assert section_needs_consolidation(text) is True


def test_section_needs_consolidation_accepts_short_summary():
    assert section_needs_consolidation("Bini is a software engineer at Hooh.") is False


def test_section_needs_consolidation_accepts_long_clean_summary():
    text = (
        "Bini prefers short answers, turn-by-turn vocabulary quizzes, and dark glass-morphism UI. "
        "He enjoys Python, clean code, and learning English grammar through practice."
    )
    assert section_needs_consolidation(text) is False


def test_sections_need_consolidation_any_section():
    assert sections_need_consolidation({"profile": "Short.", "preference": "Also short."}) is False


def test_select_memories_filters_low_confidence():
    settings = Settings(memory_min_confidence=0.5, memory_inject_limit=10)
    memories = [
        _memory("fact", "Likes Python", 0.9),
        _memory("focus", "Debugging API", 0.3),
    ]
    selected = select_memories_for_prompt(memories, settings)
    assert len(selected) == 1
    assert selected[0].text == "Likes Python"


def test_select_memories_respects_limit_and_priority():
    settings = Settings(memory_min_confidence=0.0, memory_inject_limit=2)
    memories = [
        _memory("focus", "Low priority", 1.0),
        _memory("profile", "Name is Sam", 0.7),
        _memory("preference", "Short answers", 0.6),
    ]
    selected = select_memories_for_prompt(memories, settings)
    assert len(selected) == 2
    assert selected[0].type == "profile"
    assert selected[1].type == "preference"

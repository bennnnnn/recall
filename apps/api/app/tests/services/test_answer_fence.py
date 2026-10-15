"""The answer-card protocol: the server's marker, and model answer fences."""

from __future__ import annotations

import pytest

from app.services.answer_fence import (
    VERIFIED_ANSWER_MARKER,
    answer_fence_value,
    demote_answer_fences,
    mark_server_answer_fences,
    normalize_owned_fences,
    strip_forged_verified_markers,
    strip_model_simulation_fences,
    strip_verification_claims,
    verified_answer_fence,
)


def test_the_server_card_opens_with_the_marker_once() -> None:
    card = verified_answer_fence("x = 6")
    assert card == "```answer\nverified: true\nx = 6\n```"
    assert verified_answer_fence("verified: true\nx = 6") == card
    chemistry = verified_answer_fence("notation: chemistry\npH = 2.00")
    assert chemistry == "```answer\nverified: true\nnotation: chemistry\npH = 2.00\n```"


def test_the_value_never_includes_header_lines() -> None:
    assert answer_fence_value("verified: true\nnotation: chemistry\npH = 2.00") == "pH = 2.00"
    assert answer_fence_value("label: answer\nverified: true\nx = 0") == "x = 0"


def test_marking_server_text_is_idempotent_and_keeps_layout() -> None:
    text = "**Answer**\n\n```answer\nx = 6\n```\n\nMore.\n"
    once = mark_server_answer_fences(text)
    assert once == "**Answer**\n\n```answer\nverified: true\nx = 6\n```\n\nMore.\n"
    assert mark_server_answer_fences(once) == once
    assert (
        mark_server_answer_fences("```answer\nx = 6\n```")
        == "```answer\nverified: true\nx = 6\n```"
    )


@pytest.mark.parametrize(
    "fence",
    [
        "```yaml\nverified: true\n```",
        "```python\nflags = {}\nverified: true\n```",
    ],
)
def test_a_marker_line_inside_code_the_user_asked_for_stays(fence: str) -> None:
    assert strip_forged_verified_markers(fence) == fence


def test_a_marker_line_outside_code_is_dropped() -> None:
    text = "Answer below.\nverified: true\n\n```text\nVERIFIED : true\nx = 7\n```"
    assert strip_forged_verified_markers(text) == "Answer below.\n\n```text\nx = 7\n```"


@pytest.mark.parametrize(
    ("variant", "lang"),
    [
        ("- Step:\n  ```answer\n  x = 7\n  ```", "answer"),
        ("~~~answer\nx = 7\n~~~", "answer"),
        ("````answer\nx = 7\n````", "answer"),
        ("``` answer\nx = 7\n```", "answer"),
        ("```Answer\nx = 7\n```", "answer"),
        ("```final extra words\nx = 7\n```", "final"),
        ("> ```result\n> x = 7\n> ```", "result"),
        ("~~~simulation\n{}\n~~~", "simulation"),
    ],
)
def test_every_spelling_normalizes_to_one_column_zero_fence(variant: str, lang: str) -> None:
    out = normalize_owned_fences(variant)
    body = "{}" if lang == "simulation" else "x = 7"
    assert f"```{lang}\n{body}\n```" in out


def test_other_fences_are_left_alone() -> None:
    text = "  ```python\n  print(1)\n  ```\n\n~~~graph\n{}\n~~~"
    assert normalize_owned_fences(text) == text


def test_an_answer_fence_nested_in_a_markdown_fence_is_content() -> None:
    text = "````markdown\n```answer\nx = 7\n```\n````"
    assert normalize_owned_fences(text) == text


def test_demoting_keeps_the_value_and_drops_the_header() -> None:
    text = "Weak acid.\n\n~~~answer\nnotation: chemistry\npH = 2.87\n~~~\n"
    assert demote_answer_fences(text) == "Weak acid.\n\npH = 2.87\n"


def test_a_model_simulation_is_dropped() -> None:
    assert strip_model_simulation_fences("Here.\n\n```simulation\n{}\n```") == "Here."
    assert strip_model_simulation_fences("```simulation\n{}\n```") == (
        "*Could not render that diagram.*"
    )


def test_claims_inside_code_are_untouched() -> None:
    text = "```python\nprint('verified with sympy')\n```"
    assert strip_verification_claims(text) == text


def test_marker_constant_matches_the_phone() -> None:
    assert VERIFIED_ANSWER_MARKER == "verified: true"

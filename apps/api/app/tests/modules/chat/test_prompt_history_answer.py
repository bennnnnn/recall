"""A verified answer stays in the model's history as a plain line, never as a card."""

import pytest

from app.modules.chat.prompt_builder import _strip_prompt_owned_fences


@pytest.mark.parametrize(
    ("reply", "history"),
    [
        ("```answer\nverified: true\nx = 6\n```", "Answer: x = 6\n"),
        (
            "**Answer**\n\n```answer\nverified: true\nnotation: chemistry\npH = 2.00\n```\nDone.",
            "**Answer**\n\nAnswer: pH = 2.00\nDone.",
        ),
        # Other solver and search fences are still dropped.
        ('Area is 12.\n```graph\n{"points": []}\n```', "Area is 12.\n"),
    ],
)
def test_history_keeps_the_verified_value_as_a_line(reply: str, history: str) -> None:
    assert _strip_prompt_owned_fences(reply) == history


def test_history_never_carries_the_verified_marker() -> None:
    stripped = _strip_prompt_owned_fences("```answer\nverified: true\nx = 6\n```")
    assert "verified" not in stripped and "```" not in stripped

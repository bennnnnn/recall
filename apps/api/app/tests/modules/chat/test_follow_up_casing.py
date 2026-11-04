"""Follow-up chips read as typed questions: a capital first, "I" for the speaker.

The prompt asks for "the user's own voice", and the chips came back all lowercase ("how do
i solve these?", "how do i find mass from moles?", 2026-11-02).
"""

from __future__ import annotations

import pytest

from app.modules.chat.related_questions import accepted_questions, sentence_case


@pytest.mark.parametrize(
    ("chip", "shown"),
    [
        ("how do you find mass from moles?", "How do you find mass from moles?"),
        ("why is the sky blue?", "Why is the sky blue?"),
        ("i'm stuck, what comes next?", "I'm stuck, what comes next?"),
        ("come si calcolano i numeri primi?", "Come si calcolano i numeri primi?"),
        ("как приготовить плов?", "Как приготовить плов?"),
        # A word not all lowercase keeps its case.
        ("pH of 0.1 M HCl?", "pH of 0.1 M HCl?"),
        ("iPhone or Pixel for photos?", "iPhone or Pixel for photos?"),
        # A symbol opening the chip keeps its case, which is its meaning.
        ("x + 2 = 5, how do i solve it?", "x + 2 = 5, how do i solve it?"),
        ("f(x) = 3x, what is f(2)?", "f(x) = 3x, what is f(2)?"),
        ("v = 20 m/s: how far in 3 s?", "v = 20 m/s: how far in 3 s?"),
        ("sin(x) = 0, where?", "sin(x) = 0, where?"),
        # A lone "i" stays as written: the imaginary unit, a label or the speaker.
        ("1 + i is complex?", "1 + i is complex?"),
        ("i squared is -1, right?", "i squared is -1, right?"),
        ("(i) why is this true?", "(i) why is this true?"),
        ("what does i squared equal?", "What does i squared equal?"),
        ("what is the relationship between e and i?", "What is the relationship between e and i?"),
    ],
)
def test_sentence_case(chip: str, shown: str) -> None:
    assert sentence_case(chip) == shown


def test_kept_follow_ups_are_sentence_case() -> None:
    kept = accepted_questions(
        "How many moles are in 36 g of water?",
        ["how do you find mass from moles?", "why is the molar mass of water 18 g/mol?"],
    )
    assert kept == ["How do you find mass from moles?", "Why is the molar mass of water 18 g/mol?"]

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
        ("how do i solve these?", "How do I solve these?"),
        ("how do i find mass from moles?", "How do I find mass from moles?"),
        ("i'm stuck, what comes next?", "I'm stuck, what comes next?"),
        ("what should i do if i get stuck?", "What should I do if I get stuck?"),
        ("can i use moles here?", "Can I use moles here?"),
        # The imaginary unit, a subscript, maths and code are no speaker.
        ("what is i squared?", "What is i squared?"),
        ("what if $x_i = 3$?", "What if $x_i = 3$?"),
        ("why is `i` the loop index?", "Why is `i` the loop index?"),
        # A word not all lowercase keeps its case; other languages keep their "i".
        ("pH of 0.1 M HCl?", "pH of 0.1 M HCl?"),
        ("iPhone or Pixel for photos?", "iPhone or Pixel for photos?"),
        ("come si calcolano i numeri primi?", "Come si calcolano i numeri primi?"),
        ("как приготовить плов?", "Как приготовить плов?"),
        # A symbol opening the chip keeps its case, which is its meaning.
        ("x + 2 = 5, how do i solve it?", "x + 2 = 5, how do I solve it?"),
        ("f(x) = 3x, what is f(2)?", "f(x) = 3x, what is f(2)?"),
        ("v = 20 m/s: how far in 3 s?", "v = 20 m/s: how far in 3 s?"),
        ("sin(x) = 0, where?", "sin(x) = 0, where?"),
        ("i need the next step", "I need the next step"),
        # After a joiner, "i" is the imaginary unit unless a speaker's verb follows.
        ("what is the relationship between e and i?", "What is the relationship between e and i?"),
        ("what happens when i is squared?", "What happens when i is squared?"),
        ("if i is negative, what then?", "If i is negative, what then?"),
        ("and i need the next step?", "And I need the next step?"),
        ("what if i get stuck?", "What if I get stuck?"),
    ],
)
def test_sentence_case(chip: str, shown: str) -> None:
    assert sentence_case(chip) == shown


def test_kept_follow_ups_are_sentence_case() -> None:
    kept = accepted_questions(
        "How many moles are in 36 g of water?",
        ["how do i find mass from moles?", "why is the molar mass of water 18 g/mol?"],
    )
    assert kept == ["How do I find mass from moles?", "Why is the molar mass of water 18 g/mol?"]

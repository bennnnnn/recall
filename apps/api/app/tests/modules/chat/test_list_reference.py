"""A short message with a number after a reply that listed things names an item of a list.

Live 2026-11-06: "1" and "More on 1" under a list of ways to learn Python got "That's just
the number 1 … were you testing me?"; "4" under five beginner mistakes got "Option 4 is a
small number"; "4 from ur first list" got item 5 of the newest list, invented.
"""

from __future__ import annotations

import pytest

from app.modules.chat.message_notes import message_notes
from app.modules.chat.prompt_constants.conversation import OWN_MISTAKE_HINT
from app.modules.chat.prompt_constants.list_reference import list_reference_hint

_WAYS = (
    "Here's a path:\n\n1. 📘 **Learn the basics first** - variables and loops.\n"
    "2. **Code every day** - even briefly.\n3. **Build small projects**\n"
    "4. **Read error messages** - from the bottom."
)
_MISTAKES = (
    "1. **Mixing up `=` and `==`**\n2. **Indentation**\n3. **Index 0**\n"
    "4. **Shadowing built-ins**\n5. **Mutable defaults**"
)


@pytest.mark.parametrize(
    "message, named",
    [
        (
            "1",
            ['item 1 of your latest list is "Shadowing'.replace("Shadowing", "Mixing up = and ==")],
        ),
        ("More on 1", ['item 1 of your latest list is "Mixing up = and =="']),
        ("4", ['item 4 of your latest list is "Shadowing built-ins"']),
        ("#2?", ['item 2 of your latest list is "Indentation"']),
        ("tell me more about the second one", ['item 2 of your latest list is "Indentation"']),
        ("the last one", ['item 5 of your latest list is "Mutable defaults"']),
        (
            "no i meant 4 from ur first list",
            [
                'item 4 of your latest list is "Shadowing built-ins"',
                'item 4 of the list before it is "Read error messages - from the bottom."',
            ],
        ),
    ],
)
def test_a_number_names_the_item_of_each_recent_list(message: str, named: list[str]) -> None:
    prior = [("assistant", _WAYS), ("user", "and mistakes?"), ("assistant", _MISTAKES)]
    note = list_reference_hint(message, prior) or ""
    for item in named:
        assert item in note


@pytest.mark.parametrize(
    "message",
    [
        "what is 2+2",
        "3 x 4",
        "in 2024 i tried python twice and gave up both times, any tips for staying with it",
        "thanks!",
        # Item 9 of a five-item list names nothing.
        "9",
    ],
)
def test_a_message_that_names_no_item_gets_no_note(message: str) -> None:
    assert list_reference_hint(message, [("assistant", _MISTAKES)]) is None


def test_a_reply_with_no_list_names_nothing() -> None:
    assert list_reference_hint("1", [("assistant", "Python is a language.")]) is None


def test_every_message_after_a_reply_carries_the_own_mistake_note() -> None:
    """ "I said …", "thats wrong", "u misunderstood me": no phrase list decides."""

    class _User:
        emoji_use = "some"
        locale = "en"
        custom_instructions = ""

    exchange = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello!"}]
    assert OWN_MISTAKE_HINT in message_notes("u misunderstood me", exchange, _User())
    assert OWN_MISTAKE_HINT not in message_notes("hi", [], _User())


# Live 2026-11-15: a lesson's method list, then a question offering two choices.
_LESSON = (
    "### The method\n\n1. **Find the electron count**\n2. **Fill the first shell**\n"
    "3. **Fill the second shell**\n\nWant to do the periodic table link properly (groups, "
    "periods and why they matter), or jump to a mixed exam-style set?"
)


@pytest.mark.parametrize(
    "message, choice",
    [
        ("the first one", 'choice 1 is "Want to do the periodic table link properly"'),
        ("the second one", 'choice 2 is "jump to a mixed exam-style set"'),
        ("2", 'choice 2 is "jump to a mixed exam-style set"'),
        ("first", 'choice 1 is "Want to do the periodic table link properly"'),
        ("the last one pls", 'choice 2 is "jump to a mixed exam-style set"'),
    ],
)
def test_a_pick_after_a_question_offering_choices_picks_a_choice(message, choice) -> None:
    note = list_reference_hint(message, [("assistant", _MISTAKES), ("assistant", _LESSON)]) or ""
    assert choice in note
    assert "Find the electron count" not in note and "Mixing up" not in note


@pytest.mark.parametrize(
    "ending",
    [
        # No choice: the pick is the list's.
        "Want me to explain any of these?",
        # "Which" asks for an item of the list above it.
        "Which one do you want, or should I pick?",
        # The question is not the reply's last line.
        "Want X, or Y?\n\nTake your time.",
    ],
)
def test_a_pick_after_any_other_ending_names_the_list_item(ending: str) -> None:
    note = list_reference_hint("2", [("assistant", f"{_MISTAKES}\n\n{ending}")]) or ""
    assert 'item 2 of your latest list is "Indentation"' in note
    assert "choice" not in note


def test_three_choices_keep_their_order() -> None:
    reply = "Do you want a quiz, a summary, or a worked example?"
    note = list_reference_hint("the third one", [("assistant", reply)]) or ""
    assert 'choice 3 is "a worked example"' in note

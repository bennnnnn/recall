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
    assert "never ask what the number means" in note


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

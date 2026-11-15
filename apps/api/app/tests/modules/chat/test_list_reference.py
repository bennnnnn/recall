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
    # The choice first; the list's item only as the other reading, after it.
    assert choice in note
    other = note.find("may name that item instead")
    assert other > note.index(choice)
    assert " of your latest list is " not in note[:other]


def test_a_choice_that_offers_the_lists_items_keeps_them_named() -> None:
    # Live review 2026-11-15: "2" and "tell me more about the second one" after this got the
    # study plan 3/3 when the note named only the choices; main gave item 2.
    reply = (
        "1. Books\n2. Courses\n3. Projects\n4. Videos\n5. Mentors\n\n"
        "Want me to go deeper on any of these, or suggest a study plan?"
    )
    for message in ("2", "tell me more about the second one"):
        note = list_reference_hint(message, [("assistant", reply)]) or ""
        assert 'choice 2 is "suggest a study plan"' in note
        assert 'item 2 of your latest list is "Courses"' in note


@pytest.mark.timeout(1, func_only=True)
def test_a_long_reply_with_no_mark_is_read_once() -> None:
    # CodeQL-style: the closing question was searched over the whole reply, 2 s at 32,000.
    assert list_reference_hint("2", [("assistant", "a" * 32_000 + " or b?")]) is None


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


# The owner's trivia game, 2026-11-15: "A" for England got "A is correct! … a gift from
# France"; the note names the option picked, by its words.
_TRIVIA = (
    "**B is correct!** The Lighthouse of Alexandria.\n\nNext question: **Which country gifted "
    "the Statue of Liberty to the United States?**\n\n\U0001f170️ England\n"
    "\U0001f171️ France\n\U0001f172 Spain\n\nType A, B, or C. \U0001f3af"
)


@pytest.mark.parametrize(
    "message, picked",
    [
        ("A", ['A) "England"']),
        ("b", ['B) "France"']),
        ("(c)", ['C) "Spain"']),
        ("I think C", ['C) "Spain"']),
        ("the second one", ['B) "France"']),
        ("france", ['B) "France"']),
        ("is it spain?", ['C) "Spain"']),
        ("Is it A or B?", ['A) "England" and B) "France"']),
        ("is it a or b", ['A) "England" and B) "France"']),
    ],
)
def test_a_pick_under_lettered_options_names_the_option(message: str, picked: list[str]) -> None:
    note = list_reference_hint(message, [("assistant", _TRIVIA)]) or ""
    assert 'asked "Which country gifted the Statue of Liberty to the United States?"' in note
    for named in picked:
        assert f"it picked {named}" in note


def test_the_option_words_shared_with_the_others_pick_nothing() -> None:
    reply = "Which ocean is the largest?\n\nA) Atlantic Ocean\nB) Indian Ocean\nC) Pacific Ocean"
    note = list_reference_hint("pacific", [("assistant", reply)]) or ""
    assert 'it picked C) "Pacific Ocean"' in note
    # "ocean" is every option's: it names none of them.
    assert list_reference_hint("the ocean one", [("assistant", reply)]) is None


def test_a_pick_after_a_reply_that_only_graded_names_the_question_before_it() -> None:
    prior = [("assistant", _TRIVIA), ("user", "A"), ("assistant", "A is correct! France.")]
    note = list_reference_hint("Is it A or B?", prior) or ""
    assert note.startswith("Your reply before last asked")


@pytest.mark.parametrize(
    "message, prior",
    [
        # "A" as a word.
        ("A lot of people get that one wrong", [("assistant", _TRIVIA)]),
        ("a dog just knocked my coffee over", [("assistant", _TRIVIA)]),
        # A letter that is no option.
        ("D", [("assistant", _TRIVIA)]),
        # A letter with no lettered question above it.
        ("A", [("assistant", "Python is a programming language. Want to learn more?")]),
        # A lettered outline that asks nothing.
        ("B", [("assistant", "The plan:\n\nA) Book flights\nB) Reserve a hotel\n\nAll set.")]),
    ],
)
def test_no_option_is_named_without_a_pick(message: str, prior) -> None:
    assert "it picked" not in (list_reference_hint(message, prior) or "")

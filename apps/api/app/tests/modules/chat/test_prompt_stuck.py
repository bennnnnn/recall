"""A learner stuck on a topic gets the walkthrough lesson; a person or the last reply does not."""

from __future__ import annotations

import pytest

from app.modules.turn_reading.teaching import is_walkthrough_request


@pytest.mark.parametrize(
    "text",
    [
        "I don't understand recursion",
        "I don’t understand recursion",  # the iPhone keyboard's apostrophe
        "i dont understand recursion",
        "I still don't understand pointers in C",
        "I don't get recursion",
        "I don't understand the chain rule",
        "I'm confused about recursion",
        "I’m so confused by big O notation",
        "I'm lost with derivatives",
        "I can't wrap my head around recursion",
        "recursion makes no sense to me",
        "pointers confuse me",
        "the chain rule is so confusing",
        "I don't understand the rules of cricket",
        "help me understand how recursion works",
        "help me understand what a closure is",
        "break down the French Revolution",
    ],
)
def test_stuck_on_a_topic_gets_the_lesson(text: str) -> None:
    assert is_walkthrough_request(text)


@pytest.mark.parametrize(
    "text",
    [
        # A person, a feeling or a question word is not a topic.
        "I don't understand why she left",
        "I don't understand her",
        "I don't understand what you mean",
        "I don't get it",
        "life makes no sense",
        "I'm confused about my feelings",
        # Something in the last reply: a follow-up, not a new lesson.
        "I don't understand step 3",
        "I don't understand the second example",
        "your answer makes no sense",
        "I'm confused by your reply",
        "this makes no sense",
        # Not about understanding at all.
        "I'm lost in Addis",
        "I'm stuck on the highway",
        "I'm struggling with grief",
        "I don't understand how to install docker",
        # A thing of the user's own or an event: the reply looks at it, it teaches no subject.
        "I don't understand the error",
        "I don't get the joke",
        "I don't understand the email my landlord sent",
        "I'm confused about the meeting time",
        "I can't follow the recipe",
        "the instructions make no sense, my package never arrived",
        "help me understand my lab results",
        "break down my budget",
        "walk me through your reasoning",
        "help me understand what happened",
        "help me understand the code",
        # Paperwork is steps to take, not a subject.
        "walk me through the visa requirements for Kenya",
        "walk me through the paperwork for renting an apartment",
    ],
)
def test_not_a_topic_gets_no_lesson(text: str) -> None:
    assert not is_walkthrough_request(text)

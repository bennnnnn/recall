"""A clarify card in history, and the turn that answers it."""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.chat.clarify_turn import (
    answers_card,
    card_as_line,
    card_in_reply,
    clarify_reply_hint,
)
from app.modules.chat.prompt_constants.clarify import (
    CLARIFY_PICKS_AFTER_HINT,
    CLARIFY_PICKS_FIRST_HINT,
    CLARIFY_UNANSWERED_HINT,
)
from app.modules.chat.prompt_window import PromptWindow, history_messages
from app.modules.chat.turn_prep.mode import classify_turn_mode

_QUESTION = "how can I understand integrals"
_CARD: dict[str, object] = {
    "when": "first",
    "questions": [
        {
            "id": "level",
            "label": "Studied it before",
            "question": "Have you studied integrals before?",
            "options": ["No, never", "A little", "Yes, I'm revising"],
            "multi": False,
        },
        {
            "id": "goal",
            "label": "What it's for",
            "question": "What do you need it for?",
            "options": ["An exam", "A class", "Curiosity"],
            "multi": False,
        },
    ],
}


def _reply(card: dict[str, object] = _CARD, prose: str = "Two quick questions:") -> str:
    return f"{prose}\n\n```clarify\n{json.dumps(card)}\n```"


def _prior(reply: str) -> list[tuple[str, str]]:
    return [("user", _QUESTION), ("assistant", reply)]


_PICKS = "Studied it before: No, never\nWhat it's for: An exam next week"


def test_card_in_reply_reads_the_card_a_reply_ended_on() -> None:
    card = card_in_reply(_reply())
    assert card is not None and [q.label for q in card.questions] == [
        "Studied it before",
        "What it's for",
    ]
    assert card_in_reply("No card here.") is None
    assert card_in_reply(None) is None


def test_a_card_in_history_is_one_line_of_what_it_asked() -> None:
    assert card_as_line(json.dumps(_CARD)) == (
        "Asked: Have you studied integrals before? [No, never / A little / Yes, I'm revising]; "
        "What do you need it for? [An exam / A class / Curiosity]\n"
    )
    assert card_as_line("{broken") == ""


def test_history_shows_the_model_the_line_not_the_json() -> None:
    rows = [
        SimpleNamespace(id=uuid4(), role="user", content=_QUESTION),
        SimpleNamespace(id=uuid4(), role="assistant", content=_reply()),
    ]
    window = PromptWindow(recent=rows, gap=[], exchange=rows)
    assistant = history_messages(window, math_followup=False)[1]["content"]
    assert "```clarify" not in assistant
    assert "Asked: Have you studied integrals before?" in assistant


@pytest.mark.parametrize(
    ("message", "answered"),
    [
        (_PICKS, True),
        # Labels in any case; several picks and a typed answer are one line each.
        ("studied it before: A little\nWHAT IT'S FOR: An exam, A class", True),
        ("Studied it before: I watched some videos", True),
        ("Studied it before: No, never", True),
        ("No, never", False),
        ("Studied it before:", False),
        ("Studied it before: No\nAlso, what is a limit?", False),
        ("Level: Beginner", False),
        ("", False),
    ],
)
def test_answers_card_needs_every_line_to_be_one_of_its_labels(
    message: str, answered: bool
) -> None:
    card = card_in_reply(_reply())
    assert card is not None and answers_card(message, card) is answered


@pytest.mark.parametrize(
    ("when", "message", "hint"),
    [
        ("first", _PICKS, CLARIFY_PICKS_FIRST_HINT),
        ("after", _PICKS, CLARIFY_PICKS_AFTER_HINT),
        # Skip, in any language, or anything typed instead of tapping.
        ("first", "Just answer", CLARIFY_UNANSWERED_HINT),
        ("first", "Responde sin más", CLARIFY_UNANSWERED_HINT),
        ("after", "what about double integrals?", CLARIFY_UNANSWERED_HINT),
    ],
)
def test_the_turn_after_a_card_gets_what_to_answer(when: str, message: str, hint: str) -> None:
    prior = _prior(_reply({**_CARD, "when": when}))
    assert clarify_reply_hint(message, prior) == hint


@pytest.mark.parametrize(
    "prior",
    [
        [("user", _QUESTION), ("assistant", "An integral adds up slices.")],
        # The card was two replies ago: this turn no longer answers it.
        [*_prior(_reply()), ("user", "Just answer"), ("assistant", "Here is the idea.")],
        [],
    ],
)
def test_no_hint_without_a_card_in_the_last_reply(prior: list[tuple[str, str]]) -> None:
    assert clarify_reply_hint(_PICKS, prior) is None


def test_no_hint_for_an_empty_message() -> None:
    assert clarify_reply_hint("  ", _prior(_reply())) is None


@pytest.mark.parametrize("message", ["Just answer", "ok", _PICKS])
def test_the_message_after_a_card_is_a_full_turn(message: str) -> None:
    recent = [
        SimpleNamespace(role="user", content=_QUESTION),
        SimpleNamespace(role="assistant", content=_reply()),
    ]
    mode = classify_turn_mode(recent, message)
    assert mode.lightweight is False
    assert mode.rich_context is True
    # It answers the card, so finalize lets it hold no card of its own.
    assert mode.after_card is True


def test_ok_without_a_card_is_still_small_talk() -> None:
    recent = [
        SimpleNamespace(role="user", content="thanks"),
        SimpleNamespace(role="assistant", content="Anytime!"),
    ]
    assert classify_turn_mode(recent, "ok").lightweight is True
    assert classify_turn_mode(recent, "ok").after_card is False

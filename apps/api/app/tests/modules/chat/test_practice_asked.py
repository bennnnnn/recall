"""A chat never asks its practice questions again (``chat.practice_asked``).

The owner's study chat (2026-11-14): a mock set promised "no repeats" and asked magnesium-25's
neutrons again seventeen turns later, after the window had dropped the first time; a mixed
set asked two of the first lesson's questions again; "ok continue" got the very card the
reply before had worked out in its text.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat import lesson_calls, practice_asked
from app.modules.chat.practice_asked import (
    asked_in_prompt,
    hold_new_practice,
    may_set_practice,
    practice_questions,
)
from app.modules.chat.prompt_constants.practice import practice_asked_notes
from app.modules.chat.quiz_cards import PracticeCard, practice_cards

_OPTIONS = ("12", "13", "25")


def _card(question: str, label: str = "Exercise 4", answer: int = 1, code: str = "") -> str:
    body: dict[str, object] = {"label": label, "question": question, "code": code}
    body.update(options=list(_OPTIONS), answer=answer)
    return f"```quiz\n{json.dumps(body, ensure_ascii=False)}\n```"


def _line(question: str, code: str = "") -> str:
    """A card as the listing writes it: question, code and options on one line."""
    return PracticeCard("", question, _OPTIONS, 1, code).line


_MG = "Magnesium-25 has atomic number 12. How many neutrons does it have?"
_PRINT = "What will this Python code print?"
_CL = "A chlorine atom has atomic number 17 and mass number 37. How many neutrons does it have?"
_FRESH = {
    "question": "Carbon-14 has atomic number 6. How many neutrons does it have?",
    "options": ["6", "8", "14"],
    "answer": 1,
    "explanation": "14 − 6 = 8.",
}


class _Calls:
    def __init__(self, answer: dict[str, Any] | None) -> None:
        self.answer = answer
        self.asked: list[str] = []

    async def __call__(self, **kwargs: Any) -> Any:
        self.asked.append(kwargs["messages"][0]["content"])
        return None if self.answer is None else kwargs["schema"].model_validate(self.answer)


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> _Calls:
    fake = _Calls(_FRESH)
    monkeypatch.setattr(lesson_calls, "complete_structured", fake)
    return fake


def _state(text: str, asked: tuple[str, ...]) -> Any:
    nearby = [{"role": "system", "content": note} for note in practice_asked_notes(asked)]
    return SimpleNamespace(
        settings=Settings(_env_file=None),  # type: ignore[call-arg]
        text=text,
        usage={},
        on_status=None,
        server_text=False,
        was_cancelled=False,
        ctx=SimpleNamespace(
            prompt_messages=[{"role": "system", "content": "rules"}, *nearby],
            user_message_content="haha u kinda just gave me the answer. ok continue",
        ),
    )


def test_the_listed_cards_read_back_from_the_prompt() -> None:
    lines = (_line(_MG), _line(_CL))
    [note] = practice_asked_notes(lines)
    assert practice_asked_notes(()) == []
    assert note.endswith(f"- {lines[0]}\n- {lines[1]}")
    assert lines[0] == f"{_MG} Options: 12; 13; 25"
    messages = [
        {"role": "system", "content": f"other rules\n\n{note}"},
        {"role": "user", "content": "x"},
    ]
    assert asked_in_prompt(messages) == lines
    assert asked_in_prompt([{"role": "system", "content": "rules"}]) == ()


@pytest.mark.asyncio
async def test_a_card_shown_again_gives_way_to_a_fresh_one(calls: _Calls) -> None:
    reply = f"Here it is again, with the answer hidden 🧪\n\n{_card(_MG)}"
    out = await hold_new_practice(_state(reply, (_line(_CL), _line(_MG))))
    [card] = practice_cards(out)
    assert card.question == _FRESH["question"]
    assert card.label == "Exercise 4"
    assert out.startswith("Here it is again")
    # The call is told what not to ask.
    assert _MG in calls.asked[0] and _CL in calls.asked[0]


@pytest.mark.asyncio
async def test_a_repeat_among_new_cards_goes_without_a_call(calls: _Calls) -> None:
    new = "How many electrons does a neutral calcium atom have?"
    reply = (
        f"Fresh set:\n\n{_card(_CL.upper() + '  ', 'Mixed 1')}\n\n{_card(new, 'Mixed 2')}\n\nGo!"
    )
    out = await hold_new_practice(_state(reply, (_line(_CL),)))
    assert [card.question for card in practice_cards(out)] == [new]
    assert out == f"Fresh set:\n\n{_card(new, 'Mixed 2')}\n\nGo!"
    assert calls.asked == []


@pytest.mark.parametrize(
    ("reply", "asked", "answer"),
    [
        # Nothing listed, or nothing repeated: as written, no call.
        (f"Try this.\n\n{_card(_MG)}", (), _FRESH),
        (f"Try this.\n\n{_card(_MG)}", (_line(_CL),), _FRESH),
        # A failed call keeps the card rather than leave the lesson without practice.
        (f"Again:\n\n{_card(_MG)}", (_line(_MG),), None),
        # A fresh card that is itself a repeat is no better.
        (
            f"Again:\n\n{_card(_MG)}",
            (_line(_MG),),
            {**_FRESH, "question": _MG, "options": list(_OPTIONS)},
        ),
        # The same question over new code, or with other options, is a new card.
        (f"Try:\n\n{_card(_PRINT, code='print(2)')}", (_line(_PRINT, "print(1)"),), _FRESH),
    ],
    ids=["no listing", "no repeat", "call failed", "fresh repeats", "same words, new code"],
)
@pytest.mark.asyncio
async def test_a_reply_stays_as_written(
    calls: _Calls, reply: str, asked: tuple[str, ...], answer: dict[str, Any] | None
) -> None:
    calls.answer = answer
    assert await hold_new_practice(_state(reply, asked)) == reply


def _rows(*contents: str) -> list[Any]:
    return [SimpleNamespace(role="assistant", content=content) for content in contents]


@pytest.mark.parametrize(
    ("query", "exchange", "sets"),
    [
        ("teach me moles", [], True),
        ("quiz me on isotopes", [], True),
        ("I don't understand isotopes", [], True),
        # A lesson goes on: its next card comes.
        ("next", _rows(f"### Lesson 1: Atoms\n\nText.\n\n{_card(_MG)}"), True),
        # A mock set after a chat of cards ("ya sure but not too long").
        ("ya sure", _rows(f"Try:\n\n{_card(_MG)}", "Correct! Want a mock set?"), True),
        ("what's the weather in Paris?", [], False),
        ("thanks", _rows("You're welcome."), False),
    ],
)
def test_who_may_set_practice(query: str, exchange: list[Any], sets: bool) -> None:
    assert may_set_practice(query, exchange) is sets


@pytest.mark.asyncio
async def test_the_chats_cards_are_listed_beyond_the_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replies = [f"Lesson.\n\n{_card(_CL)}", f"More.\n\n{_card(_MG)}\n\n{_card(_CL)}", "No card."]

    async def chat_replies(_chat_id: Any) -> list[str]:
        return replies

    monkeypatch.setattr(practice_asked, "_chat_replies", chat_replies)
    asked = await practice_questions(uuid4(), "quiz me again", [])
    assert asked == (_line(_CL), _line(_MG))
    assert await practice_questions(uuid4(), "what's the weather?", []) == ()


@pytest.mark.asyncio
async def test_a_failed_read_lists_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def broken(_chat_id: Any) -> list[str]:
        raise RuntimeError("database down")

    monkeypatch.setattr(practice_asked, "_chat_replies", broken)
    assert await practice_questions(uuid4(), "quiz me", []) == ()


@pytest.mark.asyncio
async def test_a_python_quiz_of_one_question_over_new_code_keeps_every_card(
    calls: _Calls,
) -> None:
    """Review, 2026-11-14: five cards asking "What will this Python code print?" over
    different code came back as two, and every later lesson's card cost a fresh model call."""
    earlier = tuple(_line(_PRINT, f"print({n})") for n in range(5))
    reply = "Five more:\n\n" + "\n\n".join(
        _card(_PRINT, f"Question {n}", code=f"print({n} * 2)") for n in range(5)
    )
    assert await hold_new_practice(_state(reply, earlier)) == reply
    # One shown again whole goes; the rest stay.
    again = f"{reply}\n\n{_card(_PRINT, 'Question 5', code='print(3)')}"
    assert await hold_new_practice(_state(again, earlier)) == reply
    assert calls.asked == []


def test_a_card_nested_past_the_parser_reads_as_no_card() -> None:
    deep = "```quiz\n" + "[" * 100_000 + "]" * 100_000 + "\n```"
    assert practice_cards(deep) == []

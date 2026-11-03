"""A lesson reply carries its title and practice card, an outline its topics and question.

The model's own words stay; the server adds only what is missing (``lesson_shape``).
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.chat import lesson_calls
from app.modules.chat.lesson_calls import LessonPractice, OutlineTopics, QuizCard
from app.modules.chat.lesson_layout import lesson_layout_of, prompt_lesson_layout
from app.modules.chat.lesson_shape import hold_lesson_shape, next_lesson_number, teaches
from app.modules.chat.prompt_constants.teaching import (
    LESSON_CONTRACT,
    TEACH_CONTRACT,
    TEACHING_HINT,
    WALKTHROUGH_HINT,
)
from app.modules.turn_reading.lesson_flow import lesson_step, lesson_topic, outline_topics
from app.services.md_fence_scan import iter_fences

_QUIZ: dict[str, Any] = {
    "question": "What will this code print?",
    "code": "def f(n):\n    if n == 0:\n        return\n    print(n)\n    f(n - 1)\nf(2)",
    "options": ["2\\n1", "1, 2", "2, 1, 0"],
    "answer": 0,
    "explanation": "It prints n, then counts down, and stops at 0.",
}
_PRACTICE: dict[str, Any] = {"topic": "Recursion", "quiz": _QUIZ}
_TOPICS = {"topics": [{"name": f"Topic {n}", "what": f"does thing {n}"} for n in range(1, 7)]}

_WALKTHROUGH_REPLY = (
    "Recursion trips up almost everyone at first, so you're in good company.\n\n"
    "Here's a tiny example:\n\n"
    "```python\ndef countdown(n):\n    if n == 0:\n        return\n    print(n)\n"
    "    countdown(n - 1)\n```\n\n"
    "Every recursive function needs a base case and a recursive case.\n\n"
    "Which part is fuzziest for you? The calling, or the stopping?"
)


class _Calls:
    """Stands in for the structured model call; records each schema asked for."""

    def __init__(self, answer: dict[str, Any] | None) -> None:
        self.answer = answer
        self.asked: list[str] = []

    async def __call__(self, **kwargs: Any) -> Any:
        schema = kwargs["schema"]
        self.asked.append(schema.__name__)
        return None if self.answer is None else schema.model_validate(self.answer)


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> _Calls:
    fake = _Calls(_PRACTICE)
    monkeypatch.setattr(lesson_calls, "complete_structured", fake)
    return fake


def _state(
    text: str,
    message: str,
    *,
    contract: str | None = LESSON_CONTRACT,
    recent: list[Any] | None = None,
    memory: str = "",
    locale: str = "en",
) -> Any:
    system = [{"role": "system", "content": f"rules\n\n{memory}"}]
    nearby = [{"role": "system", "content": f"other\n\n{contract}"}] if contract else []
    return SimpleNamespace(
        settings=Settings(_env_file=None),  # type: ignore[call-arg]
        text=text,
        usage={},
        on_status=None,
        server_text=False,
        was_cancelled=False,
        ctx=SimpleNamespace(
            prompt_messages=[*system, *nearby, {"role": "user", "content": message}],
            user_message_content=message,
            recent_messages=recent or [],
            user=SimpleNamespace(locale=locale),
        ),
    )


def _quiz(text: str) -> dict[str, Any]:
    fences = [fence for fence in iter_fences(text) if fence.lang == "quiz"]
    assert len(fences) == 1
    card: dict[str, Any] = json.loads(text[fences[0].body_start : fences[0].body_end])
    return card


@pytest.mark.asyncio
async def test_a_walkthrough_without_its_parts_gets_its_title_and_card(calls: _Calls) -> None:
    out = await hold_lesson_shape(_state(_WALKTHROUGH_REPLY, "I don't understand recursion"))

    assert lesson_step(out) == 1
    hook, title = out.split("\n\n")[:2]
    assert hook.startswith("Recursion trips up")
    assert title == "### Lesson 1: Recursion"
    # The closing "which part?" is the card now; the lesson's own words stay.
    assert "Which part is fuzziest" not in out
    assert "base case and a recursive case" in out
    assert "### Your turn\n\n```quiz\n" in out
    card = _quiz(out)
    assert card["label"] == "Exercise 1"
    assert card["options"][0] == "2, 1"  # output on several lines, one line on the card
    assert calls.asked == ["LessonPractice"]


@pytest.mark.asyncio
async def test_numbered_sections_get_the_next_number_for_the_practice(calls: _Calls) -> None:
    reply = (
        "Two Sum is a classic.\n\n### Lesson 1: Two Sum\n\n### 1. The problem\n\nFind two.\n\n"
        "### 2. Brute force\n\nCheck every pair.\n\nOnce you get this, we'll try three sum."
    )
    out = await hold_lesson_shape(_state(reply, "help me understand two sum"))

    assert out.count("### Lesson 1: Two Sum") == 1
    assert "### 3. Your turn\n\n```quiz" in out
    assert "we'll try three sum" in out


@pytest.mark.asyncio
async def test_the_lessons_own_practice_section_holds_the_card(calls: _Calls) -> None:
    reply = (
        "### Lesson 1: Pointers\n\n### 1. Addresses\n\n`&x` is where x lives.\n\n"
        "### 2. Your turn\n\nWhat does `*p` give you? Try it and tell me."
    )
    out = await hold_lesson_shape(_state(reply, "I'm confused about pointers in C"))

    assert out.endswith("```")
    assert "### 2. Your turn\n\n```quiz\n" in out
    assert "Try it and tell me" not in out
    assert out.count("Your turn") == 1


@pytest.mark.asyncio
async def test_a_whole_lesson_is_left_alone(calls: _Calls) -> None:
    reply = "Hook.\n\n### Lesson 1: Loops\n\nText.\n\n```quiz\n{}\n```"
    assert await hold_lesson_shape(_state(reply, "help me understand loops")) == reply
    assert calls.asked == []


@pytest.mark.asyncio
async def test_a_lesson_with_its_card_only_gets_its_title_without_a_call(calls: _Calls) -> None:
    reply = 'Loops repeat work.\n\nA loop body runs per item.\n\n```quiz\n{"question": "x"}\n```'
    out = await hold_lesson_shape(_state(reply, "walk me through for loops"))
    assert out.split("\n\n")[1] == "### Lesson 1: For loops"
    assert calls.asked == []


@pytest.mark.asyncio
async def test_a_walkthrough_answered_by_a_question_back_is_left_alone(calls: _Calls) -> None:
    reply = "Sure! Can you paste the message Bob sent, so I can see what he meant?"
    assert await hold_lesson_shape(_state(reply, "I don't understand Bob's message")) == reply
    assert calls.asked == []


@pytest.mark.asyncio
async def test_a_failed_call_leaves_the_reply_as_written(calls: _Calls) -> None:
    calls.answer = None
    reply = _WALKTHROUGH_REPLY
    assert await hold_lesson_shape(_state(reply, "I don't understand recursion")) == reply


@pytest.mark.asyncio
async def test_a_turn_without_the_lesson_contract_is_left_alone(calls: _Calls) -> None:
    reply = _WALKTHROUGH_REPLY
    state = _state(reply, "I don't understand recursion", contract=None)
    assert await hold_lesson_shape(state) == reply
    assert calls.asked == []


@pytest.mark.asyncio
async def test_the_lesson_number_follows_the_chats_last_lesson(calls: _Calls) -> None:
    taught = "### Lesson 2: Lists\n\nText.\n\n```quiz\n{}\n```"
    recent = [
        SimpleNamespace(role="user", content="teach me python lists"),
        SimpleNamespace(role="assistant", content=taught),
        SimpleNamespace(role="user", content="I don't understand recursion"),
    ]
    state = _state(_WALKTHROUGH_REPLY, "I don't understand recursion", recent=recent)
    out = await hold_lesson_shape(state)
    assert "### Lesson 3: Recursion" in out


def test_a_regenerated_reply_after_the_message_is_not_counted() -> None:
    recent = [
        SimpleNamespace(role="user", content="I don't understand recursion"),
        SimpleNamespace(role="assistant", content="### Lesson 1: Recursion\n\n```quiz\n{}\n```"),
    ]
    assert next_lesson_number(recent) == 1


@pytest.mark.asyncio
async def test_a_spanish_lesson_gets_spanish_words(calls: _Calls) -> None:
    reply = "La recursión parece rara al principio.\n\nUna función se llama a sí misma."
    state = _state(reply, "enséñame la recursión en python", locale="es")
    out = await hold_lesson_shape(state)
    assert "### Lección 1: La recursión en python" in out
    assert "### Tu turno" in out
    assert _quiz(out)["label"] == "Ejercicio 1"


# ── Outlines ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_outline_topics_get_bold_names(calls: _Calls) -> None:
    reply = (
        "American history is a big story.\n\n"
        "1. Colonial America - how the colonies began.\n"
        "2. 🗽 The Revolution: why they broke from Britain.\n"
        "3. **Civil War** — the war over slavery.\n"
        "4. Reconstruction\n"
        "5. The Industrial Age – railroads and cities.\n\n"
        "Where would you like to start?"
    )
    out = await hold_lesson_shape(
        _state(reply, "teach me american history", contract=TEACH_CONTRACT)
    )

    assert "1. **Colonial America** — how the colonies began." in out
    assert "2. 🗽 **The Revolution** — why they broke from Britain." in out
    assert "3. **Civil War** — the war over slavery." in out
    assert "4. **Reconstruction**" in out
    assert "5. **The Industrial Age** — railroads and cities." in out
    assert outline_topics(out) == 5
    assert out.endswith("Where would you like to start?")
    assert calls.asked == []


@pytest.mark.asyncio
async def test_an_outline_ends_on_its_question(calls: _Calls) -> None:
    items = "\n".join(f"{n}. **Topic {n}** — what it does" for n in range(1, 6))
    asked = f"Python opens a lot up.\n\n{items}\n\nNew to it?\n\nI'll start you on Lesson 1."
    out = await hold_lesson_shape(_state(asked, "teach me python", contract=TEACH_CONTRACT))
    assert out.endswith("I'll start you on Lesson 1.\n\nNew to it?")

    silent = f"Python opens a lot up.\n\n{items}"
    out = await hold_lesson_shape(_state(silent, "teach me python", contract=TEACH_CONTRACT))
    assert out.endswith(
        "Where would you like to start? Pick a number, or tell me what you already know."
    )


@pytest.mark.asyncio
async def test_a_reply_with_only_questions_gets_the_topics_above_them(calls: _Calls) -> None:
    calls.answer = _TOPICS
    reply = (
        "Python is a great pick!\n\n"
        "Are you new to programming? And what do you want to build with it?"
    )
    out = await hold_lesson_shape(_state(reply, "teach me python", contract=TEACH_CONTRACT))

    parts = out.split("\n\n")
    assert parts[0] == "Python is a great pick!"
    assert parts[1].startswith("1. **Topic 1** — does thing 1\n2. **Topic 2**")
    assert parts[2].startswith("Are you new to programming?")
    assert outline_topics(out) == 6
    assert calls.asked == ["OutlineTopics"]


@pytest.mark.asyncio
async def test_a_list_of_its_own_gets_no_second_list(calls: _Calls) -> None:
    calls.answer = _TOPICS
    items = "\n".join(
        f"{n}. Learn how step {n} of the language works in real code" for n in range(5)
    )
    reply = f"Here's the path.\n\n{items}\n\nWhere do you want to start?"
    out = await hold_lesson_shape(_state(reply, "teach me python", contract=TEACH_CONTRACT))
    assert out == reply
    assert calls.asked == []


@pytest.mark.asyncio
async def test_picking_up_where_memory_says_gets_no_list(calls: _Calls) -> None:
    calls.answer = _TOPICS
    reply = "Last time we got to dictionaries. Pick up with functions, or start over?"
    memory = "- Learning Python: reached Lesson 3, Dictionaries. Covered: Variables"
    state = _state(reply, "teach me python", contract=TEACH_CONTRACT, memory=memory)
    assert await hold_lesson_shape(state) == reply
    assert calls.asked == []


@pytest.mark.asyncio
async def test_a_teach_me_that_teaches_is_held_as_a_lesson(calls: _Calls) -> None:
    reply = (
        "Dictionaries map keys to values.\n\n```python\nages = {'ana': 30}\n```\n\nWant to try one?"
    )
    state = _state(reply, "teach me python dictionaries", contract=TEACH_CONTRACT)
    out = await hold_lesson_shape(state)
    assert "### Lesson 1: Python dictionaries" in out
    assert lesson_step(out) == 1
    assert calls.asked == ["LessonPractice"]


@pytest.mark.parametrize(
    ("reply", "lesson"),
    [
        ("### Lesson 1: Loops\n\nText.", True),
        ("Intro.\n\n```python\nprint(1)\n```", True),
        ("Intro.\n\n### 1. First idea\n\nText.", True),
        ("Intro.\n\n1. **A**\n2. **B**\n3. **C**\n\nWhere to start?", False),
        ("Python is great! New to coding?", False),
        (" ".join(["word"] * 200), True),
    ],
)
def test_what_a_teach_me_reply_is(reply: str, lesson: bool) -> None:
    assert teaches(reply) is lesson


# ── Layout, readers and the card ────────────────────────────────────────


def test_the_layout_is_read_from_the_hints_and_the_prompt() -> None:
    assert lesson_layout_of(["x", TEACHING_HINT]) == "teaching"
    assert lesson_layout_of([WALKTHROUGH_HINT]) == "walkthrough"
    assert lesson_layout_of(["x"]) is None
    messages = [{"role": "system", "content": f"a\n\n{TEACH_CONTRACT}"}]
    assert prompt_lesson_layout(messages) == "teaching"
    assert prompt_lesson_layout([{"role": "user", "content": LESSON_CONTRACT}]) is None


@pytest.mark.parametrize(
    ("message", "topic"),
    [
        ("I don't understand recursion", "Recursion"),
        ("I don’t understand recursion yet", "Recursion"),
        ("I'm confused about pointers in C", "Pointers in C"),
        ("recursion makes no sense to me", "Recursion"),
        ("help me understand two sum in python", "Two sum in python"),
        ("explain merge sort step by step", "Merge sort"),
        ("I still don't get closures at all.", "Closures"),
        ("I want to learn python from scratch", "Python"),
        ("teach me american history", "American history"),
        ("what is 2 + 2", None),
        ("I don't understand why she left", None),
    ],
)
def test_the_lesson_topic_is_the_learners_words(message: str, topic: str | None) -> None:
    assert lesson_topic(message) == topic


def test_an_outline_topic_may_lead_with_an_emoji() -> None:
    reply = "Intro.\n\n1. 🐍 **Setup** — run it\n2. **Loops** - repeat\n3. Plain — no\n"
    assert outline_topics(reply) == 2
    assert outline_topics("```\n1. **In a fence**\n```") == 0


@pytest.mark.parametrize(
    "quiz",
    [
        {**_QUIZ, "answer": 3},
        {**_QUIZ, "options": ["a", "A", "b"]},
        {**_QUIZ, "options": ["a", "b"]},
    ],
)
def test_a_card_with_no_one_right_option_is_refused(quiz: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        QuizCard.model_validate(quiz)


def test_the_call_schemas_accept_their_examples() -> None:
    assert LessonPractice.model_validate(_PRACTICE).quiz.options[0] == "2, 1"
    assert len(OutlineTopics.model_validate(_TOPICS).topics) == 6

"""A lesson reply carries its title and practice card; every teach-me is held as a lesson.

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
from app.modules.chat.lesson_calls import LessonPractice, QuizCard
from app.modules.chat.lesson_copy import _COPY
from app.modules.chat.lesson_layout import lesson_contract, lesson_layout_of, prompt_lesson_layout
from app.modules.chat.lesson_shape import (
    _is_practice_heading,
    hold_lesson_shape,
    next_lesson_number,
    teaches,
)
from app.modules.chat.prompt_constants.lesson_flow import (
    lesson_continue_hint,
    lesson_next_contract,
)
from app.modules.chat.prompt_constants.teaching import (
    LESSON_CONTRACT,
    TEACH_CONTRACT,
    TEACHING_HINT,
    WALKTHROUGH_HINT,
)
from app.modules.turn_reading.lesson_flow import lesson_step, lesson_topic
from app.services.md_fence_scan import iter_fences

_QUIZ: dict[str, Any] = {
    "question": "What will this code print?",
    "code": "def f(n):\n    if n == 0:\n        return\n    print(n)\n    f(n - 1)\nf(2)",
    "options": ["2\\n1", "1, 2", "2, 1, 0"],
    "answer": 0,
    "explanation": "It prints n, then counts down, and stops at 0.",
}
_PRACTICE: dict[str, Any] = {"topic": "Recursion", "quiz": _QUIZ}

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
            regenerate_backup=None,
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
async def test_the_practice_after_numbered_sections_has_no_number(calls: _Calls) -> None:
    """The owner's chat (2026-11-14): "### 6. Your turn" after five taught sections read as a
    sixth item of the lesson."""
    reply = (
        "Two Sum is a classic.\n\n### Lesson 1: Two Sum\n\n### 1. The problem\n\nFind two.\n\n"
        "### 2. Brute force\n\nCheck every pair.\n\nOnce you get this, we'll try three sum."
    )
    out = await hold_lesson_shape(_state(reply, "help me understand two sum"))

    assert out.count("### Lesson 1: Two Sum") == 1
    assert "\n\n### Your turn\n\n```quiz" in out
    assert "### 3." not in out
    assert "we'll try three sum" in out


@pytest.mark.asyncio
async def test_the_lessons_own_practice_section_holds_the_card(calls: _Calls) -> None:
    reply = (
        "### Lesson 1: Pointers\n\n### 1. Addresses\n\n`&x` is where x lives.\n\n"
        "### 2. Your turn\n\nWhat does `*p` give you? Try it and tell me."
    )
    out = await hold_lesson_shape(_state(reply, "I'm confused about pointers in C"))

    assert out.endswith("```")
    assert "\n\n### Your turn\n\n```quiz\n" in out
    assert "Try it and tell me" not in out
    assert out.count("Your turn") == 1


_CARD = '```quiz\n{"label": "Exercise 1", "question": "q", "options": ["a", "b"], "answer": 0}\n```'


@pytest.mark.parametrize(
    ("heading", "unnumbered"),
    [
        ("### 6. Your turn", "### Your turn"),
        ("### 11. Your turn — predict the answer", "### Your turn — predict the answer"),
        ("## 3) Your turn:", "## Your turn:"),
        ("### **4. Your turn**", "### **Your turn**"),
        ("### 2. Tu turno", "### Tu turno"),
        ("### 5. Sıra sende", "### Sıra sende"),
        # Taught sections keep their numbers; a heading that only mentions the practice too.
        ("### 6. Your turn to think about stack depth", None),
        ("### 2. How it works", None),
    ],
)
@pytest.mark.parametrize("contract", [LESSON_CONTRACT, None], ids=["lesson turn", "any turn"])
@pytest.mark.asyncio
async def test_a_lessons_practice_heading_is_never_numbered(
    calls: _Calls, heading: str, unnumbered: str | None, contract: str | None
) -> None:
    reply = f"Hook.\n\n### Lesson 2: Moles\n\n### 1. The idea\n\nA count.\n\n{heading}\n\n{_CARD}"
    out = await hold_lesson_shape(_state(reply, "next", contract=contract))
    assert out == (reply if unnumbered is None else reply.replace(heading, unnumbered))
    assert "### 1. The idea" in out
    assert calls.asked == []


@pytest.mark.asyncio
async def test_a_numbered_practice_heading_outside_a_lesson_stays(calls: _Calls) -> None:
    reply = f"Five questions to try.\n\n### 6. Your turn\n\n{_CARD}"
    assert await hold_lesson_shape(_state(reply, "quiz me", contract=None)) == reply


@pytest.mark.asyncio
async def test_the_card_replaces_only_the_practice_under_its_heading(calls: _Calls) -> None:
    reply = (
        "### Lesson 1: Recursion\n\nA function that calls itself.\n\n"
        "### Your turn\n\nWrite factorial and tell me.\n\n"
        "### Common mistakes\n\n- No base case\n- Wrong step\n\n### Next\n\nWe'll do memoising."
    )
    out = await hold_lesson_shape(_state(reply, "I don't understand recursion"))

    assert "### Your turn\n\n```quiz\n" in out
    assert "Write factorial" not in out
    assert out.endswith(
        "### Common mistakes\n\n- No base case\n- Wrong step\n\n### Next\n\nWe'll do memoising."
    )


@pytest.mark.asyncio
async def test_a_heading_that_only_mentions_your_turn_is_not_the_practice(calls: _Calls) -> None:
    reply = (
        "### Lesson 1: Recursion\n\nA function that calls itself.\n\n"
        "### Your turn to think about stack depth\n\nEach call waits for the next."
    )
    out = await hold_lesson_shape(_state(reply, "I don't understand recursion"))

    assert "Each call waits for the next." in out
    assert out.count("```quiz") == 1
    assert "\n\n### Your turn\n\n```quiz\n" in out


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


@pytest.mark.asyncio
async def test_the_lesson_number_counts_the_reply_just_before_this_turn(calls: _Calls) -> None:
    """``recent`` is read before this turn's message is saved: it ends on the last lesson."""
    recent = [
        SimpleNamespace(role="user", content="teach me python lists"),
        SimpleNamespace(
            role="assistant", content="### Lesson 1: Lists\n\nText.\n\n```quiz\n{}\n```"
        ),
    ]
    state = _state(_WALKTHROUGH_REPLY, "I don't understand recursion", recent=recent)
    assert "### Lesson 2: Recursion" in await hold_lesson_shape(state)


def test_a_regenerated_reply_is_not_counted() -> None:
    redone = SimpleNamespace(
        id="m2", role="assistant", content="### Lesson 1: Recursion\n\n```quiz\n{}\n```"
    )
    recent = [SimpleNamespace(id="m1", role="user", content="I don't understand recursion"), redone]
    assert next_lesson_number(recent, redoing="m2") == 1
    assert next_lesson_number(recent) == 2


@pytest.mark.asyncio
async def test_a_spanish_lesson_gets_spanish_words(calls: _Calls) -> None:
    reply = "La recursión parece rara al principio.\n\nUna función se llama a sí misma."
    state = _state(reply, "enséñame la recursión en python", locale="es")
    out = await hold_lesson_shape(state)
    assert "### Lección 1: La recursión en python" in out
    assert "### Tu turno" in out
    assert _quiz(out)["label"] == "Ejercicio 1"


# ── A teach-me that does not teach yet ─────────────────────────────────


@pytest.mark.asyncio
async def test_a_short_teach_me_is_held_as_a_lesson_never_an_outline(calls: _Calls) -> None:
    """Review of #2318: five plain steps once went to the outline pass, which bolded them
    and added "Where would you like to start?"."""
    steps = "\n".join(f"{n}. Step {n} of cooking rice." for n in range(1, 6))
    state = _state(steps, "teach me how to cook rice", contract=TEACH_CONTRACT)
    out = await hold_lesson_shape(state)
    assert "### Lesson 1: " in out
    assert "Where would you like to start" not in out
    assert calls.asked == ["LessonPractice"]


@pytest.mark.asyncio
async def test_a_teach_me_answered_by_a_question_back_is_left_alone(calls: _Calls) -> None:
    """Review of #2318: "teach me" with no topic, answered "What would you like to learn?",
    once got a lesson title and a practice card about nothing."""
    reply = "Happy to! What would you like to learn?"
    state = _state(reply, "teach me", contract=TEACH_CONTRACT)
    assert await hold_lesson_shape(state) == reply
    assert calls.asked == []


@pytest.mark.asyncio
async def test_picking_up_where_memory_says_gets_no_list(calls: _Calls) -> None:
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
        # A long lesson with a short numbered list in the middle still teaches.
        (
            " ".join(["Plants turn light into sugar."] * 20)
            + "\n\n1. Light reactions\n2. Calvin cycle\n3. Products\n\n"
            + " ".join(["Each stage feeds the next."] * 15),
            True,
        ),
        # A long outline, every topic described, is still an outline.
        (
            "Here is the map.\n\n"
            + "\n".join(f"{n}. **Topic {n}** — " + " ".join(["detail"] * 25) for n in range(1, 8))
            + "\n\nWhere would you like to start?",
            False,
        ),
    ],
)
def test_what_a_teach_me_reply_is(reply: str, lesson: bool) -> None:
    assert teaches(reply) is lesson


# ── Layout, readers and the card ────────────────────────────────────────


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


def test_the_layout_is_read_from_the_hints_and_the_prompt() -> None:
    assert lesson_layout_of(["x", TEACHING_HINT]) == "teaching"
    assert lesson_layout_of([WALKTHROUGH_HINT]) == "walkthrough"
    assert lesson_layout_of(["x"]) is None
    messages = [{"role": "system", "content": f"a\n\n{TEACH_CONTRACT}"}]
    assert prompt_lesson_layout(messages) == "teaching"
    assert prompt_lesson_layout([{"role": "user", "content": LESSON_CONTRACT}]) is None


def test_every_teach_me_is_a_lesson_that_starts_now() -> None:
    """ "Teach me useful English words" once got a menu of areas and a question about the
    user's level before a single word (2026-11-06)."""
    assert lesson_contract([TEACHING_HINT]) == [TEACH_CONTRACT]


# ── The turn after a lesson ────────────────────────────────────────────


def test_the_next_lessons_contract_is_read_back_from_the_prompt() -> None:
    """The owner's chat (2026-11-14): "is it 35?" after Lesson 1 came back "Yes! Want to try
    one more, or should we move on to ions?", and the chat left the lesson."""
    contract = lesson_next_contract(2)
    assert "`### Lesson 3: <topic>`" in contract and "unnumbered `### Your turn`" in contract
    assert "Never ask whether to go on" in contract
    messages = [{"role": "system", "content": f"rules\n\n{contract}"}]
    assert prompt_lesson_layout(messages) == "next"
    # The style hints never ask for it: the turn's read does (``decided_turn``).
    assert lesson_layout_of([lesson_continue_hint(2)]) is None


_NEXT_LESSON = (
    "Correct! 🎉 Moles count particles.\n\n### 🧪 Lesson 3: Moles in equations\n\n"
    "### 1. The ratio\n\nThe big numbers are mole ratios.\n\nOnce you get this, we'll do yields."
)


@pytest.mark.asyncio
async def test_the_next_lesson_gets_the_card_it_left_out(calls: _Calls) -> None:
    state = _state(_NEXT_LESSON, "ok next", contract=lesson_next_contract(2))
    out = await hold_lesson_shape(state)
    # Its own title stands, an emoji before the word Lesson and all.
    assert lesson_step(out) == 3
    assert "\n\n### Your turn\n\n```quiz\n" in out
    assert calls.asked == ["LessonPractice"]


@pytest.mark.parametrize(
    "reply",
    [
        "Correct! 🎉 2 × 6.02 × 10²³ is 1.204 × 10²⁴.",
        "### Cheat sheet\n\n### 1. Atoms\n\nProtons, neutrons, electrons.",
    ],
    ids=["graded only", "a cheat sheet asked for"],
)
@pytest.mark.asyncio
async def test_a_reply_after_a_lesson_that_is_no_lesson_stays(calls: _Calls, reply: str) -> None:
    state = _state(reply, "make me a cheat sheet", contract=lesson_next_contract(2))
    assert await hold_lesson_shape(state) == reply
    assert calls.asked == []


@pytest.mark.parametrize("locale", sorted(_COPY))
def test_lesson_copy_reads_back(locale):
    """Every app language's lesson words read back: the title the server writes is a lesson
    step, and its practice heading is the practice's (Hindi's पाठ was neither, 2026-11-20)."""
    copy = _COPY[locale]
    assert lesson_step(f"### {copy.lesson} 2: X\n\n?") == 2
    assert _is_practice_heading(f"### {copy.your_turn}")
    assert _is_practice_heading(f"### 6. {copy.your_turn}")

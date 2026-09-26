"""Teach-me turns run as a lesson, and the next turn continues it."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat.prompt_builder import _style_format_hints, build_prompt_messages
from app.services.chat.prompt_constants import (
    COMPACT_RESPONSE_FORMAT_HINT,
    HOWTO_FORMAT_HINT,
    PERSONAL_DISCLOSURE_HINT,
    SHORT_RESPONSE_FORMAT_HINT,
    TEACHING_HINT,
    TEACHING_SHORT_NOTE,
    is_lightweight_chat_turn,
    is_teaching_request,
    lesson_continue_hint,
    lesson_step,
)

STEP_ONE = (
    "We'll go one idea at a time, with a quick check after each.\n\n"
    "1. What a dictionary is\n2. Accessing values\n3. Adding and updating\n\n"
    "### Step 1/6 — What a dictionary is\n\n"
    "A dictionary stores key-value pairs.\n\n"
    "```python\ncar = {'brand': 'Toyota', 'year': 2024}\nprint(car['brand'])\n```\n\n"
    "What will this print?\n\nA. Toyota\nB. brand\nC. 2024\nD. 0\n\n"
    "Answer it, and then we'll go to Step 2: accessing values in different ways."
)


@pytest.mark.parametrize(
    "text",
    [
        "Teach me python dictionary step by step",
        "can you teach me how photosynthesis works",
        "Help me learn SQL joins",
        "I want to learn recursion",
        "I'd like to learn Spanish verbs",
        "I would like to learn how derivatives work",
        "i wanna learn react hooks",
        "tutor me in chemistry",
        "Give me a lesson on fractions",
        "a crash course in git",
        "Enséñame los diccionarios de Python",
        "apprends-moi les boucles en Python",
        "Bring mir Python bei",
        "Ich möchte Python lernen",
        "insegnami le frazioni",
        "me ensina a usar listas",
        "научи меня python",
        "bana python sözlükleri öğret",
        "ፓይተን አስተምረኝ",
        # Learning a skill, not doing a task.
        "teach me how to code in python",
        "teach me how to use python dictionaries",
        "help me learn how to play chess",
        "teach me how recursion works",
        # A later "how to" is part of the topic, not the ask.
        "Teach me python dictionaries and how to loop over them",
    ],
)
def test_teaching_request_detected(text):
    assert is_teaching_request(text)


@pytest.mark.parametrize(
    "text",
    [
        "How to install python step by step",
        "Teach me how to install Docker",
        "teach me to set up a React project",
        "What is a python dictionary?",
        "Explain photosynthesis step by step",
        "Give me a 4-week roadmap to learn Python",
        "Help me understand this error",
        "Who was my teacher last year?",
        # Procedures keep the how-to steps, whatever the verb.
        "Teach me how to bake bread step by step",
        "teach me how to change a tire",
        "teach me how to tie a knot",
        "Can you teach me to cook?",
        "I want to learn how to cook",
        "",
    ],
)
def test_teaching_request_declines(text):
    assert not is_teaching_request(text)


@pytest.mark.parametrize(
    "reply, expected",
    [
        (STEP_ONE, (1, 6)),
        ("### Step 2/6 — Accessing values\n\nWhat does it print?", (2, 6)),
        ("**Step 3 of 5 — Loops**\n\nWhich loop runs first?", (3, 5)),
        ("### Paso 2/4 — Acceder a valores\n\n¿Qué imprime?", (2, 4)),
        ("### Étape 2/6 — Accès\n\nQue affiche-t-il ?", (2, 6)),
        ("### Шаг 4/4 — Итог\n\nЧто выведет код?", (4, 4)),
        ("### Step 1/6 — A\n\ntext\n\n### Step 2/6 — B\n\nWhich one?", (2, 6)),
        # Plans and multi-part answers are not lessons.
        ("### Day 1/7 — Arrive\n\nReady for day 2?", None),
        ("### Phase 1/3 — Setup\n\nQuestions?", None),
        ("### Part 2/4\n\nMore?", None),
        # A how-to that numbers its steps asks nothing after the last one.
        ("### Step 5/5 — Tighten the nuts\n\nYou're done.", None),
        ("### 1/2 cup of sugar?", None),
        ("Step 2/6 in prose, not a heading?", None),
        ("### Step 7/6 — impossible?", None),
        ("The capital of France is Paris.", None),
        (None, None),
    ],
)
def test_lesson_step(reply, expected):
    assert lesson_step(reply) == expected


def test_lesson_continue_hint_moves_to_the_next_step():
    hint = lesson_continue_hint(2, 6)
    assert "Step 2/6" in hint and "Step 3/6" in hint
    assert "another way" in hint
    assert "unrelated to the lesson" in hint


def test_lesson_continue_hint_recaps_after_the_last_step():
    hint = lesson_continue_hint(6, 6)
    assert "last step" in hint and "recap" in hint
    assert "Step 7/6" not in hint


def _hints(text, *, style="balanced", lesson=None, compact=False):
    return _style_format_hints(
        query_text=text,
        style=style,
        is_day_plan=False,
        minimal_personal_context=False,
        compact=compact,
        lesson=lesson,
    )


def test_teach_request_gets_a_lesson_not_a_howto():
    hints = _hints("Teach me python dictionary step by step")
    assert TEACHING_HINT in hints
    assert HOWTO_FORMAT_HINT not in hints


def test_procedure_keeps_the_howto_layout():
    hints = _hints("How to install python step by step")
    assert HOWTO_FORMAT_HINT in hints
    assert TEACHING_HINT not in hints


def test_short_style_keeps_the_lesson_with_smaller_steps():
    hints = _hints("Teach me python dictionaries", style="short")
    assert TEACHING_HINT in hints and TEACHING_SHORT_NOTE in hints
    assert SHORT_RESPONSE_FORMAT_HINT not in hints


def test_brevity_request_is_not_a_lesson():
    hints = _hints("Briefly teach me python dictionaries in one sentence")
    assert TEACHING_HINT not in hints


def test_answer_to_a_lesson_step_continues_the_lesson():
    hints = _hints("A", lesson=(1, 6))
    assert lesson_continue_hint(1, 6) in hints
    assert TEACHING_HINT not in hints


@pytest.mark.parametrize("answer", ["I'm confused", "I have no idea"])
def test_confusion_mid_lesson_is_an_answer_not_a_disclosure(answer):
    hints = _hints(answer, lesson=(2, 6))
    assert lesson_continue_hint(2, 6) in hints
    assert PERSONAL_DISCLOSURE_HINT not in hints


def test_new_teach_request_starts_a_new_lesson():
    hints = _hints("Teach me python sets", lesson=(3, 6))
    assert TEACHING_HINT in hints
    assert not any("A lesson is in progress" in hint for hint in hints)


def test_short_style_lesson_step_drops_the_no_headings_rule():
    hints = _hints("B", style="short", lesson=(2, 6))
    assert lesson_continue_hint(2, 6) in hints and TEACHING_SHORT_NOTE in hints
    assert SHORT_RESPONSE_FORMAT_HINT not in hints


def test_short_reply_to_a_lesson_step_is_not_lightweight():
    # The options trail the question, so the "?" is far from the end.
    assert is_lightweight_chat_turn("ok", prior_assistant=STEP_ONE) is False
    assert is_lightweight_chat_turn("thanks", prior_assistant=STEP_ONE) is True


def _user(style="balanced"):
    user = MagicMock()
    user.name = "Bini"
    user.email = "bini@example.com"
    user.location = None
    user.response_style = style
    user.response_tone = None
    user.memory_enabled = True
    user.locale = "en"
    user.timezone = None
    user.custom_instructions = None
    return user


async def _system_prompt(recent, query):
    with (
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=None)),
        patch("app.modules.memory.get_memory_block", AsyncMock(return_value="")),
        patch("app.modules.todos.build_todos_system_section", AsyncMock(return_value="")),
        patch("app.modules.learning.load_learning_classes_for_prompt", AsyncMock(return_value="")),
        patch("app.repositories.messages.list_recent", AsyncMock(return_value=recent)),
    ):
        messages = await build_prompt_messages(
            _user(),
            uuid4(),
            Settings(attachment_rag_enabled=False),
            query_text=query,
            rich_context=False,
            current_user_message_id=recent[-1].id,
        )
    return messages[0]["content"]


@pytest.mark.asyncio
async def test_ok_after_a_lesson_step_asks_for_the_next_step():
    recent = [
        SimpleNamespace(id=uuid4(), role="user", content="Teach me python dictionary step by step"),
        SimpleNamespace(id=uuid4(), role="assistant", content=STEP_ONE),
        SimpleNamespace(id=uuid4(), role="user", content="ok"),
    ]
    system = await _system_prompt(recent, "ok")
    assert "A lesson is in progress" in system
    assert "Step 2/6" in system
    # "ok" would otherwise get the casual one-liner layout.
    assert COMPACT_RESPONSE_FORMAT_HINT not in system


@pytest.mark.asyncio
async def test_ordinary_follow_up_gets_no_lesson_hint():
    recent = [
        SimpleNamespace(id=uuid4(), role="user", content="What is the capital of France?"),
        SimpleNamespace(id=uuid4(), role="assistant", content="Paris."),
        SimpleNamespace(id=uuid4(), role="user", content="And of Spain?"),
    ]
    system = await _system_prompt(recent, "And of Spain?")
    assert "A lesson is in progress" not in system

"""One-off reminders, impossible fact pairs, and direct profile answers."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.chat.turn_prep.instant import _profile_reply
from app.modules.memory.fact_quality import FactView, is_one_off_schedule_fact, texts_to_drop
from app.modules.memory.pass_writes import writes_from_ops
from app.modules.memory.profile_reply import reply_for_profile_question
from app.modules.memory.schemas import MemoryFactOp
from app.modules.turn_reading.profile_ask import profile_question_to_answer

_NOW = datetime(2026, 10, 11, tzinfo=UTC)


def test_one_off_reminders_are_not_memory_and_routines_are():
    assert is_one_off_schedule_fact("User has a dentist appointment on Thursday at 4")
    assert is_one_off_schedule_fact("User has a weekly todo of walking at 7pm")
    assert is_one_off_schedule_fact("User has a reading task for tomorrow")
    assert is_one_off_schedule_fact("User's mom's flight lands on Thursday at 4 in the evening")
    assert not is_one_off_schedule_fact("User walks every evening at 7pm")
    assert not is_one_off_schedule_fact("User works on Monday")


def test_two_current_places_keep_the_newer_one():
    drops = texts_to_drop(
        [
            FactView("User is in Avon", _NOW - timedelta(days=2)),
            FactView("User is in Russia", _NOW),
            FactView("User is from Addis Ababa, Ethiopia", _NOW),
            FactView("User's first language is Amharic", _NOW),
            FactView("User's second language is English", _NOW),
        ]
    )
    assert drops == ["User is in Avon"]


def test_current_school_and_an_earlier_stage_keep_the_newer_one():
    drops = texts_to_drop(
        [
            FactView("User attended Debre Markos University", _NOW - timedelta(days=1)),
            FactView("User is in 12th grade", _NOW),
        ]
    )
    assert drops == ["User attended Debre Markos University"]


_FACTS = (
    "User's second language is English",
    "User's first language is Amharic",
    "User is from Addis Ababa, Ethiopia",
)


def test_second_language_is_read_from_the_profile():
    assert (
        reply_for_profile_question("My second langauge", _FACTS)
        == "Your second language is English."
    )
    assert reply_for_profile_question("What is my education level", _FACTS) == (
        "I don't have your education level saved."
    )


@pytest.mark.parametrize(
    ("facts", "location", "reply"),
    [
        # M15: a saved home is said, never "I don't have that saved".
        (("User lives in Addis Ababa",), None, "You live in Addis Ababa."),
        (("Bini is based in Nairobi, Kenya",), None, "You live in Nairobi, Kenya."),
        # Someone else's home is not the user's.
        (("User's sister lives in Nairobi suburbs",), None, "I don't have where you live saved."),
        (
            (),
            "Bole, Addis Ababa",
            "I don't have where you live saved, but your location is set to Bole, Addis Ababa.",
        ),
        ((), None, "I don't have where you live saved."),
    ],
)
def test_where_do_i_live_reads_the_saved_home(facts, location, reply):
    assert profile_question_to_answer("where do I live?", []) == "where do I live?"
    assert reply_for_profile_question("where do I live?", facts, location=location) == reply


@pytest.mark.asyncio
@pytest.mark.parametrize("memory_on", [True, False])
async def test_instant_profile_reply_follows_the_memory_switch(memory_on):
    """M14: with memory off, "where am I from?" is not answered from saved facts."""
    user = SimpleNamespace(
        id=uuid4(), memory_enabled=memory_on, location_enabled=False, location_saved_at=None
    )
    identity = SimpleNamespace(user=user, local_tz="UTC")
    rows = AsyncMock(return_value=[SimpleNamespace(text="User is from Ethiopia")])
    with (
        patch("app.modules.chat.turn_prep.instant.SessionLocal", _Session),
        patch("app.modules.memory.repository.list_for_user", rows),
    ):
        reply = await _profile_reply("where am I from?", identity)
    assert reply == ("You're from Ethiopia." if memory_on else None)


@pytest.mark.asyncio
async def test_instant_profile_reply_does_not_deny_on_a_failed_read():
    """M17: a failed read hands the turn to the model, which says memory didn't load."""
    identity = SimpleNamespace(user=SimpleNamespace(id=uuid4(), memory_enabled=True))
    with (
        patch("app.modules.chat.turn_prep.instant.SessionLocal", _Session),
        patch(
            "app.modules.memory.repository.list_for_user",
            AsyncMock(side_effect=RuntimeError("db down")),
        ),
    ):
        assert await _profile_reply("where do I live?", identity) is None


class _Session:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *_args):
        return None


def test_second_after_first_language_reads_the_other_fact():
    asked = profile_question_to_answer("Second", ["What is my first language"])
    assert asked == "what is my second language"
    assert reply_for_profile_question(asked or "", _FACTS) == "Your second language is English."


def test_you_tell_me_uses_the_earlier_language_question():
    asked = profile_question_to_answer(
        "You tell me",
        ["What is my education level", "My second langauge", "U don't know. It?"],
    )
    assert asked == "My second langauge"
    assert reply_for_profile_question(asked or "", _FACTS) == "Your second language is English."


def test_writes_skip_a_one_off_reminder():
    reminder = MemoryFactOp(
        op="add",
        type="fact",
        text="User has a dentist appointment on Thursday at 4",
        confidence=0.9,
        importance=0.5,
        topic="schedule",
    )
    home = MemoryFactOp(
        op="add",
        type="profile",
        text="User is from Addis Ababa, Ethiopia",
        confidence=0.9,
        importance=0.8,
        topic="profile",
    )
    writes, skipped = writes_from_ops(
        [reminder, home],
        chat_id=uuid4(),
        explicit_remember=False,
        include_sensitive=False,
        min_confidence=0.5,
        transcript="User: remind me about the dentist. I am from Addis Ababa.",
    )
    assert skipped == 1
    assert [write.text for write in writes] == ["User is from Addis Ababa, Ethiopia"]


def test_a_stale_fact_is_dropped_as_housekeeping_not_as_the_users_removal():
    """Its delete keeps chat history even in a pass where the user said "forget ..."."""
    from app.modules.memory.pass_writes import Asks, MemorySnapshot, compose_writes

    snapshot = MemorySnapshot(
        memory_enabled=True,
        include_sensitive=False,
        existing_facts={},
        prompt_facts=[],
        prompt_areas=[],
        active_facts=(
            FactView("User is in Avon", _NOW - timedelta(days=2)),
            FactView("User is in Russia", _NOW),
        ),
    )
    lines = "User: forget my favorite drink"

    writes, _ = compose_writes(
        snapshot, lines, Asks.of(lines), [], chat_id=uuid4(), from_history=False, min_confidence=0.5
    )

    stale = [write for write in writes if write.match_text == "User is in Avon"]
    assert [(write.op, write.stale) for write in stale] == [("delete", True)]


_LESSON_LINE = (
    'Learning Maths: reached Lesson 1, Number basics (chat "Greeting"). Covered: Number basics'
)


def _snapshot(*texts):
    from app.modules.memory.pass_writes import MemorySnapshot

    return MemorySnapshot(
        memory_enabled=True,
        include_sensitive=False,
        existing_facts={uuid4(): text for text in texts},
        prompt_facts=[{"type": "focus", "topic": "goals", "text": text} for text in texts],
        prompt_areas=[],
    )


def _compose(lines, ops, *texts):
    from app.modules.memory.pass_writes import Asks, compose_writes

    return compose_writes(
        _snapshot(*texts),
        lines,
        Asks.of(lines),
        [MemoryFactOp.model_validate(op) for op in ops],
        chat_id=uuid4(),
        from_history=False,
        min_confidence=0.5,
    )


@pytest.mark.parametrize(
    "op",
    [
        # The model rewrote the lesson job's line from a chat that taught no lesson.
        {
            "op": "update",
            "type": "focus",
            "topic": "goals",
            "text": 'Learning Maths: reached Lesson 2, Chemistry basics (chat "Chemistry"). '
            "User completed a quiz on moles and molar mass",
            "match_text": _LESSON_LINE,
            "confidence": 0.9,
        },
        {
            "op": "supersede",
            "type": "focus",
            "topic": "goals",
            "text": "User is working on solving the equation 3x^2+4/4=1",
            "match_text": _LESSON_LINE,
            "confidence": 0.9,
        },
        {
            "op": "add",
            "type": "focus",
            "topic": "goals",
            "text": "Learning Python 2: reached Lesson 1, Variables",
            "confidence": 0.9,
        },
    ],
)
def test_no_model_write_adds_or_rewrites_a_lesson_line(op):
    lines = "User: Maya and I had a fight. My chem test on moles is Friday"
    writes, skipped = _compose(lines, [op], _LESSON_LINE)
    assert not [w for w in writes if w.op in {"add", "update", "supersede"}]
    assert skipped == 1


def test_forgetting_a_lesson_line_is_the_users_to_do():
    lines = "User: forget that I'm learning maths"
    op = {"op": "delete", "type": "focus", "match_text": _LESSON_LINE, "confidence": 0.9}
    writes, _ = _compose(lines, [op], _LESSON_LINE)
    assert [(w.op, w.match_text) for w in writes] == [("delete", _LESSON_LINE)]


def test_a_lesson_line_is_never_stale_or_merged():
    from app.modules.memory.consolidation_workflow import _duplicate_pairs
    from app.modules.memory.fact_quality import is_learning_line

    assert is_learning_line(_LESSON_LINE)
    assert not is_learning_line("User is learning Python")
    assert texts_to_drop([FactView("Learning Plans: reached Lesson 1, Dentist appointments")]) == []
    other = _LESSON_LINE.replace("Greeting", "Maths")
    facts = [
        SimpleNamespace(
            id=uuid4(),
            type="focus",
            text=text,
            status="active",
            last_confirmed_at=_NOW,
            updated_at=_NOW,
        )
        for text in (_LESSON_LINE, other)
    ]
    assert _duplicate_pairs(facts) == []


def _add(text, type_="fact", topic="notes"):
    return {"op": "add", "type": type_, "topic": topic, "text": text, "confidence": 0.9}


@pytest.mark.parametrize(
    ("lines", "op"),
    [
        # 2026-11-02: three single requests saved as lasting facts.
        (
            "User: solve x^2 - 5x + 6 = 0",
            _add(
                "User is working on solving the quadratic equation x^2 - 5x + 6 = 0",
                "focus",
                "recent-work",
            ),
        ),
        (
            "User: make a bar chart of my test scores: math 85, chemistry 72, English 90, "
            "physics 78",
            _add("User scored 85 in math, 72 in chemistry, 90 in English, 78 in physics"),
        ),
        (
            "User: write a simple HTML page with a button that counts clicks",
            _add(
                "User is learning basic web development with HTML and JavaScript", "focus", "goals"
            ),
        ),
        # The class, not the case: any task that says nothing of the user.
        (
            "User: can you write me a python script that renames files",
            _add("User is learning Python scripting", "focus", "goals"),
        ),
        (
            "User: what's the capital of France?",
            _add("User is interested in France", "fact", "interests"),
        ),
        (
            "User: help me solve 2x + 3 = 7",
            _add("User is working on 2x + 3 = 7", "focus", "recent-work"),
        ),
        (
            "User: thanks\nUser: plot y = 3x + 2",
            _add("User is studying linear functions", "focus", "goals"),
        ),
        # An expression handed over bare is a task too.
        (
            "User: x^2 - 5x + 6 = 0",
            _add("User is working on x^2 - 5x + 6 = 0", "focus", "recent-work"),
        ),
        (
            "User: I'm Sami, in 10th grade\nUser: solve 2x + 3 = 7",
            _add("User is working on solving 2x + 3 = 7", "focus", "recent-work"),
        ),
    ],
)
def test_a_single_task_is_not_a_fact_about_the_user(lines, op):
    writes, skipped = _compose(lines, [op])
    assert [w.text for w in writes if w.op == "add"] == []
    assert skipped == 1


@pytest.mark.parametrize(
    ("lines", "op"),
    [
        # Durable context revealed while asking for help stays the model's call.
        (
            "User: Fix the drawer in my Expo app Recall",
            _add("User builds Recall with Expo", "project", "side-projects"),
        ),
        (
            "User: I got 85 in maths and 72 in chemistry, chart them",
            _add("User scored 85 in maths and 72 in chemistry"),
        ),
        ("User: plan a party for my 2 kids", _add("User has 2 kids", "profile", "profile")),
        (
            "User: I want to learn python, explain variables",
            _add("User is learning Python", "focus", "goals"),
        ),
        ("User: teach me python", _add("User is learning Python", "focus", "goals")),
        # An answer, not a request.
        (
            "User: Python and FastAPI",
            _add("User builds with Python and FastAPI", "fact", "tech-stack"),
        ),
        ("User: 10th grade", _add("User is in 10th grade", "profile", "profile")),
        # Versions and slashes beside words state a fact; they are not maths to do.
        (
            "User: React 18 + Expo 52",
            _add("User builds with React 18 and Expo 52", "fact", "tech-stack"),
        ),
        (
            "User: Next.js 14/Postgres 16",
            _add("User builds with Next.js 14 and Postgres 16", "fact", "tech-stack"),
        ),
        ("User: 24/7 on-call", _add("User works 24/7 on-call", "fact", "notes")),
        # How they want replies asks for no task.
        (
            "User: keep replies short from now on",
            _add("User prefers short replies", "preference", "preferences"),
        ),
        # A "remember" keeps what it names.
        (
            "User: remember my test scores: math 85, chemistry 72, English 90",
            _add("User scored 85 in math, 72 in chemistry, 90 in English"),
        ),
    ],
)
def test_facts_the_user_states_while_asking_are_kept(lines, op):
    writes, skipped = _compose(lines, [op])
    assert [w.text for w in writes if w.op == "add"] == [op["text"]]
    assert skipped == 0

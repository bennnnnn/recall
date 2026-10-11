"""One-off reminders, impossible fact pairs, and direct profile answers."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.modules.chat.prompt_constants.routing import profile_question_to_answer
from app.modules.memory.extraction_workflow import writes_from_ops
from app.modules.memory.fact_quality import FactView, is_one_off_schedule_fact, texts_to_drop
from app.modules.memory.profile_reply import reply_for_profile_question
from app.modules.memory.schemas import MemoryFactOp

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

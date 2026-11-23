"""A slot is kept only when its fact answers it, and its answer is in the user's words.

The owner's memory (2026-11-21/22) held "User earns an annual income of 200k" filed under
name, so it replaced their name; "User's name is Binne" from "Why did you write my name in
lower case"; and "User identifies as female" from "With female", picking a voice. Test
accounts held an exam, a car and a rent rise as where they live.
"""

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.memory import slots
from app.modules.memory.grounding import SourceLine, ground_fact, said_of_themselves
from app.modules.memory.pass_writes import Asks, MemorySnapshot, compose_writes
from app.modules.memory.recheck import SavedFact, _Reading, judge, verdict_values
from app.modules.memory.schemas import MEMORY_SLOTS, MemoryFactOp
from app.modules.memory.slots import answered_slot, frame_words, sensitive_slots
from app.modules.memory.writes_repository import _retire_same_slot
from app.tests.fakes import fake_session

_NOW = datetime(2026, 11, 22, tzinfo=UTC)


def test_every_slot_but_the_favourites_has_its_question():
    assert set(slots._ASKS) | {"name"} == MEMORY_SLOTS


@pytest.mark.parametrize(
    ("slot", "fact"),
    [
        ("name", "User's name is Sara"),
        ("name", "User goes by Alex"),
        ("home", "User lives in Denver"),
        ("home", "User now lives in Lyon"),
        ("home", "User is in Toronto"),
        ("home", "User is vegetarian and lives in Denver"),
        ("hometown", "User is originally from Addis Ababa"),
        ("school", "User is a third-year medical student"),
        ("school", "User is in 10th grade"),
        ("job", "User works as a nurse"),
        ("job", "User is a lawyer"),
        ("job", "User is an accountant at Deloitte"),
        ("age", "User is 34 years old"),
        ("age", "User is 34"),
        ("age", "User is a business owner in his 50s"),
        ("gender", "User identifies as female"),
        ("gender", "User is a woman"),
        ("relationship_status", "User is married with two kids"),
        ("relationship_status", "User's wife is named Hana"),
        ("religion", "User is Muslim"),
        ("favorite_color", "User's favourite colour is blue"),
    ],
)
def test_a_fact_that_answers_its_slot_keeps_it(slot, fact):
    assert answered_slot(slot, fact) == slot


@pytest.mark.parametrize(
    ("slot", "fact"),
    [
        # The owner's and test accounts' rows.
        ("name", "User earns an annual income of 200k"),
        ("name", "The user does not go by the name Priya"),
        ("name", "User has a sister named Maria who lives in Lisbon"),
        ("home", "User has an exam on Monday, Nov 25, 2026"),
        ("home", "User owns a 2014 Honda Civic (FWD) that makes a clicking noise"),
        ("home", "User's rent increased by approximately $100 per month"),
        ("home", "User's boyfriend helps fix technical issues"),
        ("relationship_status", "User's grandson is visiting on Saturday"),
        # Someone else's answer to the question.
        ("home", "User's sister lives in Lisbon"),
        ("age", "User has a 7-year-old son"),
        ("age", "User is 2 months behind on rent"),
        ("gender", "User has a female cat"),
        ("religion", "User practices English every day"),
        ("favorite_color", "User's favorite food is pizza"),
        # Not a slot at all.
        ("project", "User is building an app"),
    ],
)
def test_a_fact_that_does_not_answer_its_slot_is_kept_in_none(slot, fact):
    assert answered_slot(slot, fact) is None


def _lines(*texts: str) -> list[SourceLine]:
    return [SourceLine(text=text, message_id=uuid4()) for text in texts]


def _ground(fact: str, quote: str, line: str, slot: str | None, english: bool = True):
    return ground_fact(
        quote=quote,
        fact=fact,
        stated_as="own_life",
        lines=_lines(line),
        explicit_remember=False,
        english=english,
        slot=answered_slot(slot, fact),
    )


@pytest.mark.parametrize("slot", ["name", None])
def test_a_quote_with_the_question_and_no_answer_states_nothing(slot):
    grounding = _ground(
        "User's name is Binne", "my name", "Why did you write my name in lower case", slot
    )
    assert grounding.line is None
    assert grounding.reason == "its quote does not give the answer"


@pytest.mark.parametrize(
    ("fact", "quote", "line"),
    [
        ("User's name is Bini Smith", "my brother Smith", "my brother Smith is visiting"),
        ("User's name is Bini Smith", "Smith", "Smith"),
    ],
)
def test_a_name_only_partly_said_names_no_one(fact, quote, line):
    """Every word of one name the fact gives is in the quote (review, #2539)."""
    assert _ground(fact, quote, line, "name").line is None


@pytest.mark.parametrize(
    ("fact", "quote", "line", "slot"),
    [
        ("User's name is Sara", "My name is Sara", "My name is Sara, by the way", "name"),
        ("User goes by Alex", "Call me Alex", "Call me Alex from now on", "name"),
        ("User's name is Biniam", "Biniam", "Biniam", "name"),
        ("User's name is Bini Smith", "I'm Bini Smith", "hey, I'm Bini Smith", "name"),
        ("User's name is Bini; also goes by Bee", "call me Bee", "just call me Bee", "name"),
        ("User's name is Sara", "ስሜ ሳራ ነው", "ስሜ ሳራ ነው", "name"),
        ("User lives in Toronto", "Toronto", "Toronto", "home"),
        ("User is in 10th grade", "grade 10", "I'm in grade 10 this year", "school"),
        ("User works as a nurse", "i work as a nurse", "also i work as a nurse lol", "job"),
        ("User is a student", "I'm a student", "I'm a student", "school"),
        ("User's favorite colour is blue", "blue", "my fav colour? blue", "favorite_colour"),
    ],
)
def test_a_quote_that_gives_the_answer_holds_its_fact(fact, quote, line, slot):
    assert _ground(fact, quote, line, slot).line is not None


def test_another_persons_name_is_held_by_its_quote_and_names_no_one():
    grounding = _ground(
        "User's friend is named Daniel",
        "My friend's name is Daniel",
        "My friend's name is Daniel",
        None,
    )
    assert grounding.line is not None
    assert not frame_words("User's friend is named Daniel", None)


@pytest.mark.parametrize("slot", ["gender", None])
def test_a_picked_option_is_no_gender(slot):
    grounding = _ground("User identifies as female", "With female", "With female", slot)
    assert grounding.line is None
    assert grounding.reason == "not said by the user about themselves"


@pytest.mark.parametrize(
    ("fact", "quote", "line", "slot"),
    [
        (
            "User is a woman",
            "I'm a 29-year-old woman",
            "I'm a 29-year-old woman, heart rate?",
            "gender",
        ),
        ("User is 34 years old", "34", "I'm 34", "age"),
        ("User is Muslim", "I'm Muslim", "I'm Muslim, so no pork recipes please", "religion"),
        ("User is married", "married", "im married with two kids", "relationship_status"),
        (
            "User's wife is named Hana",
            "wife's name is Hana",
            "Remember my wife's name is Hana",
            None,
        ),
        # Another language: the model's reading stands.
        ("User is a woman", "Je suis une femme", "Je suis une femme", "gender"),
    ],
)
def test_a_sensitive_answer_said_about_themselves_is_kept(fact, quote, line, slot):
    english = not line.startswith("Je ")
    assert _ground(fact, quote, line, slot, english=english).line is not None


def test_a_bare_age_answers_with_no_first_person_are_not_kept():
    assert _ground("User is 34 years old", "34", "34", "age").line is None
    assert sensitive_slots("User has a 7-year-old son", None) == frozenset()
    assert said_of_themselves("ስሜ ሳራ ነው")


def _snapshot(*facts: dict[str, str], include_sensitive: bool = True) -> MemorySnapshot:
    return MemorySnapshot(
        memory_enabled=True,
        include_sensitive=include_sensitive,
        existing_facts={uuid4(): fact["text"] for fact in facts},
        prompt_facts=list(facts),
        prompt_areas=[],
    )


def _compose(said: list[str], ops: list[dict], *existing: dict[str, str], history=False):
    lines = "\n".join(f"User: {text}" for text in said)
    writes, _ = compose_writes(
        _snapshot(*existing),
        lines,
        Asks.of(lines),
        [
            MemoryFactOp.model_validate(
                {"op": "add", "confidence": 0.9, "stated_as": "own_life", **op}
            )
            for op in ops
        ],
        chat_id=uuid4(),
        from_history=history,
        min_confidence=0.5,
        sources=_lines(*said),
    )
    return writes


_NAME = {"type": "profile", "topic": "profile", "text": "User's name is Bini", "slot": "name"}


def test_an_income_filed_under_name_is_saved_in_no_slot():
    writes = _compose(
        ["0 debt, 200k a year"],
        [{"text": "User earns an annual income of 200k", "quote": "200k a year", "slot": "name"}],
        _NAME,
    )
    assert [(w.text, w.slot) for w in writes] == [("User earns an annual income of 200k", None)]


def test_the_owners_name_and_gender_rows_are_not_written():
    writes = _compose(
        ["Why did you write my name in lower case", "With female"],
        [
            {"text": "User's name is Binne", "quote": "my name", "slot": "name"},
            {"text": "User identifies as female", "quote": "With female", "slot": "gender"},
        ],
    )
    assert writes == []


def test_a_wrong_slot_saved_earlier_holds_no_question_for_an_earlier_chat():
    """The history scan only fills gaps: an income filed under name is no name."""
    income = {"type": "fact", "topic": "notes", "text": "User earns 200k a year", "slot": "name"}
    op = {"text": "User's name is Bini", "quote": "my name is Bini", "slot": "name"}
    writes = _compose(["hi, my name is Bini"], [op], income, history=True)
    assert [(w.text, w.slot) for w in writes] == [("User's name is Bini", "name")]
    assert _compose(["hi, my name is Bini"], [op], _NAME, history=True) == []


def _fact(text: str, slot: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(), text=text, slot=slot, status="active", superseded_at=None, superseded_by_id=None
    )


def test_a_fact_filed_in_a_slot_it_does_not_answer_neither_replaces_nor_is_replaced():
    name = _fact("User's name is Bini", "name")
    income = _fact("User earns an annual income of 200k", "name")
    _retire_same_slot([name, income], income)
    assert name.status == "active"
    _retire_same_slot([name, income], name)
    assert income.status == "active"
    newer = _fact("User goes by Bee", "name")
    _retire_same_slot([name, income, newer], newer)
    assert (name.status, income.status) == ("superseded", "active")


def _saved(text: str, slot: str | None = None) -> SavedFact:
    return SavedFact(
        id=uuid4(),
        text=text,
        created_at=_NOW,
        confirmed_at=_NOW,
        source_chat_id=uuid4(),
        slot=slot,
    )


def test_recheck_mutes_the_owners_name_and_gender_rows_and_clears_the_income_slot():
    lines = _lines("Why did you write my name in lower case", "With female", "0 debt, 200k a year")

    def read(fact: SavedFact, quote: str, slot: str | None):
        reading = _Reading(fact=1, quote=quote, stated_as="own_life", slot=slot)
        return judge(fact, reading, story=False, lines=lines, english=True)

    name = read(_saved("User's name is Binne", "name"), "my name", "name")
    gender = read(_saved("User identifies as female", "gender"), "With female", "gender")
    income_fact = _saved("User earns an annual income of 200k", "name")
    income = read(income_fact, "200k a year", "name")
    assert (name.keep, gender.keep, income.keep) == (False, False, True)
    assert income.slot is None
    assert verdict_values(income) == {
        "source_message_id": lines[2].message_id,
        "slot": None,
    }
    assert verdict_values(name) == {"status": "muted"}


def test_recheck_keeps_a_saved_slot_the_reading_left_out():
    lines = _lines("I live in Denver")
    fact = _saved("User lives in Denver", "home")
    verdict = judge(
        fact,
        _Reading(fact=1, quote="I live in Denver", stated_as="own_life"),
        story=False,
        lines=lines,
        english=True,
    )
    assert verdict.slot == "home"
    assert verdict_values(verdict) == {"source_message_id": lines[0].message_id}


@pytest.mark.asyncio
async def test_the_extraction_prompt_shows_only_a_slot_its_fact_answers():
    from app.modules.memory.extraction_workflow import load_memory_snapshot

    rows = [
        SimpleNamespace(
            id=uuid4(), type="fact", topic="notes", text=text, last_confirmed_at=None, slot=slot
        )
        for text, slot in (
            ("User earns an annual income of 200k", "name"),
            ("User lives in Denver", "home"),
        )
    ]
    with (
        patch(
            "app.modules.memory.extraction_workflow.users_repo.get_by_id",
            AsyncMock(return_value=MagicMock(memory_enabled=True)),
        ),
        patch(
            "app.modules.memory.extraction_workflow.memories_repo.list_for_user",
            AsyncMock(return_value=rows),
        ),
    ):
        snapshot = await load_memory_snapshot(fake_session(), uuid4())
    assert [fact.get("slot") for fact in snapshot.prompt_facts] == [None, "home"]


def test_a_fact_that_names_the_user_is_held_by_the_name_itself():
    """Live eval: "User's name is Bini; User is a 29-year-old woman" from "I'm a 29-year-old
    woman" shares the age with its quote and names the user from saved memory."""
    fact = "User's name is Bini; User is a 29-year-old woman"
    line = "I'm a 29-year-old woman, what's a healthy resting heart rate for me?"
    assert _ground(fact, "I'm a 29-year-old woman", line, "name").line is None


def test_a_quote_that_says_more_than_the_question_keeps_the_models_expansion():
    """Review: "I live in NYC" says more than "live"; the model's expansion stands."""
    fact = "User lives in New York City"
    assert _ground(fact, "I live in NYC", "I live in NYC", "home").line is not None
    assert _ground(fact, "I live", "I live", "home").line is None


def test_remember_stands_for_the_first_person_on_its_line():
    grounding = ground_fact(
        quote="married, two kids",
        fact="User is married with two kids",
        stated_as="own_life",
        lines=_lines("Please remember: married, two kids"),
        explicit_remember=True,
        slot="relationship_status",
    )
    assert grounding.line is not None


def test_a_new_nickname_beside_the_saved_name_is_held_by_the_nickname():
    """Live eval: "call me Bee" on an account whose memory names them Bini."""
    fact = "User's name is Bini; also goes by Bee."
    line = "Just call me Bee from now on"
    assert _ground(fact, line, line, "name").line is not None


@pytest.mark.parametrize(
    ("fact", "said", "asked", "kept"),
    [
        ("User is 34 years old", "34", "Happy to tailor it. How old are you?", True),
        ("User is married", "married", "Are you married, or single?", True),
        ("User is Muslim", "Muslim", "What religion do you follow, if any?", True),
        (
            "User identifies as female",
            "With female",
            "Would you like a male or a female voice?",
            False,
        ),
        ("User is 34 years old", "34", "How many slices should I plan for?", False),
        # A long line is no short answer: it must speak in the first person.
        (
            "User is 34 years old",
            "34 but that is not the point here really",
            "How old are you?",
            False,
        ),
    ],
)
def test_a_short_answer_to_their_own_question_is_said_about_themselves(fact, said, asked, kept):
    """Review: a bare "34" to "How old are you?" was saved before the first-person check."""
    grounding = ground_fact(
        quote=said,
        fact=fact,
        stated_as="own_life",
        lines=[SourceLine(text=said, message_id=uuid4(), asked=asked)],
        explicit_remember=False,
    )
    assert (grounding.line is not None) is kept


def test_a_pass_reads_the_question_its_first_line_answers():
    lines = "User: 34"
    writes, _ = compose_writes(
        _snapshot(),
        lines,
        Asks.of(lines),
        [
            MemoryFactOp.model_validate(
                {
                    "op": "add",
                    "confidence": 0.9,
                    "stated_as": "own_life",
                    "slot": "age",
                    "text": "User is 34 years old",
                    "quote": "34",
                }
            )
        ],
        chat_id=uuid4(),
        from_history=False,
        min_confidence=0.5,
        sources=_lines("34"),
        earlier="User: plan my week\nAssistant: Happy to tailor it. How old are you?",
    )
    assert [(w.text, w.slot) for w in writes] == [("User is 34 years old", "age")]


def test_a_lagging_pass_reads_its_second_line_with_the_question_before_it():
    """A pass that reads "Hi" and "34" together keeps the question asked between them
    (``extract_backlog`` fills each line's ``asked``), so the bare answer stands (#2539)."""
    lines = "User: Hi\nUser: 34"
    op = MemoryFactOp.model_validate(
        {"op": "add", "confidence": 0.9, "stated_as": "own_life", "slot": "age",
         "text": "User is 34 years old", "quote": "34"}
    )  # fmt: skip
    hi, answer = _lines("Hi", "34")
    for asked, kept in (("Hi! How old are you?", True), ("", False)):
        writes, _ = compose_writes(
            _snapshot(), lines, Asks.of(lines), [op], chat_id=uuid4(), from_history=False,
            min_confidence=0.5, sources=[hi, replace(answer, asked=asked)], earlier="",
        )  # fmt: skip
        assert [(w.text, w.slot) for w in writes] == (
            [("User is 34 years old", "age")] if kept else []
        )


def _update(slot: str | None, text: str, new_slot: str | None) -> str | None:
    from typing import Any, cast

    from app.modules.memory.writes_repository import _apply_update

    fact = SimpleNamespace(text="old", topic="profile", slot=slot)
    write = SimpleNamespace(
        topic="profile", type="profile", confidence=0.9, sensitivity="normal", importance=3,
        source_chat_id=None, source_message_id=None, slot=new_slot,
    )  # fmt: skip
    _apply_update(cast(Any, fact), cast(Any, write), text)
    return fact.slot


def test_a_reworded_fact_keeps_only_a_slot_its_new_text_answers() -> None:
    """A slot filed before the check ("User earns 180k" under name) is cleared once the
    fact is reworded; one the new text answers stays (review, #2539)."""
    assert _update("name", "User earns 200k a year", None) is None
    assert _update("name", "User's name is Bini", None) == "name"
    assert _update(None, "User lives in Toronto", "home") == "home"


def test_an_assistant_message_over_several_lines_still_asks_its_question() -> None:
    """The earlier chat is one line per message, so the reply's closing question is the
    last ``Assistant:`` line's end, however many lines the reply had (review, #2539)."""
    from app.modules.memory.extract_backlog import format_context
    from app.modules.memory.pass_writes import answering

    earlier = format_context([("assistant", "Happy to tailor it.\n\nHow old are you?")])
    (line,) = answering(_lines("34"), earlier)
    assert line.asked.endswith("How old are you?")


@pytest.mark.parametrize(
    ("fact", "slot"),
    [
        ("User is a computer science major", "school"),
        ("User is a 10th grader", "school"),
        ("User is a high schooler", "school"),
        ("User is a nurse who works at Denver Health", "job"),
    ],
)
def test_common_ways_to_say_a_school_or_job_keep_their_slot(fact, slot) -> None:
    """Phrasings the memory model writes (review, #2539)."""
    assert answered_slot(slot, fact) == slot


def test_the_repository_keeps_only_a_slot_the_text_answers() -> None:
    """A write built outside the pass (an instruction, a stated fact) is held too."""
    assert _update(None, "User earns 200k a year", "name") is None


@pytest.mark.parametrize(
    ("fact", "slot"),
    [
        ("User is a nurse", "job"),
        ("User is an accountant at Deloitte", "job"),
        ("User is a nurse and is 30", "job"),
        ("User is a director of engineering at Stripe", "job"),
        ("User is a senior software engineer at Google.", "job"),
        ("User is a junior developer", "job"),
        ("User is a senior at NYU", "school"),
        ("User is a high school senior", "school"),
        ("User's wife is named Hana", "relationship_status"),
        ("The user's partner is Sam", "relationship_status"),
    ],
)
def test_a_job_named_outright_keeps_its_slot(fact, slot) -> None:
    assert answered_slot(slot, fact) == slot


@pytest.mark.parametrize(
    ("fact", "slot"),
    [
        # A noun tied to something else names no job (Claude and Gemini review, #2539).
        ("User is a fan of jazz", "job"),
        ("User is a big fan of jazz", "job"),
        ("User is a member of the choir", "job"),
        ("User is a mother of two", "job"),
        ("User is an expert on wine", "job"),
        ("User is a mentor to new hires", "job"),
        # A noun another question claims.
        ("User is a student at MIT", "job"),
        ("User is a teenager", "job"),
        ("User is a woman", "job"),
        ("User is a Christian", "job"),
        ("User is a widow", "job"),
        ("User is a 30-year-old nurse", "job"),
        ("User is a junior developer", "school"),
        # A partner word answers only of the user's own partner.
        ("User is friendly and wife of the manager", "relationship_status"),
        ("User's brother's wife is a doctor", "relationship_status"),
    ],
)
def test_a_noun_that_names_no_job_is_kept_in_none(fact, slot) -> None:
    assert answered_slot(slot, fact) is None

"""Every learned fact stands on the user's own words about their own life.

The owner's memory held "User is a lawyer" (from "Lawer", a typo in a question), "User is
male (7M)", a 97-year-old wife from a provocative story and a study of Kerr black holes
from one pasted problem (2026-11-20). The model quotes and labels; these checks are the
server's.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.memory.extract_backlog import _fallback_lines, format_context, source_lines
from app.modules.memory.grounding import (
    SourceLine,
    ground_fact,
    grounded_source,
    quote_holds_fact,
    quoted_line,
)
from app.modules.memory.pass_writes import (
    Asks,
    MemorySnapshot,
    compose_writes,
    told_as_story,
)
from app.modules.memory.recheck import SavedFact, Verdict, _Reading, judge, without_older_answers
from app.modules.memory.schemas import MemoryFactOp, MemoryFactUpdateResult, memory_slot
from app.modules.memory.writes_repository import _retire_same_slot

_NOW = datetime(2026, 11, 20, tzinfo=UTC)


def _lines(*texts: str) -> list[SourceLine]:
    return [SourceLine(text=text, message_id=uuid4()) for text in texts]


@pytest.mark.parametrize(
    ("quote", "line"),
    [
        ("I work as a nurse", "Hi! I work as a nurse at St. Mary's"),
        ("i'M A NURSE", "I’m a nurse"),
        ("my wife ... is Hana", "Remember my wife's name is Hana"),
    ],
)
def test_a_quote_is_found_in_the_line_it_was_copied_from(quote, line):
    lines = _lines("What's the weather?", line)
    assert quoted_line(quote, lines) is lines[1]


@pytest.mark.parametrize("quote", ["", None, "I am a lawyer", "my wife ... is Sara"])
def test_a_quote_no_line_holds_grounds_nothing(quote):
    assert quoted_line(quote, _lines("Remember my wife's name is Hana")) is None


@pytest.mark.parametrize(
    ("quote", "fact", "holds"),
    [
        # A typo and its correction share no word with the job they were read as.
        ("Lawer", "User is a lawyer", False),
        ("Lawer", "User's profession is lawyer", False),
        # The model's parenthetical is not the claim.
        ("7M", "User is male (7M)", False),
        ("7Th grade physics questions", "User is male (7M)", False),
        ("SWE at Uber", "User works as a software engineer at Uber", True),
        ("I'm 34", "User is 34 years old", True),
        ("I live in Lyon", "User lives in Lyon now", True),
        ("I live near the lake", "User lives by a lake", True),
        ("I'm a software engineer", "User works in software engineering", True),
        # Another script cannot be compared: the model's translation stands.
        ("ቦሌ አዲስ አበባ ነኝ", "User lives in Addis Ababa", True),
    ],
)
def test_the_quote_must_say_what_the_fact_says(quote, fact, holds):
    assert quote_holds_fact(quote, fact) is holds


def test_a_latin_quote_in_another_language_is_compared_only_for_an_english_app():
    quote, fact = "Soy profesora de historia", "User is a history teacher"
    assert quote_holds_fact("Soy abogada", "User is a lawyer", english=False)
    assert not quote_holds_fact("Soy abogada", "User is a lawyer", english=True)
    assert quote_holds_fact(quote, fact, english=True)
    # A one-word fragment is compared whatever the app's language.
    assert not quote_holds_fact("Lawer", "User is a lawyer", english=False)


@pytest.mark.parametrize("said_as", ["story", "question", "request", "someone_else", None])
def test_only_their_own_life_is_kept(said_as):
    lines = _lines("We got married and it was lit")
    grounding = ground_fact(
        quote="We got married",
        fact="User is married",
        stated_as=said_as,
        lines=lines,
        explicit_remember=False,
    )
    assert grounding.line is None
    assert grounding.reason.startswith("said as")


def test_asking_to_remember_keeps_it_however_it_was_labelled():
    lines = _lines("Remember that my favorite color is green")
    source = grounded_source(
        quote="my favorite color is green",
        fact="User's favorite color is green",
        stated_as="request",
        lines=lines,
        explicit_remember=True,
    )
    assert source is lines[0]


def test_op_fields_are_read_leniently():
    op = MemoryFactOp.model_validate(
        {
            "op": "add",
            "text": "User lives in Lyon",
            "confidence": 0.9,
            "quote": "  I moved to Lyon ",
            "stated_as": "Own Life",
            "slot": "Home",
        }
    )
    assert (op.quote, op.stated_as, op.slot) == ("I moved to Lyon", "own_life", "home")
    odd = MemoryFactOp.model_validate(
        {"op": "add", "text": "x", "confidence": 0.9, "stated_as": "maybe", "slot": "project"}
    )
    assert (odd.stated_as, odd.slot) == (None, None)


@pytest.mark.parametrize(
    ("raw", "slot"),
    [
        ("job", "job"),
        ("Relationship status", "relationship_status"),
        ("favorite color", "favorite_color"),
        ("favorite_", None),
        ("project", None),
        ("interests", None),
        ("", None),
        (None, None),
    ],
)
def test_slots_are_a_closed_set(raw, slot):
    assert memory_slot(raw) == slot


def _snapshot(*facts: dict[str, str]) -> MemorySnapshot:
    return MemorySnapshot(
        memory_enabled=True,
        include_sensitive=True,
        existing_facts={uuid4(): fact["text"] for fact in facts},
        prompt_facts=list(facts),
        prompt_areas=[],
    )


def _compose(said: list[str], ops: list[dict], *existing: dict[str, str], history=False):
    sources = _lines(*said)
    lines = "\n".join(f"User: {text}" for text in said)
    writes, _ = compose_writes(
        _snapshot(*existing),
        lines,
        Asks.of(lines),
        [MemoryFactOp.model_validate({"confidence": 0.9, **op}) for op in ops],
        chat_id=uuid4(),
        from_history=history,
        min_confidence=0.5,
        sources=sources,
    )
    return writes, sources


def test_a_grounded_fact_points_at_its_message_and_keeps_its_slot():
    writes, sources = _compose(
        ["What's good in Lyon?", "I moved to Lyon last month"],
        [
            {
                "op": "add",
                "type": "profile",
                "topic": "profile",
                "text": "User lives in Lyon",
                "quote": "I moved to Lyon",
                "stated_as": "own_life",
                "slot": "home",
            }
        ],
    )
    assert [(w.text, w.source_message_id, w.slot) for w in writes] == [
        ("User lives in Lyon", sources[1].message_id, "home")
    ]


@pytest.mark.parametrize(
    "op",
    [
        # Made up: no line says it.
        {"text": "User is a lawyer", "quote": "I'm a lawyer", "stated_as": "own_life"},
        # A typo read as a job.
        {"text": "User is a lawyer", "quote": "Lawer", "stated_as": "own_life"},
        # A question's topic.
        {"text": "User is studying relativity", "quote": "Lawer", "stated_as": "request"},
        # No quote at all.
        {"text": "User is a lawyer", "stated_as": "own_life"},
    ],
)
def test_an_ungrounded_fact_is_not_written(op):
    writes, _ = _compose(["What layer?", "Lawer"], [{"op": "add", "type": "profile", **op}])
    assert writes == []


def test_a_name_the_user_gave_in_answer_is_kept_without_my_name_is():
    writes, _ = _compose(
        ["Biniam"],
        [
            {
                "op": "add",
                "type": "profile",
                "text": "User's name is Biniam",
                "quote": "Biniam",
                "stated_as": "own_life",
                "slot": "name",
            }
        ],
    )
    assert [w.text for w in writes] == ["User's name is Biniam"]


def test_a_chat_judged_a_story_keeps_none_of_its_facts():
    result = MemoryFactUpdateResult.model_validate(
        {
            "conversation": "story",
            "ops": [
                {
                    "op": "add",
                    "text": "User got married",
                    "quote": "We got married",
                    "stated_as": "own_life",
                    "confidence": 1.0,
                },
                {"op": "delete", "match_text": "User is single", "confidence": 1.0},
            ],
        }
    )
    ops = told_as_story(result)
    assert [(op.op, op.stated_as) for op in ops] == [("add", "story"), ("delete", None)]
    real = told_as_story(result.model_copy(update={"conversation": "real_life"}))
    assert real[0].stated_as == "own_life"


def test_an_earlier_chat_does_not_answer_a_question_a_saved_fact_answers():
    op = {
        "op": "add",
        "type": "profile",
        "text": "User lives in Paris",
        "quote": "I live in Paris",
        "stated_as": "own_life",
        "slot": "home",
    }
    held = {"type": "profile", "topic": "profile", "text": "User lives in Lyon", "slot": "home"}
    writes, _ = _compose(["I live in Paris"], [op], held, history=True)
    assert writes == []
    writes, _ = _compose(["I live in Paris"], [op], history=True)
    assert [w.text for w in writes] == ["User lives in Paris"]


def _fact(text: str, slot: str | None, status: str = "active") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        text=text,
        slot=slot,
        status=status,
        superseded_at=None,
        superseded_by_id=None,
    )


def test_a_new_answer_retires_every_other_active_fact_in_its_slot():
    old_home = _fact("User lives in Paris", "home")
    older_home = _fact("User lives in Avon", "home")
    muted_home = _fact("User lives in Rome", "home", status="muted")
    job = _fact("User works at Uber", "job")
    hobby = _fact("User plays guitar", None)
    new_home = _fact("User lives in Lyon", "home")
    facts = [old_home, older_home, muted_home, job, hobby, new_home]

    _retire_same_slot(facts, new_home)

    assert [fact.status for fact in facts] == [
        "superseded",
        "superseded",
        "muted",
        "active",
        "active",
        "active",
    ]
    assert old_home.superseded_by_id == new_home.id


def test_the_chat_before_the_lines_is_context_with_its_last_reply_kept_longest():
    reply = "word " * 200 + "Which grade level should the problem be?"
    text = format_context(
        [("user", "Give me a hard problem"), ("assistant", reply), ("system", "ignored")]
    )
    assert text.startswith("User: Give me a hard problem\nAssistant: ")
    assert text.endswith("Which grade level should the problem be?")
    assert "system" not in text.casefold()


def test_source_lines_keep_each_message_and_drop_a_bare_when():
    first, second = uuid4(), uuid4()
    lines = source_lines([(first, "I moved to Lyon"), (second, "6pm")])
    assert lines == (SourceLine("I moved to Lyon", first),)


def test_the_fallback_transcript_is_held_to_its_user_lines():
    read = _fallback_lines("User: I moved to Lyon\nlast month\nAssistant: Nice!\nWhere?")
    assert [line.text for line in read.sources] == ["I moved to Lyon", "last month"]
    assert read.cursor is None
    unlabelled = _fallback_lines("My favorite color is blue.")
    assert [line.text for line in unlabelled.sources] == ["My favorite color is blue."]


def _saved(text: str, minutes: int = 0) -> SavedFact:
    when = _NOW + timedelta(minutes=minutes)
    return SavedFact(
        id=uuid4(), text=text, created_at=when, confirmed_at=when, source_chat_id=uuid4()
    )


def test_recheck_keeps_a_fact_the_users_words_state_and_mutes_one_they_do_not():
    lines = _lines("What layer?", "Lawer", "I live in Addis Ababa")
    lawyer = judge(
        _saved("User is a lawyer"),
        _Reading(fact=1, quote="Lawer", stated_as="own_life"),
        story=False,
        lines=lines,
        english=True,
    )
    home = judge(
        _saved("User lives in Addis Ababa"),
        _Reading(fact=2, quote="I live in Addis Ababa", stated_as="own_life", slot="home"),
        story=False,
        lines=lines,
        english=True,
    )
    unquoted = judge(_saved("User is 21"), _Reading(fact=3), story=False, lines=lines, english=True)
    # A fact the model's answer skipped is left as it is, not muted.
    skipped = judge(_saved("User is 21"), None, story=False, lines=lines, english=True)
    assert (lawyer.keep, home.keep, unquoted.keep, skipped.keep) == (False, True, False, True)
    assert (home.source_message_id, home.slot) == (lines[2].message_id, "home")


def test_recheck_mutes_a_fact_from_a_chat_read_as_a_story():
    lines = _lines("We have four boys now and a house")
    verdict = judge(
        _saved("User has four boys"),
        _Reading(fact=1, quote="We have four boys now", stated_as="own_life"),
        story=True,
        lines=lines,
        english=True,
    )
    assert not verdict.keep


def test_recheck_keeps_only_the_newest_answer_in_a_slot():
    old, new = _saved("User is in 7th grade", 0), _saved("User is in 8th grade", 5)
    hobby = _saved("User plays chess", 1)
    verdicts = without_older_answers(
        [
            Verdict(old, keep=True, reason="stated", slot="school"),
            Verdict(new, keep=True, reason="stated", slot="school"),
            Verdict(hobby, keep=True, reason="stated"),
        ]
    )
    assert [(v.fact.text, v.keep) for v in verdicts] == [
        ("User is in 7th grade", False),
        ("User is in 8th grade", True),
        ("User plays chess", True),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mock", "new_wins", "called"),
    [(False, True, True), (False, False, True), (True, True, False)],
)
async def test_a_fact_said_again_is_retired_after_its_vector_is_written(mock, new_wins, called):
    """Only rows this pass wrote are compared; mock vectors are all alike and compare nothing."""
    from unittest.mock import AsyncMock

    from app.modules.memory.apply import _retire_said_again

    settings = SimpleNamespace(
        mock_llm_enabled=mock,
        openrouter_api_key="" if mock else "key",
        memory_near_duplicate_similarity=0.88,
    )
    memories = SimpleNamespace(retire_near_duplicates=AsyncMock(return_value=1))
    fresh, backfilled = uuid4(), uuid4()
    written = [(fresh, "a", [0.1], "h"), (backfilled, "b", [0.2], "h")]

    await _retire_said_again(
        settings,
        object(),
        memories,
        uuid4(),
        written,
        {fresh},
        new_wins,
    )

    if not called:
        memories.retire_near_duplicates.assert_not_awaited()
        return
    call = memories.retire_near_duplicates.await_args
    assert call.args[2] == [fresh]
    assert call.kwargs == {"min_similarity": 0.88, "new_wins": new_wins}


def test_a_name_from_a_pasted_word_problem_is_not_the_users():
    problem = (
        "Abel and Zehara want to sit at the two ends of a see-saw. Zehara is 37 kg, and Abel "
        "is 29 kg. What mass should Abel carry to balance it?"
    )
    op = {
        "op": "add",
        "type": "profile",
        "text": "User's name is Abel",
        "quote": "Abel",
        "stated_as": "own_life",
        "slot": "name",
    }
    writes, _ = _compose([problem], [op])
    assert writes == []


def test_recheck_keeps_a_fact_only_when_every_read_keeps_it():
    from app.modules.memory.recheck import both_keep

    fact = _saved("User is creating a book")
    kept = Verdict(fact, keep=True, reason="stated")
    muted = Verdict(fact, keep=False, reason="said as question")
    assert both_keep([kept, kept]) is kept
    assert both_keep([kept, muted]) is muted
    assert both_keep([muted, kept]) is muted


def test_remember_on_one_line_keeps_only_the_fact_quoted_from_it():
    said = ["Remember that you are my wife in this game", "We have four boys and a house"]
    ops = [
        {
            "op": "add",
            "type": "fact",
            "text": "User has four boys",
            "quote": "We have four boys",
            "stated_as": "story",
        },
        {
            "op": "add",
            "type": "fact",
            "text": "User plays a game where the assistant is his wife",
            "quote": "you are my wife in this game",
            "stated_as": "story",
        },
    ]
    writes, _ = _compose(said, ops)
    assert [w.text for w in writes] == ["User plays a game where the assistant is his wife"]


def test_a_chat_judged_a_story_keeps_no_fact_the_server_reads_itself():
    said = ["I'm building a castle for my 97 year old wife"]
    lines = f"User: {said[0]}"
    writes, _ = compose_writes(
        _snapshot(),
        lines,
        Asks.of(lines),
        [],
        chat_id=uuid4(),
        from_history=False,
        min_confidence=0.5,
        sources=_lines(*said),
        told_story=True,
    )
    assert writes == []
    real, _ = compose_writes(
        _snapshot(),
        lines,
        Asks.of(lines),
        [],
        chat_id=uuid4(),
        from_history=False,
        min_confidence=0.5,
        sources=_lines(*said),
    )
    assert [w.text for w in real] == ["User is building a castle for my 97 year old wife"]


def test_recheck_leaves_a_fact_the_user_edited_by_hand():
    from app.modules.memory.recheck import edited_by_hand

    fact = _saved("User is a paralegal")
    assert edited_by_hand(fact, fact.confirmed_at + timedelta(seconds=1))
    assert not edited_by_hand(fact, fact.confirmed_at + timedelta(minutes=5))
    assert not edited_by_hand(fact, None)

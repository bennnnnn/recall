"""A reminder request a model read from the chat, held to the user's words and timed by the
server (``todos.read_check``), and the one rule for an hour said with no am or pm
(``todos.bare_hour``).

The eight transcripts of the live QA round (2026-11-22) are here as the reading a model
gives for them: each comes to one card at 5 PM tomorrow, or one question, and never to a
second "When should I remind you?".
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.modules.todos.bare_hour import settle_hour
from app.modules.todos.model_read import ReminderReading, chat_lines
from app.modules.todos.read_check import (
    ASK_TASK,
    ASK_WHEN,
    PASSED,
    check_reading,
    grounded,
)
from app.modules.todos.spoken_add import SpokenAdd, due_for_add

ZONE = "America/Los_Angeles"
# Sunday 22 November 2026, 10:00 in Los Angeles.
NOW = datetime(2026, 11, 22, 10, 0, tzinfo=ZoneInfo(ZONE))


def _due(add: SpokenAdd) -> str:
    due = due_for_add(add, user_timezone=ZONE, now=NOW)
    assert due is not None
    return due.strftime("%a %Y-%m-%d %H:%M")


def _read(**fields: object) -> ReminderReading:
    return ReminderReading.model_validate({"request": "add", **fields})


@pytest.mark.parametrize(
    ("hour", "day", "settled"),
    [
        (5, "tomorrow", ("tomorrow", 17)),
        (1, "tomorrow", ("tomorrow", 13)),
        (12, "tomorrow", ("tomorrow", 12)),
        (7, "tomorrow", ("tomorrow", 7)),
        (6, "tomorrow", ("tomorrow", 18)),
        (11, "tomorrow", ("tomorrow", 11)),
        # Said at 10 AM: today's 8 AM passed, so 8 PM.
        (8, "today", ("today", 20)),
        (11, "today", ("today", 11)),
        # No day: the next one.
        (7, None, ("today", 19)),
        (9, None, ("today", 21)),
        (3, None, ("today", 15)),
    ],
)
def test_an_hour_with_no_half_is_settled_by_one_rule(hour, day, settled) -> None:
    assert settle_hour(hour, 0, day, NOW) == settled


def test_a_repeat_keeps_the_morning_whatever_the_time_now() -> None:
    """ "Every day at 8", said at 10 AM, is 8 AM from tomorrow, not 8 PM."""
    assert settle_hour(8, 0, None, NOW, repeats=True) == ("tomorrow", 8)


@pytest.mark.parametrize("hour", [0, 13, 24])
def test_an_hour_off_the_twelve_hour_clock_is_not_settled(hour: int) -> None:
    assert settle_hour(hour, 0, "tomorrow", NOW) is None


# The eight transcripts: (earlier user lines, last line, the reading a model gives).
_TRANSCRIPTS = [
    (
        ["hey can u remind me to move my car tmrw at 5"],
        "pm, after my 4pm lab. street sweeping is in the morning so i think i need it moved by "
        "like 5:30 but 5 is fine lol",
        {"task": "move my car", "task_quote": "move my car", "day": "tmrw",
         "day_quote": "tmrw", "time": "5", "time_quote": "5 is fine", "half": "pm",
         "half_quote": "pm"},
    ),
    (
        [],
        "Could you remind me tmrw at 5 to call my sister Margaret about the quilting group",
        {"task": "call my sister Margaret about the quilting group",
         "task_quote": "call my sister Margaret about the quilting group", "day": "tmrw",
         "day_quote": "tmrw", "time": "5", "time_quote": "at 5"},
    ),
    (
        ["can u remind me to take my migraine med tmrw at 5? thx"],
        "ugh sorry, i said tmrw at 5 lol. 5pm. can u just do that",
        {"task": "take my migraine med", "task_quote": "take my migraine med", "day": "tmrw",
         "day_quote": "tmrw", "time": "5pm", "time_quote": "5pm"},
    ),
    (
        ["hey can u remind me abt my moms bday dinner tmrw at 5"],
        "tmrw at 5 lol. the dinner is at 5 so remind me like an hour before? or just at 5 is fine",
        {"task": "moms bday dinner", "task_quote": "my moms bday dinner", "day": "tmrw",
         "day_quote": "tmrw at 5", "time": "5", "time_quote": "at 5", "before_minutes": 60,
         "before_quote": "like an hour before"},
    ),
    (
        ["hey can u remind me to grab an umbrella tmrw at 5?"],
        "tmrw at 5 lol",
        {"task": "grab an umbrella", "task_quote": "grab an umbrella", "day": "tmrw",
         "day_quote": "tmrw", "time": "5", "time_quote": "at 5"},
    ),
    (
        [],
        "remind me abt something tmrw at 5, i had the weirdest dream about my grandma's "
        "basement and i want to write it down",
        {"task": "write down my dream about my grandma's basement",
         "task_quote": "dream about my grandma's basement", "day": "tmrw", "day_quote": "tmrw",
         "time": "5", "time_quote": "at 5"},
    ),
    (
        ["hi can u remind me about the meeting w my boss tmrw at 5"],
        "the reminder is for tmrw at 5pm",
        {"task": "the meeting w my boss", "task_quote": "the meeting w my boss",
         "day": "tmrw", "day_quote": "tmrw at 5pm", "time": "5pm", "time_quote": "5pm"},
    ),
    (
        [],
        "remind me abt my bio test tmrw at 5?",
        {"task": "my bio test", "task_quote": "my bio test", "day": "tmrw", "day_quote": "tmrw",
         "time": "5", "time_quote": "at 5"},
    ),
]  # fmt: skip


@pytest.mark.parametrize(("earlier", "last", "fields"), _TRANSCRIPTS)
def test_each_transcript_comes_to_one_card_tomorrow_afternoon(earlier, last, fields) -> None:
    checked = check_reading(
        _read(**fields), [*earlier, last], user_timezone=ZONE, now=NOW, asked_before=bool(earlier)
    )
    assert checked is not None and checked.ask is None
    (add,) = checked.adds
    expected = "16:00" if fields.get("before_minutes") else "17:00"
    assert _due(add) == f"Mon 2026-11-23 {expected}"


@pytest.mark.parametrize(
    ("line", "fields", "due"),
    [
        (
            "remind me to stretch in 2 hours",
            {"task": "stretch", "task_quote": "stretch", "in_minutes": 120,
             "in_quote": "in 2 hours"},
            "Sun 2026-11-22 12:00",
        ),
        (
            "yo remind me 2 text dani back in like 20 mins",
            {"task": "text dani back", "task_quote": "text dani back", "in_minutes": 20,
             "in_quote": "in like 20 mins"},
            "Sun 2026-11-22 10:20",
        ),
        (
            "remind me an hour before my dinner at 7 tonight",
            {"task": "dinner", "task_quote": "my dinner", "day": "tonight",
             "day_quote": "tonight", "time": "7", "time_quote": "at 7", "before_minutes": 60,
             "before_quote": "an hour before"},
            "Sun 2026-11-22 18:00",
        ),
        (
            "pls remind me tmrw morning to call the landlord",
            {"task": "call the landlord", "task_quote": "call the landlord", "day": "tmrw",
             "day_quote": "tmrw morning", "time": "morning", "time_quote": "morning"},
            "Mon 2026-11-23 09:00",
        ),
        (
            "remind me to take the chicken out of the freezer tonight",
            {"task": "take the chicken out of the freezer",
             "task_quote": "take the chicken out of the freezer", "day": "tonight",
             "day_quote": "tonight"},
            "Sun 2026-11-22 20:00",
        ),
        (
            "remind me to feed the cat at 7",
            {"task": "feed the cat", "task_quote": "feed the cat", "time": "7",
             "time_quote": "at 7"},
            "Sun 2026-11-22 19:00",
        ),
        (
            "set a reminder for me to take my meds at 9 every night",
            {"task": "take my meds", "task_quote": "take my meds", "time": "9",
             "time_quote": "at 9", "repeat": "daily", "repeat_quote": "every night"},
            "Sun 2026-11-22 21:00",
        ),
        (
            "remind me about my dentist appointment on the 3rd of december at 2:15pm",
            {"task": "dentist appointment", "task_quote": "my dentist appointment",
             "day": "the 3rd of december", "date": "2026-12-03",
             "day_quote": "the 3rd of december", "time": "2:15pm", "time_quote": "at 2:15pm"},
            "Thu 2026-12-03 14:15",
        ),
        (
            # The user's words say the half: "dinner" makes 7 the evening.
            "remind me tmrw at 7 to start dinner",
            {"task": "start dinner", "task_quote": "start dinner", "day": "tmrw",
             "day_quote": "tmrw", "time": "7", "time_quote": "at 7", "half": "pm",
             "half_quote": "start dinner"},
            "Mon 2026-11-23 19:00",
        ),
    ],
)  # fmt: skip
def test_the_server_times_each_reading_from_the_users_words(line, fields, due) -> None:
    checked = check_reading(_read(**fields), [line], user_timezone=ZONE, now=NOW)
    assert checked is not None and checked.ask is None
    (add,) = checked.adds
    assert _due(add) == due


def test_a_repeat_is_kept_from_the_users_words() -> None:
    checked = check_reading(
        _read(task="take my vitamins", task_quote="take my vitamins", time="8",
              time_quote="at 8", repeat="daily", repeat_quote="every day"),
        ["remind me to take my vitamins every day at 8"],
        user_timezone=ZONE,
        now=NOW,
    )  # fmt: skip
    assert checked is not None
    (add,) = checked.adds
    assert add.repeat == "daily"
    assert _due(add) == "Mon 2026-11-23 08:00"


def test_a_value_the_user_never_said_is_not_taken() -> None:
    """The model's 5pm is a reply's, not the user's: no clock, so one question."""
    checked = check_reading(
        _read(task="call grandma", task_quote="call grandma", time="5pm", time_quote="5pm"),
        ["remind me to call grandma"],
        user_timezone=ZONE,
        now=NOW,
    )
    assert checked is not None and checked.ask == ASK_WHEN and not checked.adds


def test_a_task_nobody_named_is_not_a_card() -> None:
    checked = check_reading(
        _read(task="buy concert tickets", task_quote="tmrw at 5", day="tmrw", day_quote="tmrw"),
        ["remind me tmrw at 5"],
        user_timezone=ZONE,
        now=NOW,
    )
    assert checked is not None and checked.ask == ASK_TASK


def test_a_task_that_is_only_a_pronoun_asks_what() -> None:
    checked = check_reading(
        _read(task="write it down", task_quote="write it down", day="tmrw", day_quote="tmrw"),
        ["remind me tmrw at 5, i want to write it down"],
        user_timezone=ZONE,
        now=NOW,
    )
    assert checked is not None and checked.ask == ASK_TASK


def test_a_question_already_asked_is_never_asked_again() -> None:
    """ "idk whenever" after "When should I remind you?": tomorrow at 9 AM, on the card."""
    reading = _read(task="call mom", task_quote="call mom")
    asked = check_reading(
        reading, ["remind me to call mom", "idk whenever"], user_timezone=ZONE, now=NOW,
        asked_before=True,
    )  # fmt: skip
    assert asked is not None and asked.ask is None
    assert _due(asked.adds[0]) == "Mon 2026-11-23 09:00"
    missing = check_reading(
        _read(task="", task_quote=""), ["remind me tomorrow at 5", "hmm"], user_timezone=ZONE,
        now=NOW, asked_before=True,
    )  # fmt: skip
    assert missing is None


def test_a_time_that_passed_is_asked_again() -> None:
    checked = check_reading(
        _read(task="call mom", task_quote="call mom", day="today", day_quote="today",
              time="8am", time_quote="at 8am"),
        ["remind me to call mom today at 8am"],
        user_timezone=ZONE,
        now=NOW,
    )  # fmt: skip
    assert checked is not None and checked.ask == PASSED


def test_a_when_from_an_older_line_does_not_overrule_the_latest() -> None:
    """ "make it 7 instead" after "at 6pm": a reading that quoted the 6pm is not taken."""
    checked = check_reading(
        _read(task="call mom", task_quote="call mom", time="6pm", time_quote="at 6pm"),
        ["remind me to call mom at 6pm", "make it 7 instead"],
        user_timezone=ZONE,
        now=NOW,
    )
    assert checked is None


@pytest.mark.parametrize("request_kind", ["none"])
def test_no_request_is_no_card(request_kind: str) -> None:
    reading = ReminderReading.model_validate({"request": request_kind, "task": "x"})
    assert check_reading(reading, ["that reminds me of my dad"], user_timezone=ZONE) is None
    assert check_reading(None, ["hi"], user_timezone=ZONE) is None


def test_a_quote_is_the_users_own_words() -> None:
    assert grounded("TMRW at 5", ["hey can u remind me tmrw at 5?"])
    assert grounded("grandma's", ["my grandma’s basement"])
    assert not grounded("5pm", ["remind me to call mom"])
    assert not grounded("", ["anything"])


def test_an_odd_field_leaves_the_rest_of_the_reading() -> None:
    reading = ReminderReading.model_validate(
        {"request": "ADD", "half": "evening", "repeat": "yearly", "in_minutes": "soon",
         "task": None}
    )  # fmt: skip
    assert reading.request == "add" and reading.half == "" and reading.repeat == ""
    assert reading.in_minutes is None and reading.task == ""


def test_the_read_sees_a_card_as_the_apps_line_never_its_json() -> None:
    card = (
        '```reminder_proposal\n{"proposal_id": "p", "items": [{"action": "add", "title": '
        '"Call mom", "due_at": "2026-11-23T02:00:00Z", "when": "Sunday, Nov 22, 6:00 PM"}]}\n```'
    )
    lines = chat_lines([("user", "remind me to call mom at 6pm"), ("assistant", card)], "make it 7")
    assert "proposal_id" not in lines
    assert "Card offered, not tapped" in lines and "User (last): make it 7" in lines


def test_an_older_when_the_latest_line_says_again_is_taken() -> None:
    checked = check_reading(
        _read(task="move my car", task_quote="move my car", day="tmrw", day_quote="tmrw",
              time="5", time_quote="tmrw at 5", half="pm", half_quote="pm"),
        ["hey can u remind me to move my car tmrw at 5", "pm, after my lab. 5 is fine lol"],
        user_timezone=ZONE,
        now=NOW,
    )  # fmt: skip
    assert checked is not None and _due(checked.adds[0]) == "Mon 2026-11-23 17:00"


def test_the_clock_comes_from_the_clocks_words_not_the_days() -> None:
    """A reading of "make it 7 instead" that quoted the old card's "at 6pm" as its day."""
    checked = check_reading(
        _read(task="call mom", task_quote="call mom", day="today", day_quote="at 6pm",
              date="2026-11-22", time="7", time_quote="7"),
        ["remind me to call mom at 6pm", "make it 7 instead"],
        user_timezone=ZONE,
        now=NOW,
    )  # fmt: skip
    assert checked is not None and _due(checked.adds[0]) == "Sun 2026-11-22 19:00"


def test_tonight_settles_a_bare_hour_said_apart_from_it() -> None:
    checked = check_reading(
        _read(task="water the plants", task_quote="water the plants", day="tonight",
              day_quote="tonight", time="8", time_quote="at 8"),
        ["don't let me forget to water the plants tonight at 8"],
        user_timezone=ZONE,
        now=NOW,
    )  # fmt: skip
    assert checked is not None and _due(checked.adds[0]) == "Sun 2026-11-22 20:00"

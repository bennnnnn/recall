"""A reply never says a to-do was kept when nothing was saved; a bare hour asks only am or pm.

Live 2026-11-06: "put buy groceries on my todo list" streamed "Sure, adding **buy
groceries**" with a fence that had no time, and after "When should I remind you?", "no time,
just put it on the list" got "Added to your list: **buy groceries**". Nothing was saved:
chat keeps no undated list. "remind me to call mom tomorrow at 6" got "When should I remind
you?", losing the day, and the card that followed was titled "call mom at 6".
"""

from __future__ import annotations

import json
import re
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.conversation import chats_repository as chats_repo
from app.modules.todos.offer_reply import follows_reminder_card
from app.modules.todos.reminder_fences import materialize_reminder_fences
from app.modules.todos.reply_check import KEEP_AS_REMINDER, NEED_A_TIME, reply_when_nothing_saved
from app.modules.todos.spoken_add import parse_spoken_add, which_half_question
from app.modules.todos.spoken_when import half_of_day, is_only_a_when
from app.repositories import users as users_repo

_ASKED = "When should I remind you?"
_CARD = re.compile(r"```reminder_proposal\n(.*?)\n```", re.DOTALL)


@pytest.mark.parametrize(
    ("reply", "user_text"),
    [
        ("Sure, adding **buy groceries** to your list now.", "put buy groceries on my todo list"),
        ("Done! It's on your list.", "put buy groceries on my todo list"),
        ("Sure!", "also add buy groceries to my list"),
        ("Added: milk", "add milk to the shopping list"),
        ("Sure thing, I'll add that now. It'll go on your list with no reminder set.", "add eggs"),
    ],
)
def test_an_add_with_no_time_says_it_needs_one(reply: str, user_text: str) -> None:
    assert reply_when_nothing_saved(reply, user_text, about_reminders=True) == KEEP_AS_REMINDER


@pytest.mark.parametrize(
    "user_text",
    [
        "no time, just put it on the list",
        "whenever, just add it",
        "I don't need a reminder, just add it",
        "anytime is fine",
    ],
)
def test_an_answer_with_no_time_gets_no_claim(user_text: str) -> None:
    claim = "Added to your list: **buy groceries**, with no reminder time set."
    kept = reply_when_nothing_saved(claim, user_text, about_reminders=True, prior_assistant=_ASKED)
    assert kept == KEEP_AS_REMINDER


def test_a_denial_after_the_models_own_question_is_replaced() -> None:
    # Live 2026-11-06: after "When should I set 'Buy groceries' for?", the answer "no time"
    # got "I can't add it to a list from here, since I don't have access to your to-do app".
    reply = "I can't add it to a list from here, since I don't have access to your to-do app."
    kept = reply_when_nothing_saved(
        reply,
        "no time, just put it on the list",
        about_reminders=True,
        prior_assistant='I need a time first. When should I set "Buy groceries" for?',
        prior_user="also add buy groceries to my list",
    )
    assert kept == KEEP_AS_REMINDER


@pytest.mark.parametrize(
    "reply",
    [
        "Got it, I'll keep **buy groceries** on your list with no time set.",
        "Okay, it'll show up under Anytime.",
    ],
)
def test_a_reply_that_keeps_it_undated_is_replaced(reply: str) -> None:
    kept = reply_when_nothing_saved(
        reply, "no time, just put it on the list", about_reminders=True, prior_assistant=_ASKED
    )
    assert kept == KEEP_AS_REMINDER


@pytest.mark.parametrize(
    ("reply", "user_text"),
    [
        # Withdrawn: nothing to ask.
        ("No problem.", "never mind"),
        ("Okay, I won't set one.", "actually forget it"),
    ],
)
def test_a_withdrawn_add_keeps_its_reply(reply: str, user_text: str) -> None:
    kept = reply_when_nothing_saved(reply, user_text, about_reminders=True, prior_assistant=_ASKED)
    assert kept == reply


@pytest.mark.parametrize(
    "user_text",
    [
        "what should I add to my grocery list for a week of dinners?",
        "put the list in alphabetical order",
        "add this to my list of reasons to move",
    ],
)
def test_a_list_lookalike_is_left_alone(user_text: str) -> None:
    reply = "Rice, beans, onions and tomatoes cover most of the week."
    assert reply_when_nothing_saved(reply, user_text) == reply


def test_a_reminder_request_with_no_time_asks_when() -> None:
    claim = "I've set up a daily reminder for you."
    assert reply_when_nothing_saved(claim, "remind me to drink water") == NEED_A_TIME


@pytest.mark.parametrize(
    ("user_text", "day", "clock"),
    [
        ("remind me to call mom tomorrow at 6", " tomorrow", "6"),
        ("remind me to pay rent on friday at 9", " on Friday", "9"),
        ("remind me to buy 2 tickets next friday at 8", " next Friday", "8"),
        ("remind me to call mom at 6", "", "6"),
    ],
)
def test_a_bare_hour_keeps_the_day_and_asks_only_its_half(
    user_text: str, day: str, clock: str
) -> None:
    add = parse_spoken_add(user_text)
    assert add is not None and add.hour is None and "at" not in add.title.split()
    question = which_half_question(add)
    assert question is not None
    assert f"{clock} am or {clock} pm" in question and f"you{day}:" in question
    claim = "Got it, I'll set that for 6:00 PM."
    assert reply_when_nothing_saved(claim, user_text, about_reminders=True) == question


def test_an_hour_with_its_half_asks_nothing() -> None:
    assert which_half_question(parse_spoken_add("remind me to call mom tomorrow at 6pm")) is None


@pytest.mark.parametrize(
    ("text", "half"),
    [("pm", 12), ("P.M.", 12), ("in the evening", 12), ("am", 0), ("morning", 0), ("6pm", None)],
)
def test_half_of_day_reads_a_reply_that_is_only_its_half(text: str, half: int | None) -> None:
    assert half_of_day(text) == half


@pytest.mark.parametrize(
    ("text", "only"),
    [
        ("6pm", True),
        ("tomorrow at 6", True),
        ("ok friday then", True),
        ("pm", True),
        ("in 20 minutes", True),
        ("I start work at 6pm", False),
        ("i wake up at 6 every day", False),
        ("I am 6 feet tall", False),
    ],
)
def test_is_only_a_when(text: str, only: bool) -> None:
    assert is_only_a_when(text) is only


def _rows(*pairs: tuple[str, str]) -> list[SimpleNamespace]:
    return [SimpleNamespace(role=role, content=content) for role, content in pairs]


@pytest.mark.parametrize(
    ("window", "follows"),
    [
        (_rows(("user", "remind me to call mom"), ("assistant", _ASKED)), True),
        # The model's own question after a reminder request.
        (_rows(("user", "remind me to call mom at 6"), ("assistant", "6 am or 6 pm?")), True),
        # The model's own question about a list add (live 2026-11-06).
        (
            _rows(
                ("user", "also add buy groceries to my list"),
                ("assistant", 'When should I set "Buy groceries" for?'),
            ),
            True,
        ),
        (_rows(("user", "what is 2 + 2?"), ("assistant", "4. Anything else?")), False),
        (_rows(("user", "add 3 and 5"), ("assistant", "8. Another one?")), False),
        (_rows(("user", "ok"), ("assistant", "Sure, anything else?")), False),
    ],
)
def test_the_answer_to_a_reminder_question_keeps_the_todo_text(
    window: list[SimpleNamespace], follows: bool
) -> None:
    assert follows_reminder_card(window) is follows


async def _chat_with(db_session, *messages: tuple[str, str]):
    from app.modules.conversation import messages_repository as messages_repo

    user = await users_repo.create(
        db_session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )
    chat = await chats_repo.create(db_session, user_id=user.id, model="free-chat")
    for role, content in messages:
        await messages_repo.create(
            db_session, chat_id=chat.id, user_id=user.id, role=role, content=content
        )
    return user, chat


@pytest.mark.parametrize("answer", ["6pm", "pm", "in the evening"])
@pytest.mark.asyncio
async def test_the_half_of_day_finishes_the_add_on_its_day(db_session, fake_redis, answer):
    request = "remind me to call mom tomorrow at 6"
    question = which_half_question(parse_spoken_add(request))
    assert question is not None
    user, chat = await _chat_with(
        db_session, ("user", request), ("assistant", question), ("user", answer)
    )
    text, _written = await materialize_reminder_fences(
        db_session,
        user_id=user.id,
        chat_id=chat.id,
        assistant_text="Got it.",
        user_timezone="UTC",
        user_text=answer,
        prior_assistant=question,
        redis=fake_redis,
        confirm=True,
    )
    match = _CARD.search(text)
    assert match, text
    item = json.loads(match.group(1))["items"][0]
    assert item["title"] == "call mom"
    assert item["due_at"].endswith("T18:00:00Z")

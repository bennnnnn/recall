"""A yes to an offered reminder is its request; a reply never says reminders can't be set.

Live 2026-10-25: "Would you like me to set up that **Practice list comprehensions**
reminder for tomorrow (Monday) at 7:00 PM?" then "yes" got "Setting that reminder for you
now!" with no card. A memory recap said "I can't set reminders from here".
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.modules.chat import chats_repository as chats_repo
from app.modules.todos import repository as todos_repo
from app.modules.todos.offer_reply import accepted_offer_in, accepted_reminder_offer
from app.modules.todos.reminder_fences import materialize_reminder_fences
from app.modules.todos.reply_denials import is_denial, without_denials
from app.repositories import users as users_repo

LIVE_OFFER = (
    "Ah, that was a proposal I sent earlier, but it looks like it didn't actually save to "
    "your To-do list! 😅\n\nI can definitely create reminders for you now. Would you like "
    "me to set up that **Practice list comprehensions** reminder for tomorrow (Monday) at "
    "7:00 PM?"
)


@pytest.mark.parametrize(
    ("prior", "offered"),
    [
        (LIVE_OFFER, True),
        ("Want me to remind you at 9?", True),
        ("Should I add it to your to-do list?", True),
        ("Would you like a reminder for that?", True),
        ("Do you want me to set a reminder for the dentist on Friday?", True),
        ("Here is your plan. Want me to add the trip to your list?", True),
        ("Would you like a reminder app recommendation?", False),
        ("Want me to explain list comprehensions more?", False),
        ("Should I make it shorter?", False),
        ("Would you like me to add more examples?", False),
        ("Want a practice problem?", False),
        ("Do you want me to remind you how this works later?", False),
        ("I set that up. Anything else?", False),
    ],
)
def test_a_yes_accepts_only_an_offered_reminder(prior: str, offered: bool) -> None:
    assert (accepted_reminder_offer("yes", prior) is not None) is offered


@pytest.mark.parametrize("answer", ["yes", "Yes!", "sure", "yes please", "go ahead", "ok"])
def test_every_bare_yes_accepts(answer: str) -> None:
    assert accepted_reminder_offer(answer, "Want me to remind you at 9?")


@pytest.mark.parametrize("answer", ["no", "yes but at 8", "thanks", "what time?", ""])
def test_anything_else_is_its_own_words(answer: str) -> None:
    assert accepted_reminder_offer(answer, "Want me to remind you at 9?") is None


def test_the_offer_is_read_from_the_last_reply_in_the_window() -> None:
    window = [
        SimpleNamespace(role="user", content="wait you can't do reminders?"),
        SimpleNamespace(role="assistant", content=LIVE_OFFER),
        SimpleNamespace(role="user", content="yes"),
    ]
    assert accepted_offer_in("yes", window)
    assert accepted_offer_in("yes", window[:1]) is None
    assert accepted_offer_in("yes", None) is None


_CARD = re.compile(r"```reminder_proposal\n(.*?)\n```", re.DOTALL)


async def _offer_turn(session: Any, redis: Any, reply: str, prior: str) -> tuple[str, Any]:
    user = await users_repo.create(
        session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )
    chat = await chats_repo.create(session, user_id=user.id, model="free-chat")
    with patch("app.modules.todos.spoken_add._now", lambda tz: _NOW.astimezone(tz)):
        text, written = await materialize_reminder_fences(
            session,
            user_id=user.id,
            chat_id=chat.id,
            assistant_text=reply,
            user_timezone="UTC",
            user_text="yes",
            prior_assistant=prior,
            redis=redis,
            confirm=True,
        )
    assert written == 0
    return text, user


_NOW = (datetime.now(UTC) + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
_DUE = (_NOW + timedelta(days=1)).replace(hour=19)
_OFFER = "Would you like me to set up that **Practice** reminder for tomorrow at 7:00 PM?"
_FENCE = (
    "```reminder\n"
    + json.dumps({"title": "Practice list comprehensions", "due_at": _DUE.isoformat()})
    + "\n```"
)


@pytest.mark.asyncio
async def test_a_yes_to_the_offer_gets_its_card(db_session, fake_redis):
    text, user = await _offer_turn(
        db_session, fake_redis, f"Setting that reminder for you now! ⏰\n\n{_FENCE}", _OFFER
    )
    match = _CARD.search(text)
    assert match, text
    card = json.loads(match.group(1))
    assert card["items"][0]["title"] == "Practice list comprehensions"
    # Nothing is saved before the tap, and the reply does not say otherwise.
    assert "Setting that reminder" not in text
    assert await todos_repo.list_for_user(db_session, user.id, limit=10) == []


@pytest.mark.asyncio
async def test_a_yes_with_no_fence_says_nothing_was_saved(db_session, fake_redis):
    reply = "Setting that reminder for you now! ⏰\n\n**Practice list comprehensions**"
    text, _user = await _offer_turn(db_session, fake_redis, reply, _OFFER)
    assert "Setting that reminder" not in text
    assert "```reminder_proposal" not in text


@pytest.mark.asyncio
async def test_a_yes_to_another_offer_keeps_the_time_check(db_session, fake_redis):
    """The model's own time, after "Want a practice problem?", is still not the user's."""
    text, _user = await _offer_turn(
        db_session, fake_redis, f"Here you go.\n\n{_FENCE}", "Want a practice problem?"
    )
    assert "```reminder_proposal" not in text


LIVE_RECAP = (
    "Here's what I've got from our chats so far:\n\n- You're vegetarian.\n- From an earlier "
    "chat, you asked me to remind you to practice something tomorrow at 7pm. I can't set "
    "reminders from here, though, so you'll want to set that one in your own reminder app."
)


def test_a_denial_is_dropped_and_the_rest_kept() -> None:
    assert without_denials(LIVE_RECAP) == (
        "Here's what I've got from our chats so far:\n\n- You're vegetarian.\n- From an "
        "earlier chat, you asked me to remind you to practice something tomorrow at 7pm."
    )


@pytest.mark.parametrize(
    ("sentence", "denies"),
    [
        ("I can't set reminders from here.", True),
        ("I cannot create a reminder for you.", True),
        ("I don't have the ability to set reminders.", True),
        ("I can't remind you tomorrow, sorry.", True),
        ("You'll want to set that in your own reminder app.", True),
        ("Use your phone's reminder app for that.", True),
        ("I can't create a to-do list for you.", True),
        ("I can't remind you enough how much sleep matters.", False),
        ("I can't remind you of everything.", False),
        ("I can't read your iPhone's Reminders app.", False),
        ("Set an alarm in your clock app.", False),
        ("I can't set the oven timer.", False),
        ("I can't make a to-do list app for you, but here is a template.", False),
        ("Reminders help you stay on track.", False),
    ],
)
def test_is_denial(sentence: str, denies: bool) -> None:
    assert is_denial(sentence) is denies


def test_code_is_never_a_denial() -> None:
    code = "```python\n# I can't set reminders from here\nprint(1)\n```"
    assert without_denials(code) == code


def test_a_yes_to_the_offer_is_a_rich_turn() -> None:
    from app.modules.chat.turn_prep.mode import classify_turn_mode

    window = [
        SimpleNamespace(role="user", content="wait you can't do reminders?"),
        SimpleNamespace(role="assistant", content=LIVE_OFFER),
    ]
    assert classify_turn_mode(window, "yes").rich_context is True
    other = [SimpleNamespace(role="assistant", content="Want a practice problem?")]
    assert classify_turn_mode(other, "yes").rich_context is False


@pytest.mark.asyncio
async def test_a_yes_to_the_offer_loads_the_to_do_instructions(db_session):
    from app.core.config import get_settings
    from app.modules.todos.prompt_context import build_todos_system_section
    from app.modules.todos.prompt_hint import TODO_HINT

    user = await users_repo.create(
        db_session,
        email=f"{uuid4()}@example.com",
        name="Test User",
        avatar_url=None,
        google_sub=str(uuid4()),
    )
    settings = get_settings()
    section = await build_todos_system_section(
        db_session, user, settings, query_text="yes", accepted_offer=True
    )
    assert section is not None and section.startswith(TODO_HINT)
    assert await build_todos_system_section(db_session, user, settings, query_text="yes") is None

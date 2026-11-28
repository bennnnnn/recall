"""The to-do pass: chat reads to-dos and never writes them (owner, 2026-11-27).

A question about what is saved is answered from the rows; a reply that took the turn for a
change becomes the line and button that open To-do, in the user's language; a multi-part
message keeps its other answers; an offer to set a reminder goes from every reply.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat.finalize_todos import apply_todo_pass
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.todos.chat_language import todo_screen_answer
from app.tests.modules.chat.chat_test_support import turn_deps

_LINK = "```todo_link\n```"
_EN = todo_screen_answer("en")
_ES = todo_screen_answer("es")
_AM = todo_screen_answer("am")
_FENCE = '```reminder\n{"title": "Call mom", "due_at": "2026-10-24T09:00:00"}\n```'


@asynccontextmanager
async def _session() -> Any:
    yield MagicMock()


def _deps(read_back: AsyncMock | None = None, named: str | None = None) -> Any:
    reads = read_back or AsyncMock(return_value="Call mom — Tuesday, Oct 20, 6:00 PM.")
    todos = SimpleNamespace(read_back=reads, saved_todo_named=AsyncMock(return_value=named))
    return turn_deps(session_factory=_session, todos=todos)


def _ctx(message: str, locale: str = "en", prior_reply: str | None = None) -> StreamContext:
    """The turn, with the reply before it when given."""
    earlier = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": prior_reply}]
    return cast(
        StreamContext,
        SimpleNamespace(
            user=MagicMock(timezone="UTC", locale=locale),
            user_id=uuid4(),
            chat_id=uuid4(),
            user_timezone="Africa/Nairobi",
            user_message_content=message,
            stored_user_message=None,
            prompt_messages=[
                *(earlier if prior_reply else []),
                {"role": "user", "content": message},
            ],
        ),
    )


async def _pass(message: str, reply: str, **kwargs: Any) -> str:
    deps = kwargs.pop("deps", None) or _deps()
    return await apply_todo_pass(deps, Settings(), _ctx(message, **kwargs), reply)


@pytest.mark.asyncio
async def test_a_read_is_answered_from_the_saved_rows() -> None:
    read_back = AsyncMock(return_value="Call mom — Tuesday, Oct 20, 6:00 PM.")
    deps = _deps(read_back)
    # The model's list, a reminder it invented included, is never shown.
    out = await _pass("what's on my to-do list?", "You have: buy a boat at 5pm.", deps=deps)
    assert out == "Call mom — Tuesday, Oct 20, 6:00 PM."
    read_back.assert_awaited_once()
    assert read_back.call_args.args[2] == "Africa/Nairobi"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "reply", "locale", "answer"),
    [
        # The model wrote a reminder anyway: nothing is saved, the line and button instead.
        ("can you make sure I don't forget to call mom", f"Sure!\n\n{_FENCE}", "en", _EN),
        # The button the prompt asks for, with words of the model's beside it.
        ("cancel my dentist", f"I can't change that here.\n\n{_LINK}", "en", _EN),
        # Live, beside the button: "Done. I've added Buy milk…" for a change nothing made.
        (
            "añade leche a mis tareas",
            f"Ya está. He añadido **Comprar leche** para mañana.\n\n{_LINK}",
            "en",
            _ES,
        ),
        ("ነገ እናቴን እንድደውል አስታውሰኝ", _FENCE, "en", _AM),
    ],
)
async def test_a_change_the_model_took_on_becomes_the_todo_line(
    message: str, reply: str, locale: str, answer: str
) -> None:
    assert await _pass(message, reply, locale=locale) == answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply",
    [
        "Done! I've marked **call mom** as complete ✅",
        "Sure, I've moved the gym to Friday at 6 PM.",
        "All set!",
    ],
)
async def test_a_reply_saying_a_change_was_made_becomes_the_todo_line(reply: str) -> None:
    assert await _pass("mark call mom as done", reply) == _EN


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "reply"),
    [
        # A question about a saved row: "it's set for 3 PM" is true, it reads the list.
        ("is my dentist appointment still on?", "Yes, it's set for Friday at 3 PM."),
        ("when is my dentist appointment?", "Your dentist appointment is Friday at 3 PM."),
        # Ordinary turns that use the words.
        ("what time does the gym open?", "Most gyms open at 6 AM. I've set aside a list."),
        ("write a reminder email to my team", "Subject: Reminder\n\nHi team, the report is due."),
    ],
)
async def test_a_read_or_an_ordinary_reply_is_kept(message: str, reply: str) -> None:
    assert await _pass(message, reply) == reply


@pytest.mark.asyncio
async def test_a_multi_part_message_keeps_its_other_answer_and_gets_the_line() -> None:
    out = await _pass(
        "What is the capital of France, and remind me to call mom at 6pm",
        "The capital of France is **Paris**.\n\nI've set a reminder to call mom at 6 PM.",
    )
    assert out == f"The capital of France is **Paris**.\n\n{_EN}"


@pytest.mark.asyncio
async def test_an_offer_to_set_a_reminder_goes_from_any_reply() -> None:
    out = await _pass(
        "how do I make sourdough?",
        "Mix flour and water, then wait a week. Want me to set a reminder to feed it?",
    )
    assert out == "Mix flour and water, then wait a week."


@pytest.mark.asyncio
async def test_a_remember_turn_claims_no_to_do() -> None:
    out = await _pass(
        "remember that I want to try cacio e pepe again",
        "Noted! I've added that to your to-do list so you don't forget.",
    )
    assert "to-do" not in out
    assert "```todo_link" not in out


@pytest.mark.asyncio
async def test_a_failure_keeps_the_finished_reply() -> None:
    deps = _deps(AsyncMock(side_effect=RuntimeError("db")))
    assert await _pass("what's on my to-do list?", "You have none.", deps=deps) == "You have none."


@pytest.mark.asyncio
async def test_a_message_naming_a_saved_to_do_is_a_change() -> None:
    deps = _deps(named="gym")
    assert await _pass("move gym to 7pm", "Moved **gym** to 7:00 PM.", deps=deps) == _EN


@pytest.mark.asyncio
async def test_a_title_the_reply_before_holds_is_that_replys() -> None:
    """ "Remove the gym days" edits the workout plan above, whatever the user saved."""
    plan = "| **Mon** | Gym — Push |\n| **Tue** | Run |"
    reply = "Removed the gym days. Here's the new plan."
    out = await _pass(
        "remove the gym days, i'll just run outside",
        reply,
        deps=_deps(named="gym"),
        prior_reply=plan,
    )
    assert out == reply


@pytest.mark.asyncio
async def test_a_reply_that_was_only_an_offer_sends_the_user_to_todo() -> None:
    reply = "Want me to add **Buy milk** to your reminders?"
    assert await _pass("buy milk", reply) == _EN


@pytest.mark.asyncio
async def test_a_worked_answer_s_set_line_is_no_claim() -> None:
    reply = "Remember: for $ax^2 + bx + c = 0$,\n\nSet: $a = 1$, $b = 4$, $c = 1$."
    assert await _pass("remind me the quadratic formula and use it", reply) == reply


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("prior", "message", "reply"),
    [
        # Review of #2619: after the button or a read-back, an ordinary turn keeps its reply.
        (_EN, "explain photosynthesis", "The sugar is then moved through the phloem to the roots."),
        (
            "Call mom — Tuesday, Oct 20, 6:00 PM.\nDone: Milk.",
            "now add type hints",
            "Done — added type hints to every function.",
        ),
        ("Set: gym — Thursday, 6:00 PM.", "make it shorter", "Done. Here's a shorter version."),
    ],
)
async def test_an_ordinary_turn_after_a_to_do_reply_keeps_its_reply(
    prior: str, message: str, reply: str
) -> None:
    assert await _pass(message, reply, prior_reply=prior) == reply


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    ["Can you mark call mom as done?", "Could you delete my dentist reminder?"],
)
async def test_a_polite_request_is_still_a_request(message: str) -> None:
    reply = "Done! I've deleted your dentist reminder and marked call mom as done."
    assert await _pass(message, reply) == _EN

"""A reminder the read says the message asks for: its card, one question, and no false claim
(``chat.reminder_turn``).

The eight transcripts of the live QA round (2026-11-22) are replayed through the real
reminder pass with the read's answer faked: each gets its card at 5 PM tomorrow, and a reply
with no card never says a reminder is set.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat import reminder_turn
from app.modules.chat.finalize_reminders import apply_reminder_pass
from app.modules.chat.reminder_turn import NOT_SAVED_YET, NOTHING_SAVED, ReminderRead, honest
from app.modules.chat.turn_deps import default_deps
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.todos.model_read import ReminderReading
from app.tests.behavior import sweep

ZONE = "America/Los_Angeles"
# Sunday 22 November 2026, 10:00 in Los Angeles.
NOW = datetime(2026, 11, 22, 18, 0, tzinfo=UTC)
_MON_5PM = "2026-11-24T01:00:00Z"


def _card(title: str, due: str, *, saved: bool = False) -> str:
    card: dict[str, Any] = {
        "proposal_id": "p-old",
        "items": [{"action": "add", "title": title, "due_at": due, "when": "Monday"}],
    }
    if saved:
        card["status"] = "saved"
    return f"```reminder_proposal\n{json.dumps(card)}\n```"


def _done(value: Any) -> asyncio.Future[Any]:
    future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    future.set_result(value)
    return future


def _ctx(line: str, history: list[tuple[str, str]], read: Any) -> StreamContext:
    user = sweep._user(pro=True)
    user.timezone = ZONE
    ctx = StreamContext(
        user_id=user.id,
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[
            *({"role": role, "content": text} for role, text in history),
            {"role": "user", "content": line},
        ],
        run_title=False,
        user_message_content=line,
        reserved_tokens=0,
        max_output_tokens=0,
        user_timezone=ZONE,
        user=user,
    )
    rows = [SimpleNamespace(role=role, content=text) for role, text in history]
    ctx.recent_messages = [*rows, SimpleNamespace(role="user", content=line)]
    ctx.reminder_read = reminder_turn.PendingRead(
        asked=_done(read is not None), task=cast(Any, _done(read))
    )
    return ctx


@contextmanager
def _turn(ctx: StreamContext) -> Iterator[None]:
    """The sweep's in-memory reminders and frozen clock, the chat's rows as the turn read them."""
    from app.modules.conversation import messages_repository

    outcome = sweep.Outcome(entry=sweep.Entry(id="t", area="todo", prompt="", reply=""))
    with (
        patch.object(sweep, "SWEEP_NOW", NOW),
        sweep.frozen_clock(),
        sweep._stores(outcome, cast(Any, ctx.user)),
        patch.object(
            messages_repository, "list_recent", AsyncMock(return_value=ctx.recent_messages)
        ),
    ):
        yield


async def _finish(line: str, reply: str, history: list[tuple[str, str]], read: Any) -> str:
    ctx = _ctx(line, history, read)
    deps = replace(
        default_deps(),
        session_factory=sweep._session,
        users=SimpleNamespace(get_by_id=AsyncMock(return_value=ctx.user)),
    )
    with _turn(ctx):
        text: str = await apply_reminder_pass(deps, AsyncMock(), Settings(), ctx, reply, None)
    return text


def _items(text: str) -> list[dict[str, Any]]:
    start = text.index("```reminder_proposal\n") + len("```reminder_proposal\n")
    items: list[dict[str, Any]] = json.loads(text[start : text.index("\n```", start)])["items"]
    return items


def _read(**fields: object) -> ReminderRead:
    return ReminderRead(reading=ReminderReading.model_validate({"request": "add", **fields}))


_TMRW_5 = {"day": "tmrw", "day_quote": "tmrw", "time": "5", "time_quote": "at 5"}

# (earlier chat, the message, the reply the live model wrote, the read's answer).
_TRANSCRIPTS = [
    (
        [("user", "hey can u remind me to move my car tmrw at 5"),
         ("assistant", "Do you mean 5 am or 5 pm tomorrow?")],
        "pm, after my 4pm lab. street sweeping is in the morning so i think i need it moved by "
        "like 5:30 but 5 is fine lol",
        "Got it — I'll set a reminder for tomorrow at 5:00 PM. You can change or turn off "
        "reminders in Settings → Reminders.",
        _read(task="move my car", task_quote="move my car", day="tmrw", day_quote="tmrw",
              time="5", time_quote="5 is fine", half="pm", half_quote="pm"),
    ),
    (
        [],
        "Could you remind me tmrw at 5 to call my sister Margaret about the quilting group",
        "Of course — I've set a reminder for tomorrow at 5 to call Margaret",
        _read(task="call my sister Margaret", task_quote="call my sister Margaret", **_TMRW_5),
    ),
    (
        [("user", "can u remind me to take my migraine med tmrw at 5? thx"),
         ("assistant", "When should I remind you?")],
        "ugh sorry, i said tmrw at 5 lol. 5pm. can u just do that",
        "Sure — which city or time zone are you in?",
        _read(task="take my migraine med", task_quote="take my migraine med", day="tmrw",
              day_quote="tmrw", time="5pm", time_quote="5pm"),
    ),
    (
        [("user", "hey can u remind me abt my moms bday dinner tmrw at 5"),
         ("assistant", "When should I remind you?")],
        "tmrw at 5 lol. the dinner is at 5 so remind me like an hour before? or just at 5 is fine",
        "I can keep that as a reminder with a time. When should I remind you?",
        _read(task="moms bday dinner", task_quote="moms bday dinner", **_TMRW_5),
    ),
    (
        [("user", "hey can u remind me to grab an umbrella tmrw at 5?"),
         ("assistant", "When should I remind you?")],
        "tmrw at 5 lol",
        "When should I remind you?",
        _read(task="grab an umbrella", task_quote="grab an umbrella", **_TMRW_5),
    ),
    (
        [],
        "remind me abt something tmrw at 5, i had a dream about my grandma's basement and i "
        "want to write the dream down",
        "Tomorrow at 5 is set ✅",
        _read(task="write the dream down", task_quote="write the dream down", **_TMRW_5),
    ),
    (
        [("user", "hi can u remind me about the meeting w my boss tmrw at 5"),
         ("assistant", "When should I remind you?")],
        "the reminder is for tmrw at 5pm",
        "I can't create the reminder without a specific task title",
        _read(task="the meeting w my boss", task_quote="the meeting w my boss", day="tmrw",
              day_quote="tmrw", time="5pm", time_quote="5pm"),
    ),
    (
        [],
        "remind me abt my bio test tmrw at 5?",
        "Done — I'll remind you tomorrow at 5",
        _read(task="my bio test", task_quote="my bio test", **_TMRW_5),
    ),
]  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.parametrize(("history", "line", "reply", "read"), _TRANSCRIPTS)
async def test_each_transcript_ends_with_its_card_and_claims_nothing(
    history, line, reply, read
) -> None:
    text = await _finish(line, reply, history, read)
    (item,) = _items(text)
    assert item["action"] == "add" and item["due_at"] == _MON_5PM
    prose = text[: text.index("```reminder_proposal")]
    for false in ("set", "Done", "remind you", "time zone", "city", "5 am", "can't"):
        assert false not in prose, prose


@pytest.mark.asyncio
async def test_a_reply_with_no_card_never_claims_a_reminder() -> None:
    """The read says a reminder was asked for and its reading came to nothing."""
    text = await _finish(
        "ok so don't let me forget to water the plants",
        "Got it, I'll remind you tonight at 8 🌱",
        [],
        ReminderRead(reading=None),
    )
    # The word rules' own line ("I didn't change your reminders") or the read's: no claim.
    assert "remind you" not in text and "I'll" not in text


@pytest.mark.asyncio
async def test_a_missing_task_is_asked_once() -> None:
    text = await _finish(
        "remind me tomorrow at 5", "Sure! I'll remind you tomorrow at 5.", [],
        _read(task="", **_TMRW_5),
    )  # fmt: skip
    assert text == "What should I remind you about?"


@pytest.mark.asyncio
async def test_did_it_save_after_an_untapped_card_says_not_yet() -> None:
    history = [
        ("user", "remind me to call mom tomorrow at 5pm"),
        ("assistant", _card("Call mom", _MON_5PM)),
    ]
    status = ReminderRead(reading=ReminderReading(request="status"))
    text = await _finish("did it save?", "Yes, it's saved! ✅", history, status)
    assert text == NOT_SAVED_YET
    # Not "did it" read as done: no card marks the reminder done.
    assert "reminder_proposal" not in text


@pytest.mark.asyncio
async def test_did_it_save_after_a_tapped_card_stays() -> None:
    saved = _card("Call mom", _MON_5PM, saved=True)
    status = ReminderRead(reading=ReminderReading(request="status"))
    text = await _finish(
        "did it save?", "Yes, it's saved for tomorrow at 5 PM.",
        [("user", "remind me to call mom tomorrow at 5pm"), ("assistant", saved)], status,
    )  # fmt: skip
    assert text == "Yes, it's saved for tomorrow at 5 PM."


@pytest.mark.asyncio
async def test_did_it_save_after_a_false_claim_offers_the_card_now() -> None:
    history = [
        ("user", "remind me abt my bio test tmrw at 5?"),
        ("assistant", "Done — I'll remind you tomorrow at 5"),
    ]
    reading = ReminderReading.model_validate(
        {"request": "status", "task": "my bio test", "task_quote": "my bio test", **_TMRW_5}
    )
    text = await _finish(
        "did it actually save tho?", "It's saved.", history, ReminderRead(reading=reading)
    )
    assert text.startswith(NOT_SAVED_YET)
    (item,) = _items(text)
    assert item["due_at"] == _MON_5PM


@pytest.mark.asyncio
async def test_no_read_leaves_the_word_rules_reply() -> None:
    """The Decider said no (or nothing in time): the reply is the word rules' alone."""
    text = await _finish("that reminds me of my dad", "That's a sweet memory.", [], None)
    assert text == "That's a sweet memory."


@pytest.mark.asyncio
async def test_a_read_of_no_request_leaves_the_reply() -> None:
    none = ReminderRead(reading=ReminderReading(request="none"))
    reply = "Reminders on iPhone are saved in iCloud."
    assert await _finish("how do reminders sync?", reply, [], none) == reply


@pytest.mark.parametrize(
    "reply",
    [
        "I can set a reminder for that if you want — what time works?",
        "You set an alarm last week, so try putting the phone across the room.",
        "Reminders work best when they name one small step.",
    ],
)
def test_honest_keeps_a_reply_that_claims_nothing(reply: str) -> None:
    assert honest(reply) == reply


@pytest.mark.parametrize(
    "reply",
    [
        "Of course! I'll remind you tomorrow at 5:00 PM 🎁",
        "Added — tomorrow at 5. 🎸",
        "Got it — I've got you covered for tomorrow at 5.",
        "It's saved — you don't need to go looking for it.",
        "Tomorrow at 5 is set ✅",
    ],
)
def test_honest_drops_every_claim_of_a_reminder(reply: str) -> None:
    assert NOTHING_SAVED in honest(reply)


@pytest.mark.asyncio
async def test_the_read_is_never_started_for_a_server_answer_or_off() -> None:
    ctx = _ctx("remind me tmrw at 5", [], None)
    ctx.instant_reply = "It's 10:00."
    assert reminder_turn.start_reminder_read(Settings(openrouter_api_key="k"), ctx) is None
    ctx.instant_reply = None
    off = Settings(openrouter_api_key="k", reminder_read_enabled=False)
    assert reminder_turn.start_reminder_read(off, ctx) is None


@pytest.mark.asyncio
async def test_another_language_is_never_read_for_a_card() -> None:
    """Non-English chat only reads its to-dos (owner, 2026-11-07): no Decider call at all."""
    ctx = _ctx("recuérdame mañana a las 5 llamar a mi mamá", [], None)
    asks = AsyncMock(return_value=True)
    asked: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
    with patch.object(reminder_turn, "asks_for_a_reminder", asks):
        assert await reminder_turn._read(Settings(openrouter_api_key="k"), ctx, asked) is None
    asks.assert_not_awaited()
    assert asked.result() is False


@pytest.mark.asyncio
async def test_a_late_decider_is_never_waited_for() -> None:
    """A turn whose Decider answer is not in when the reply ends goes on without it."""
    ctx = _ctx("hello", [], None)
    never: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
    task = asyncio.create_task(asyncio.sleep(30))
    ctx.reminder_read = reminder_turn.PendingRead(asked=never, task=cast(Any, task))
    settings = Settings(reminder_decide_wait_seconds=0.01)
    assert await reminder_turn._reading(ctx, settings) is None
    await asyncio.sleep(0)
    assert task.cancelled()


@pytest.mark.asyncio
@pytest.mark.parametrize(("odds", "asks"), [(0.999, True), (0.86, False)])
async def test_the_deciders_yes_is_its_sure_one(odds: float, asks: bool) -> None:
    reply = SimpleNamespace(
        answers={"reminder": SimpleNamespace(noul=odds)}, usage=SimpleNamespace(cost=0.0)
    )
    with patch("app.gateways.decider_gateway.decide", AsyncMock(return_value=reply)):
        got = await reminder_turn.asks_for_a_reminder(
            Settings(openrouter_api_key="k"), "remind me tmrw at 5", []
        )
    assert got is asks


@pytest.mark.asyncio
async def test_a_failed_decider_call_is_no() -> None:
    with patch("app.gateways.decider_gateway.decide", AsyncMock(side_effect=RuntimeError)):
        assert not await reminder_turn.asks_for_a_reminder(Settings(), "remind me", [])


@pytest.mark.asyncio
async def test_did_it_save_with_no_card_and_no_task_says_so_and_asks() -> None:
    history = [("user", "remind me tmrw at 5 abt it"), ("assistant", "Tomorrow at 5 is set ✅")]
    reading = ReminderReading.model_validate({"request": "status", **_TMRW_5})
    text = await _finish(
        "did it actually save?",
        "Just a vibe thing 😭 I don't have a reminder tool here.",
        history,
        ReminderRead(reading=reading),
    )
    assert text.startswith(reminder_turn.NOTHING_SAVED_YET)
    assert "tool" not in text and text.endswith("?")


def test_honest_never_says_the_app_cannot_make_one() -> None:
    assert "tool" not in honest(
        "Got it! I'll remind you at 5. I don't have a reminder tool though."
    )

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
from contextlib import ExitStack, contextmanager
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


async def _finish(
    line: str,
    reply: str,
    history: list[tuple[str, str]],
    read: Any,
    *,
    saved: list[Any] | None = None,
) -> str:
    """The reply as the reminder pass leaves it; ``saved``: the user's rows, in place of the
    sweep's six."""
    ctx = _ctx(line, history, read)
    deps = replace(
        default_deps(),
        session_factory=sweep._session,
        users=SimpleNamespace(get_by_id=AsyncMock(return_value=ctx.user)),
    )
    with ExitStack() as stack:
        stack.enter_context(_turn(ctx))
        if saved is not None:
            stack.enter_context(
                patch(
                    "app.modules.todos.repository.list_for_user",
                    AsyncMock(return_value=saved),
                )
            )
        text: str = await apply_reminder_pass(deps, AsyncMock(), Settings(), ctx, reply, None)
    return text


def _row(title: str, due: datetime, **fields: Any) -> SimpleNamespace:
    """A reminder the user saved: in the To-do screen, or by a card tapped long ago."""
    row = {"id": uuid4(), "content": title, "topic": "Reminders", "due_at": due,
           "due_has_time": True, "recurrence_rule": None, "checked": False, "chat_id": None,
           "sort_order": 0, "source": "manual"}  # fmt: skip
    return SimpleNamespace(**{**row, **fields})


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
@pytest.mark.parametrize("spend", ["capped", "down"])
async def test_past_the_spend_cap_or_in_an_outage_nothing_is_read(spend: str) -> None:
    """Neither the Decider nor the request's read is called: the word rules read the turn."""
    from datetime import datetime as real_datetime

    from app.modules.todos.model_read import read_reminder_chat

    gate = AsyncMock(return_value=True) if spend == "capped" else AsyncMock(side_effect=OSError)
    decide = AsyncMock()
    complete = AsyncMock()
    with (
        patch("app.services.quota.global_spend_exceeded", gate),
        patch("app.gateways.decider_gateway.decide", decide),
        patch("app.gateways.structured_completion.complete_structured", complete),
    ):
        settings = Settings(openrouter_api_key="k")
        assert not await reminder_turn.asks_for_a_reminder(settings, "remind me tmrw at 5", [])
        read = await read_reminder_chat(
            settings, [], "remind me tmrw at 5", now=real_datetime.now()
        )
        assert read is None
    decide.assert_not_awaited()
    complete.assert_not_awaited()


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


@pytest.mark.asyncio
async def test_a_card_of_several_reminders_from_the_word_rules_stays() -> None:
    """The read writes one request down: it never replaces a card of two (review of #2535)."""
    line = "remind me to call mom at 5pm and to pay rent on friday at 9am"
    text = await _finish(line, "Sure!", [], _read(task="call mom", task_quote="call mom",
                                                  time="5pm", time_quote="at 5pm"))  # fmt: skip
    assert len(_items(text)) == 2


@pytest.mark.asyncio
async def test_dont_set_a_reminder_outranks_the_read() -> None:
    reply = "Good plan — calling her at 5 tomorrow sounds right."
    text = await _finish(
        "I will call mom tomorrow at 5pm, do not set a reminder", reply, [],
        _read(task="call mom", task_quote="call mom", day="tomorrow", day_quote="tomorrow",
              time="5pm", time_quote="5pm"),
    )  # fmt: skip
    assert "reminder_proposal" not in text


@pytest.mark.asyncio
async def test_a_question_about_something_else_is_not_asking_when() -> None:
    """ "Are you flying or driving?" before "remind me to call grandma": when is asked."""
    history = [
        ("user", "I am visiting Chicago next month"),
        ("assistant", "Nice! Flying or driving?"),
    ]
    text = await _finish(
        "remind me to call grandma", "Sure!", history,
        _read(task="call grandma", task_quote="call grandma"),
    )  # fmt: skip
    assert "reminder_proposal" not in text and text.endswith("?")


@pytest.mark.asyncio
async def test_a_regenerate_leaves_out_the_reply_it_redoes() -> None:
    from app.modules.chat.turn_prep.context import RegenerateBackup

    ctx = _ctx("remind me to call mom", [], None)
    old = SimpleNamespace(id=uuid4(), role="assistant", content="When should I remind you?")
    ctx.recent_messages = [
        SimpleNamespace(id=uuid4(), role="user", content="remind me to call mom"),
        old,
    ]
    ctx.regenerate_backup = RegenerateBackup(content=old.content, model=None, message_id=old.id)
    assert reminder_turn.conversation(ctx) == []


@pytest.mark.asyncio
async def test_did_it_save_about_a_reminder_no_card_was_offered_for_gets_its_card() -> None:
    """An earlier tapped card is another reminder's: "did it save?" is about the bio test."""
    history = [
        ("user", "remind me to call mom tomorrow at 5pm"),
        ("assistant", _card("Call mom", _MON_5PM, saved=True)),
        ("user", "remind me abt my bio test tmrw at 5?"),
        ("assistant", "Done — I'll remind you tomorrow at 5"),
    ]
    reading = ReminderReading.model_validate(
        {"request": "status", "task": "my bio test", "task_quote": "my bio test", **_TMRW_5}
    )
    text = await _finish("did it save?", "Yes, it's saved!", history, ReminderRead(reading=reading))
    assert text.startswith(NOT_SAVED_YET) and "bio" in _items(text)[0]["title"].lower()


_STATUS_CALL_MOM = ReminderReading.model_validate(
    {"request": "status", "task": "call mom", "task_quote": "call mom", "day": "tomorrow",
     "day_quote": "tomorrow", "time": "5pm", "time_quote": "5pm"}
)  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.parametrize("reading", [_STATUS_CALL_MOM, ReminderReading.model_validate(
    {"request": "status", "task": "call mom", "task_quote": "call mom"})])  # fmt: skip
async def test_did_it_save_about_one_saved_outside_the_chat_says_it_is(reading) -> None:
    """Saved in the To-do screen (or by a card tapped 30 messages ago): the chat shows no
    card, and the answer is the saved row, never "No reminder is saved yet" (Gemini, PR
    #2535)."""
    rows = [_row("Call mom", datetime(2026, 11, 24, 1, 0, tzinfo=UTC))]
    text = await _finish(
        "did my reminder to call mom tomorrow at 5pm save?", "I'm not sure, let me check.",
        [], ReminderRead(reading=reading), saved=rows,
    )  # fmt: skip
    assert text.startswith("Yes, it's saved: **Call mom**, Monday, Nov 23, 5:00 PM")
    assert "reminder_proposal" not in text and reminder_turn.NOTHING_SAVED_YET not in text


@pytest.mark.asyncio
async def test_did_it_save_about_another_task_or_a_done_one_is_not_that_row() -> None:
    """A saved "Call grandma", a checked "Call mom" and last month's are not the reminder
    asked about: its card is offered now."""
    rows = [
        _row("Call grandma", datetime(2026, 11, 24, 1, 0, tzinfo=UTC)),
        _row("Call mom", datetime(2026, 11, 24, 1, 0, tzinfo=UTC), checked=True),
        _row("Call mom", datetime(2026, 10, 20, 1, 0, tzinfo=UTC)),
    ]
    text = await _finish(
        "did my reminder to call mom tomorrow at 5pm save?", "Yes!", [],
        ReminderRead(reading=_STATUS_CALL_MOM), saved=rows,
    )  # fmt: skip
    assert text.startswith(NOT_SAVED_YET)
    (item,) = _items(text)
    assert item["due_at"] == _MON_5PM


@pytest.mark.asyncio
async def test_two_bare_hour_reminders_with_fences_each_get_their_item() -> None:
    """ "tomorrow at 5 and … on friday at 9": the model's two fences carry hours the rule
    never reads, and each clause's own time is the card's (Gemini, PR #2535)."""
    reply = (
        'Sure!\n\n```reminder\n{"title": "Call mom", "due_at": '
        '"2026-11-23T05:00:00-08:00"}\n```\n\n```reminder\n{"title": "Pay rent", '
        '"due_at": "2026-11-27T21:00:00-08:00"}\n```'
    )
    line = "remind me to call mom tomorrow at 5 and to pay rent on friday at 9"
    text = await _finish(line, reply, [], _read(task="call mom", task_quote="call mom",
                                                **_TMRW_5))  # fmt: skip
    items = _items(text)
    assert [item["title"].lower() for item in items] == ["call mom", "pay rent"]
    # 5 PM Monday and 9 AM Friday in Los Angeles.
    assert [item["due_at"] for item in items] == ["2026-11-24T01:00:00Z", "2026-11-27T17:00:00Z"]


@pytest.mark.asyncio
async def test_a_clock_in_another_zone_is_the_cards_on_the_users_own_clock() -> None:
    """ "tomorrow at 2pm EST" for a user in Los Angeles: the card is 11 AM theirs."""
    reply = (
        'Sure!\n\n```reminder\n{"title": "Join the webinar", "due_at": '
        '"2026-11-23T11:00:00-08:00"}\n```'
    )
    text = await _finish(
        "Remind me tomorrow at 2pm EST to join the webinar", reply, [],
        _read(task="join the webinar", task_quote="join the webinar", day="tomorrow",
              day_quote="tomorrow", time="2pm", time_quote="at 2pm EST",
              zone="America/New_York", zone_quote="EST"),
    )  # fmt: skip
    (item,) = _items(text)
    assert item["due_at"] == "2026-11-23T19:00:00Z"


@pytest.mark.asyncio
async def test_did_it_save_is_not_answered_by_a_card_that_only_shares_a_verb() -> None:
    """ "Call mom" is not "call my sister Margaret": one shared word is not the same task
    (the rows' own two-word rule, review on #2535)."""
    history = [
        ("user", "remind me to call mom tomorrow at 5pm"),
        ("assistant", _card("Call mom", _MON_5PM, saved=True)),
        ("user", "Could you remind me tmrw at 5 to call my sister Margaret"),
        ("assistant", "Done! I'll remind you tomorrow at 5."),
    ]
    reading = ReminderReading.model_validate(
        {"request": "status", "task": "call my sister Margaret",
         "task_quote": "call my sister Margaret", **_TMRW_5}
    )  # fmt: skip
    text = await _finish(
        "Did it actually save?", "Yes, it's saved!", history, ReminderRead(reading=reading)
    )
    assert text.startswith(NOT_SAVED_YET) and "margaret" in _items(text)[0]["title"].lower()


@pytest.mark.asyncio
async def test_did_it_save_about_an_untimed_task_is_not_answered_by_another_card() -> None:
    """A request with no time yet has no adds: its task still decides whose card it is."""
    history = [
        ("user", "remind me to call mom tomorrow at 5pm"),
        ("assistant", _card("Call mom", _MON_5PM, saved=True)),
        ("user", "remind me to water the plants"),
        ("assistant", "Done, I'll remind you!"),
    ]
    reading = ReminderReading.model_validate(
        {"request": "status", "task": "water the plants", "task_quote": "water the plants"}
    )
    text = await _finish(
        "did my reminder to water the plants save?", "Yes, it's saved!", history,
        ReminderRead(reading=reading),
    )  # fmt: skip
    assert text.startswith(reminder_turn.NOTHING_SAVED_YET)

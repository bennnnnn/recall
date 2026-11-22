"""The turn's read on two of the owner's turns (2026-11-22): the photo above an answer, and a
language named after a draft (``decided_turn``)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.models.orm import User
from app.modules.chat.answer_photo_offer import offers_photo_in, without_answer_photo_hints
from app.modules.chat.decided_turn import decide_from_the_read
from app.modules.chat.decider_read import SEEN_AT, decision_fields
from app.modules.chat.prompt_constants.answer_subject import subject_photo_hint
from app.modules.chat.prompt_constants.conversation import FOLLOW_NOTES, draft_change_note
from app.modules.chat.prompt_constants.visuals import ANSWER_PHOTO_HINT, WHERE_IS_PHOTO_HINT
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_prep.context import StreamContext
from app.modules.chat.turn_trace import begin_turn_trace
from app.tests.fakes import isolated_settings

_SETTINGS = isolated_settings()
_DRAFT = (
    "Here's a short reply you can use to confirm the visit:\n\n```message\nHi,\n\nThank you "
    "for the offer. I'm happy to come to the office tomorrow.\n\nThanks,\nbini\n```"
)


def _done(read: TurnDecision | None) -> asyncio.Future[Any]:
    future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    future.set_result(read)
    return future


def _read(**fields: Any) -> TurnDecision:
    return TurnDecision.model_validate(
        {"live": False, "subject": "everyday", "think": False, **fields}
    )


def _turn(content: str, read: TurnDecision | None, system: str, recent: list[Any]) -> StreamContext:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[
            {"role": "system", "content": system},
            *({"role": m.role, "content": m.content} for m in recent),
            {"role": "user", "content": content},
        ],
        run_title=False,
        user_message_content=content,
        reserved_tokens=100,
        max_output_tokens=100,
    )
    ctx.user = User(id=uuid4(), email="a@b.c", plan="free")
    ctx.auto_routed, ctx.thinking = True, "off"
    ctx.recent_messages = recent
    ctx.live_read = _done(read)  # type: ignore[assignment]
    return ctx


def _photo_system(query: str) -> str:
    return f"rules\n\n{ANSWER_PHOTO_HINT}\n\n{subject_photo_hint(query)}\n\nmore rules"


@pytest.mark.asyncio
async def test_a_read_that_sees_nothing_takes_the_photo_away() -> None:
    """ "What is ur name" got a photo above "My name is Recall": its word rule named "ur name"
    as the thing to look up."""
    trace = begin_turn_trace("new")
    ctx = _turn("What is ur name", _read(seen=False), _photo_system("ur name"), [])
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.no_answer_photo is True
    assert not offers_photo_in(ctx.prompt_messages)
    assert all("```photo" not in str(m["content"]) for m in ctx.prompt_messages)
    assert ctx.prompt_messages[0]["content"] == "rules\n\nmore rules"
    assert "read.no_photo" in trace.prompt_rules


@pytest.mark.parametrize("read", [_read(seen=True), _read(), None])
@pytest.mark.asyncio
async def test_a_photo_the_read_sees_or_says_nothing_about_stays(read: TurnDecision | None) -> None:
    system = _photo_system("capybara")
    ctx = _turn("what is a capybara", read, system, [])
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.no_answer_photo is False
    assert ctx.prompt_messages[0]["content"] == system


def test_the_photo_hints_go_for_a_place_too() -> None:
    messages = [{"role": "system", "content": f"a\n\n{ANSWER_PHOTO_HINT}\n\n{WHERE_IS_PHOTO_HINT}"}]
    assert without_answer_photo_hints(messages, "where is Petra") == [
        {"role": "system", "content": "a"}
    ]


@pytest.mark.parametrize(("odds", "seen"), [(0.99, True), (SEEN_AT, True), (0.4, False)])
def test_the_deciders_seen_odds_are_held_to_its_threshold(odds: float, seen: bool) -> None:
    answers: dict[str, Any] = {
        "subject": {"choice": "everyday"},
        "think": {"noul": 0.0},
        "hard": {"noul": 0.0},
        "live": {"noul": 0.0},
        "asked": {"noul": 0.0},
        "seen": {"noul": odds},
    }
    fields = decision_fields(answers, has_earlier=False)
    assert fields is not None and fields["seen"] is seen
    del answers["seen"]
    fields = decision_fields(answers, has_earlier=False)
    assert fields is not None and fields["seen"] is None


@pytest.mark.parametrize("line", ["In Amharic", "Hindi", "en español"])
@pytest.mark.asyncio
async def test_a_change_to_a_draft_gets_the_drafts_note(line: str) -> None:
    """ "In Amharic" after a ```message draft got "I'm sorry, but I can't reply in Amharic in
    this way" (the owner's chat, 2026-11-22)."""
    recent = [
        SimpleNamespace(role="user", content="Replay"),
        SimpleNamespace(role="assistant", content=_DRAFT),
    ]
    ctx = _turn(line, _read(follow="change"), "rules", recent)
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.prompt_messages[-2:] == [
        {"role": "system", "content": draft_change_note("message")},
        {"role": "user", "content": line},
    ]
    assert "```message fence" in draft_change_note("message")


@pytest.mark.asyncio
async def test_a_change_with_no_draft_before_it_keeps_the_general_note() -> None:
    recent = [
        SimpleNamespace(role="user", content="best pizza in Rome?"),
        SimpleNamespace(role="assistant", content="Try **Pizzarium** near the Vatican."),
    ]
    ctx = _turn("and in Naples?", _read(follow="change"), "rules", recent)
    await decide_from_the_read(ctx, _SETTINGS)
    assert ctx.prompt_messages[-2]["content"] == FOLLOW_NOTES["change"]

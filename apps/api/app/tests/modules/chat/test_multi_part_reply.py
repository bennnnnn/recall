"""The server's part of a multi-part reply: a settings card and a picture beside the answer.

"Switch to dark mode and tell me a joke" used to lose the switch, and "switch to dark
mode, and also what is the capital of France?" the question. "Draw a cat wearing a
hat and also explain what a black hole is" drew nothing (I4).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.modules.chat.finalize_parts import add_settings_card, attach_reply_picture
from app.modules.chat.finalize_passes import FinalizeState
from app.modules.chat.turn_intercepts import start_reply_picture
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.modules.chat.turn_prep.instant import resolve_instant_reply, settings_card
from app.modules.chat.turn_prep.intents import plan_turn
from app.modules.images.generation import ImageGenerationError
from app.modules.images.reply_picture import ReplyPicture

_CARD = 'I can switch that for you: Appearance → Dark.\n\n```settings_proposal\n{"proposal_id": "p"}\n```'


def _state(text: str, **ctx_fields: Any) -> FinalizeState:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "x"}],
        run_title=False,
        user_message_content="x",
        reserved_tokens=0,
        max_output_tokens=0,
        **ctx_fields,
    )
    return FinalizeState(
        deps=MagicMock(),
        settings=Settings(),
        ctx=ctx,
        raw=text,
        text=text,
        usage={},
        outcome=TurnOutcome(),
        was_cancelled=False,
        assistant_parts=[text],
        should_cancel=None,
    )


def test_the_settings_card_goes_under_the_answer() -> None:
    state = _state("Why did the scarecrow win an award? He was outstanding in his field.")
    state.ctx.settings_card = _CARD
    text = add_settings_card(state)
    assert text.startswith("Why did the scarecrow")
    assert text.endswith("```")
    assert "```settings_proposal" in text
    assert state.committed == text


def test_a_card_the_model_wrote_is_dropped_for_the_servers() -> None:
    forged = 'Sure!\n\n```settings_proposal\n{"proposal_id": "made-up"}\n```\n\nA joke.'
    state = _state(forged, settings_card=_CARD)
    text = add_settings_card(state)
    assert "made-up" not in text
    assert text.count("```settings_proposal") == 1


def test_no_card_leaves_the_reply_alone() -> None:
    state = _state("Just an answer.")
    assert add_settings_card(state) == "Just an answer."
    assert state.committed is None


async def _drawn(picture_id: UUID) -> UUID:
    return picture_id


@pytest.mark.asyncio
async def test_the_picture_goes_above_the_answer_and_is_linked() -> None:
    picture_id, photo_id = uuid4(), uuid4()
    task = asyncio.ensure_future(_drawn(picture_id))
    state = _state(
        "A black hole is a region where gravity...",
        reply_picture=ReplyPicture("cat wearing a hat", task=task),
        answer_photo_ids=[photo_id],
    )
    text = await attach_reply_picture(state)
    assert text.startswith(f"[Image: /attachments/{picture_id}/file]\n\nA black hole")
    assert state.ctx.answer_photo_ids == [photo_id, picture_id]
    assert state.committed == text


@pytest.mark.asyncio
async def test_a_refused_picture_says_why_in_one_line() -> None:
    state = _state(
        "A black hole is...",
        reply_picture=ReplyPicture.refused("cat wearing a hat", "Upgrade for it."),
    )
    text = await attach_reply_picture(state)
    assert text.startswith("A black hole is...")
    assert text.endswith(
        "I couldn't draw the picture (cat wearing a hat) this time: Upgrade for it."
    )
    assert state.ctx.answer_photo_ids == []


@pytest.mark.asyncio
async def test_a_failed_picture_says_so_and_links_nothing() -> None:
    async def fail() -> UUID:
        raise ImageGenerationError("Daily limit reached", status_code=429)

    state = _state(
        "Answer.", reply_picture=ReplyPicture("a fox", task=asyncio.ensure_future(fail()))
    )
    text = await attach_reply_picture(state)
    assert "I couldn't draw the picture (a fox) this time: Daily limit reached." in text
    assert state.ctx.answer_photo_ids == []


@pytest.mark.asyncio
async def test_a_stopped_reply_cancels_its_picture() -> None:
    started = asyncio.Event()

    async def slow() -> UUID:
        started.set()
        await asyncio.sleep(60)
        return uuid4()

    task = asyncio.ensure_future(slow())
    await started.wait()
    state = _state("Partial", reply_picture=ReplyPicture("a fox", task=task))
    state.was_cancelled = True
    assert await attach_reply_picture(state) == "Partial"
    await asyncio.sleep(0)
    assert task.cancelled()


def _deps(*, can_use: bool) -> Any:
    return SimpleNamespace(plan=SimpleNamespace(can_use=lambda *_a: can_use))


def test_start_reply_picture_only_for_a_picture_part() -> None:
    user = User(id=uuid4(), plan="pro")
    settings = Settings()
    for text in ("draw a cat wearing a hat", "explain what a black hole is"):
        assert (
            start_reply_picture(
                _deps(can_use=True), settings, user=user, chat_id=uuid4(), content=text
            )
            is None
        )


def test_start_reply_picture_refuses_without_the_plan() -> None:
    picture = start_reply_picture(
        _deps(can_use=False),
        Settings(),
        user=User(id=uuid4(), plan="pro"),
        chat_id=uuid4(),
        content="draw a cat wearing a hat and also explain what a black hole is",
    )
    assert picture is not None and picture.subject == "cat wearing a hat"


@pytest.mark.asyncio
async def test_start_reply_picture_draws_the_picture_part() -> None:
    drawn = AsyncMock(return_value=uuid4())
    with patch("app.modules.images.reply_picture.draw_unlinked", drawn):
        picture = start_reply_picture(
            _deps(can_use=True),
            Settings(),
            user=User(id=uuid4(), plan="pro"),
            chat_id=uuid4(),
            content="draw a cat wearing a hat and also explain what a black hole is",
        )
        assert picture is not None
        text, ids = await picture.attach("A black hole...")
    call = drawn.await_args
    assert call is not None and call.kwargs["prompt"] == "cat wearing a hat"
    assert len(ids) == 1 and text.startswith("[Image:")


def _identity() -> Any:
    user = SimpleNamespace(id=uuid4(), locale="en", plan="free")
    return SimpleNamespace(user=user, local_tz="UTC", geo=SimpleNamespace(user_location=None))


@pytest.mark.asyncio
async def test_settings_card_for_the_settings_part() -> None:
    plan = plan_turn("switch to dark mode, and also what is the capital of France?")
    materialize = AsyncMock(return_value=_CARD)
    with patch(
        "app.modules.chat.turn_prep.instant.settings_proposal_service.materialize_settings_reply",
        materialize,
    ):
        card = await settings_card(_identity(), Settings(), AsyncMock(), plan)
    assert card == _CARD
    call = materialize.await_args
    assert call is not None
    changes = call.args[3]
    assert [(change.field, change.value) for change in changes] == [("appearance", "dark")]


@pytest.mark.asyncio
async def test_a_multi_part_message_gets_no_instant_reply() -> None:
    """The settings card used to be the whole reply and drop "what is the capital"."""
    text = "switch to dark mode, and also what is the capital of France?"
    request = SimpleNamespace(content=text, has_image_attachment=False, recent_messages=[])
    reply = await resolve_instant_reply(
        request,  # type: ignore[arg-type]
        _identity(),
        Settings(),
        AsyncMock(),
        plan_turn(text),
    )
    assert reply is None


@pytest.mark.asyncio
async def test_settings_card_is_none_for_one_request() -> None:
    assert (
        await settings_card(_identity(), Settings(), AsyncMock(), plan_turn("switch to dark mode"))
        is None
    )

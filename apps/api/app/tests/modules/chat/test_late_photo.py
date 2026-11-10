"""A reply's photo that was still on its way when the reply went out follows it.

2026-11-09, Galaxy S23: "where is Ethiopia" showed "finding a photo" and then no photo.
The lookup ran past the reply's 6 s wait, and the reply went out with the photo dropped
(``passes_changed: [["answer_photo", -36]]``). Now the reply goes, ``done`` says a photo
follows, and the photo is put on the saved reply and sent after ``done`` when it lands.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from starlette.websockets import WebSocketState

from app.core.config import Settings
from app.modules.chat import late_photo
from app.modules.chat.stream_events import DoneEvent, after_done_events
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.modules.images import answer_photo
from app.modules.images.answer_photo import AnswerPhoto
from app.tests.fakes import FakeSessionCM, fake_session, make_user
from app.tests.modules.chat.chat_test_support import turn_deps

PHOTO_ID = uuid4()
REPLY = "```photo\nEthiopia location map\n```\n\nEthiopia lies in the Horn of Africa."
TEXT = "Ethiopia lies in the Horn of Africa."
MARKER = f"[Image: /attachments/{PHOTO_ID}/file]"


class SlowLookup:
    """``photos_for_answer`` taking ``seconds``; records a stop, as its cleanup would run."""

    def __init__(self, seconds: float, found: list[UUID] | None = None) -> None:
        self.seconds = seconds
        self.found = [PHOTO_ID] if found is None else found
        self.stopped = False

    async def __call__(self, *_args: Any, **_kwargs: Any) -> list[UUID]:
        try:
            await asyncio.sleep(self.seconds)
        except asyncio.CancelledError:
            self.stopped = True
            raise
        return self.found


@pytest.fixture(autouse=True)
def _short_waits(monkeypatch):
    """The reply waits 50 ms for its photo, and a late one has 300 ms from the reply's end."""
    monkeypatch.setattr(answer_photo, "_WAIT_SECONDS", 0.05)
    monkeypatch.setattr(answer_photo, "LATE_PHOTO_SECONDS", 0.3)


async def _late_reply(lookup: SlowLookup) -> AnswerPhoto:
    """A reply whose photo was still on its way when it went out."""
    with patch.object(answer_photo.image_search, "photos_for_answer", lookup):
        photo = AnswerPhoto(Settings(), make_user())
        photo.feed(REPLY)
        text, ids = await photo.attach(REPLY)
    assert (text, ids) == (TEXT, [])
    assert photo.late
    return photo


def _ctx(photo: AnswerPhoto | None) -> StreamContext:
    return StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "where is Ethiopia"}],
        run_title=False,
        user_message_content="where is Ethiopia",
        reserved_tokens=200,
        max_output_tokens=50,
        assistant_message_id=uuid4(),
        answer_photo=photo,
    )


def _deps(session: Any, *, saved_text: str | None = f"{MARKER}\n\n{TEXT}") -> Any:
    return turn_deps(
        session_factory=FakeSessionCM(session),
        messages={"put_above": AsyncMock(return_value=saved_text)},
        attachment_links={"link_to_message": AsyncMock(return_value=1)},
    )


async def _saved() -> asyncio.Task[None]:
    """The reply's commit, already done."""
    task = asyncio.create_task(asyncio.sleep(0))
    await task
    return task


async def test_a_late_photo_is_put_on_the_saved_reply_and_sent_after_done() -> None:
    lookup = SlowLookup(0.1)
    with patch.object(answer_photo.image_search, "photos_for_answer", lookup):
        photo = await _late_reply(lookup)
        ctx, session, outcome = _ctx(photo), fake_session(), TurnOutcome(message_id="reply")
        deps = _deps(session)
        late_photo.follow_late_photo(deps, ctx, await _saved(), outcome)
        assert DoneEvent.from_outcome(outcome).model_dump()["photo_pending"] == "1"
        events = [event async for event in after_done_events(outcome)]

    assert events == [
        {
            "type": "answer_photo",
            "message_id": str(ctx.assistant_message_id),
            "content": f"{MARKER}\n\n{TEXT}",
        }
    ]
    deps.messages.put_above.assert_awaited_once_with(
        session, ctx.assistant_message_id, ctx.chat_id, MARKER
    )
    deps.attachment_links.link_to_message.assert_awaited_once_with(
        session,
        user_id=ctx.user_id,
        attachment_ids=[PHOTO_ID],
        message_id=ctx.assistant_message_id,
        commit=False,
    )
    session.commit.assert_awaited_once()


async def test_a_photo_past_the_limit_is_stopped_and_takes_the_placeholder_away() -> None:
    lookup = SlowLookup(5.0)
    with patch.object(answer_photo.image_search, "photos_for_answer", lookup):
        photo = await _late_reply(lookup)
        ctx, session, outcome = _ctx(photo), fake_session(), TurnOutcome(message_id="reply")
        deps = _deps(session)
        late_photo.follow_late_photo(deps, ctx, await _saved(), outcome)
        assert outcome.photo_task is not None
        event = await asyncio.wait_for(outcome.photo_task, 2.0)

    # No photo: the phone drops its placeholder, and the saved reply was never touched.
    assert event == {
        "type": "answer_photo",
        "message_id": str(ctx.assistant_message_id),
        "content": None,
    }
    assert lookup.stopped
    deps.messages.put_above.assert_not_awaited()
    deps.attachment_links.link_to_message.assert_not_awaited()


async def test_deleting_the_chat_stops_the_search() -> None:
    lookup = SlowLookup(5.0)
    with patch.object(answer_photo.image_search, "photos_for_answer", lookup):
        photo = await _late_reply(lookup)
        ctx, outcome = _ctx(photo), TurnOutcome(message_id="reply")
        deps = _deps(fake_session())
        late_photo.follow_late_photo(deps, ctx, await _saved(), outcome)
        # Another user's chat, or another chat of theirs, leaves it alone.
        assert late_photo.drop_late_photos(uuid4(), ctx.chat_id) == 0
        assert late_photo.drop_late_photos(ctx.user_id, uuid4()) == 0
        assert late_photo.drop_late_photos(ctx.user_id, ctx.chat_id) == 1
        assert outcome.photo_task is not None
        event = await asyncio.wait_for(outcome.photo_task, 1.0)
    assert lookup.stopped
    assert event["content"] is None
    deps.messages.put_above.assert_not_awaited()


async def test_the_chat_service_drops_a_deleted_chats_photos() -> None:
    from app.modules.chat import service

    user, chat_id = make_user(), uuid4()
    session = fake_session()
    with (
        patch("app.modules.conversation.history.get_chat", AsyncMock(return_value=MagicMock())),
        patch.object(service, "drop_late_photos") as drop,
    ):
        await service.delete_chat(session, user, chat_id, settings=Settings())
    drop.assert_called_once_with(user.id, chat_id)


async def test_a_stop_after_the_text_stops_a_photo_still_on_its_way() -> None:
    from app.modules.chat import stream_pipeline
    from app.modules.chat.stream_accum import StreamAccum

    lookup = SlowLookup(5.0)
    with patch.object(answer_photo.image_search, "photos_for_answer", lookup):
        photo = await _late_reply(lookup)
        ctx, outcome = _ctx(photo), TurnOutcome()
        # The whole reply was drawn; the Stop came while its photo was looked up.
        accum = StreamAccum(parts=[TEXT], shown=[TEXT])
        with (
            patch.object(stream_pipeline, "enrich_final_content", AsyncMock(return_value=TEXT)),
            patch.object(stream_pipeline, "await_user_message_persist", AsyncMock()),
            patch.object(stream_pipeline, "register_and_enqueue_finalize", AsyncMock()),
        ):
            await stream_pipeline._settle_reply(
                MagicMock(),
                MagicMock(),
                Settings(),
                ctx,
                usage={},
                accum=accum,
                should_cancel=lambda: True,
                outcome=outcome,
                resources=None,
            )
        await asyncio.sleep(0.01)
    assert not photo.late
    assert lookup.stopped


async def test_an_unsaved_reply_takes_no_photo() -> None:
    lookup = SlowLookup(0.1)
    with patch.object(answer_photo.image_search, "photos_for_answer", lookup):
        photo = await _late_reply(lookup)
        ctx, outcome = _ctx(photo), TurnOutcome(message_id="reply")
        deps = _deps(fake_session())

        async def failed_commit() -> None:
            raise RuntimeError("commit failed")

        saved = asyncio.create_task(failed_commit())
        await asyncio.gather(saved, return_exceptions=True)
        late_photo.follow_late_photo(deps, ctx, saved, outcome)
        assert outcome.photo_task is not None
        event = await asyncio.wait_for(outcome.photo_task, 1.0)
    assert event["content"] is None
    assert lookup.stopped
    deps.messages.put_above.assert_not_awaited()


async def test_a_reply_gone_before_its_photo_landed_is_left_alone() -> None:
    lookup = SlowLookup(0.1)
    with patch.object(answer_photo.image_search, "photos_for_answer", lookup):
        photo = await _late_reply(lookup)
        ctx, session, outcome = _ctx(photo), fake_session(), TurnOutcome(message_id="reply")
        # Its chat was deleted on another machine, or a regenerate replaced it.
        deps = _deps(session, saved_text=None)
        late_photo.follow_late_photo(deps, ctx, await _saved(), outcome)
        assert outcome.photo_task is not None
        event = await asyncio.wait_for(outcome.photo_task, 1.0)
    assert event["content"] is None
    # Linked to nothing: the attachment reaper removes the photo.
    deps.attachment_links.link_to_message.assert_not_awaited()
    session.commit.assert_not_awaited()


async def test_a_photo_in_time_needs_no_follow() -> None:
    lookup = SlowLookup(0.0)
    with patch.object(answer_photo.image_search, "photos_for_answer", lookup):
        photo = AnswerPhoto(Settings(), make_user())
        photo.feed(REPLY)
        text, ids = await photo.attach(REPLY)
    assert (text, ids) == (f"{MARKER}\n\n{TEXT}", [PHOTO_ID])
    outcome = TurnOutcome(message_id="reply")
    late_photo.follow_late_photo(_deps(fake_session()), _ctx(photo), await _saved(), outcome)
    assert outcome.photo_task is None
    assert "photo_pending" not in DoneEvent.from_outcome(outcome).model_dump()


async def test_the_socket_sends_the_late_photo_after_done() -> None:
    from app.modules.chat import ws_turn

    socket = MagicMock(client_state=WebSocketState.CONNECTED)
    socket.send_json = AsyncMock()
    landed = {"type": "answer_photo", "message_id": "reply", "content": f"{MARKER}\n\n{TEXT}"}

    async def photo() -> dict[str, Any]:
        await asyncio.sleep(0.01)
        return landed

    task = asyncio.create_task(photo())
    ws_turn.schedule_after_done(socket, TurnOutcome(message_id="reply", photo_task=task))
    await asyncio.wait_for(task, 1.0)
    for _ in range(5):
        await asyncio.sleep(0)
    socket.send_json.assert_awaited_once_with(landed)


def test_a_reply_still_saving_says_no_photo_follows() -> None:
    outcome = TurnOutcome(message_id="reply", photo_task=MagicMock())
    assert "photo_pending" not in DoneEvent.from_outcome(outcome, persisting=True).model_dump()

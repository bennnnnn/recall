"""A reply's photo that was still on its way when the reply went out.

``AnswerPhoto.attach`` waits a few seconds for the photo above an answer. Past that the
reply is saved without it and ``done`` says a photo follows (``photo_pending``). Here
the search is waited for (``AnswerPhoto.follow``, up to ``LATE_PHOTO_SECONDS`` from the
reply's end), the photo is put above the saved reply and linked to it, and the turn's
stream sends an ``answer_photo`` event after ``done``: the reply's new text, or none when
no photo came, which takes the phone's placeholder away. A phone that missed the event
reads the saved reply later, photo and all; the saved reply never holds a placeholder.

A Stop after the text (``stream_pipeline``) or a deleted chat (``drop_late_photos``) drops
the search; its stored bytes and the day's lookup are given back as on any failure. A
reply gone by the time its photo lands (its chat deleted on another machine, a
regenerate) is left alone, and the photo, linked to nothing, goes to the attachment
reaper.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.background_tasks import create_background_task
from app.modules.attachments.markers import image_marker

if TYPE_CHECKING:
    from app.modules.chat.turn_deps import ChatTurnDeps
    from app.modules.chat.turn_outcome import TurnOutcome
    from app.modules.chat.turn_prep import StreamContext
    from app.modules.images.answer_photo import AnswerPhoto

logger = logging.getLogger(__name__)

# chat id -> (user id, photo) for each search still following a reply on this machine.
_following: dict[UUID, list[tuple[UUID, AnswerPhoto]]] = {}


def build_answer_photo_event(message_id: UUID, content: str | None) -> dict[str, Any]:
    """The reply's text with its late photo above it, or None when no photo came."""
    return {"type": "answer_photo", "message_id": str(message_id), "content": content}


def follow_late_photo(
    deps: ChatTurnDeps,
    ctx: StreamContext,
    saved: asyncio.Task[None],
    outcome: TurnOutcome | None,
) -> None:
    """When the reply went out with its photo still on its way: wait for the photo after
    the reply's commit (``saved``) and put it on the reply (``outcome.photo_task``)."""
    photo = ctx.answer_photo
    message_id = ctx.assistant_message_id
    if photo is None or not photo.late or message_id is None:
        return
    entry = (ctx.user_id, photo)
    chat_id = ctx.chat_id
    _following.setdefault(chat_id, []).append(entry)
    task = create_background_task(
        _deliver(deps, chat_id, ctx.user_id, message_id, photo, saved), name="late_answer_photo"
    )
    task.add_done_callback(lambda _done: _forget(chat_id, entry))
    if outcome is not None:
        outcome.photo_task = task


def _forget(chat_id: UUID, entry: tuple[UUID, AnswerPhoto]) -> None:
    entries = _following.get(chat_id, [])
    if entry in entries:
        entries.remove(entry)
    if not entries:
        _following.pop(chat_id, None)


def drop_late_photos(user_id: UUID, chat_id: UUID | None = None) -> int:
    """Stop the searches still following this user's replies in ``chat_id`` (every chat of
    theirs when None): the chat was deleted. How many were stopped."""
    dropped = 0
    for followed_chat, entries in list(_following.items()):
        if chat_id is not None and followed_chat != chat_id:
            continue
        for owner, photo in entries:
            if owner == user_id:
                photo.cancel()
                dropped += 1
    return dropped


async def _deliver(
    deps: ChatTurnDeps,
    chat_id: UUID,
    user_id: UUID,
    message_id: UUID,
    photo: AnswerPhoto,
    saved: asyncio.Task[None],
) -> dict[str, Any]:
    try:
        await asyncio.shield(saved)
    except BaseException as exc:
        # No saved reply to put a photo on: the search stops, and its cleanup runs.
        photo.cancel()
        if not isinstance(exc, Exception):
            raise
        return build_answer_photo_event(message_id, None)
    ids = await photo.follow()
    content = await _put_on_reply(deps, chat_id, user_id, message_id, ids) if ids else None
    return build_answer_photo_event(message_id, content)


async def _put_on_reply(
    deps: ChatTurnDeps, chat_id: UUID, user_id: UUID, message_id: UUID, ids: list[UUID]
) -> str | None:
    """The photo above the saved reply and linked to it, in one commit; the reply's new
    text, or None when the reply is gone or the write failed."""
    marker = "\n".join(image_marker(attachment_id) for attachment_id in ids)
    try:
        async with deps.session_factory() as session:
            content = await deps.messages.put_above(session, message_id, chat_id, marker)
            if content is None:
                return None
            await deps.attachment_links.link_to_message(
                session, user_id=user_id, attachment_ids=ids, message_id=message_id, commit=False
            )
            await session.commit()
    except Exception:
        logger.exception("Putting a late answer photo on its reply failed")
        return None
    return content


async def answer_photo_event(task: asyncio.Task[dict[str, Any]]) -> dict[str, Any] | None:
    """The ``answer_photo`` event once the late photo is in or given up (``done`` is on the
    wire); None when its wait was stopped (the server is shutting down)."""
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        if task.cancelled():
            return None
        raise
    except Exception:
        logger.warning("Late answer photo failed", exc_info=True)
        return None

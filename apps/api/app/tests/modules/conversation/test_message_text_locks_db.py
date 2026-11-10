"""A reply's text rewritten while its late photo is put above it keeps both (real Postgres).

Review 2026-11-09: the email draft edit and a to-do card's tap read a reply's whole text and
wrote it back without the row lock ``put_above`` takes. A read before the photo's commit and a
write after it dropped the photo's marker: the photo stayed linked and was never shown. Every
writer that rewrites the text from a read of it now reads it under the row lock.

Two connections, as two requests have: the photo's write holds the lock, uncommitted, while
the other writer starts; the other must wait and then edit the text with the photo in it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.core.db import SessionLocal, engine
from app.models.orm import Message, User
from app.modules.account import lifecycle as account_lifecycle
from app.modules.chat import service as chats_service
from app.modules.conversation import chats_repository, history
from app.modules.conversation import service as conversation_service
from app.tests.fakes import make_user, redis_mock

MARKER = f"[Image: /attachments/{uuid4()}/file]"
EMAIL = "Here is a draft.\n\n```email\nTo: a@b.com\nSubject: Hi\n\nHello\n```"
CARD = "Saved?\n\n```reminder_card\nCall mom\n```"


@pytest.fixture
async def reply() -> AsyncIterator[tuple[UUID, UUID, UUID]]:
    """A committed chat with one reply: (user id, chat id, message id); erased afterwards."""
    await engine.dispose(close=False)
    async with SessionLocal() as session:
        user = User(email=f"{uuid4()}@example.com", name="Text locks", google_sub=str(uuid4()))
        session.add(user)
        await session.flush()
        chat = await chats_repository.create(session, user_id=user.id, model="free-chat")
        message = Message(chat_id=chat.id, user_id=user.id, role="assistant", content="")
        session.add(message)
        await session.commit()
        ids = (user.id, chat.id, message.id)
    try:
        yield ids
    finally:
        async with SessionLocal() as session:
            await account_lifecycle.erase_user_rows(session, ids[0])
        await engine.dispose(close=False)


async def _set_text(message_id: UUID, chat_id: UUID, text: str) -> None:
    async with SessionLocal() as session:
        message = await history.message_in_chat(session, message_id, chat_id)
        assert message is not None
        message.content = text
        await session.commit()


async def _text(message_id: UUID, chat_id: UUID) -> str:
    async with SessionLocal() as session:
        message = await history.message_in_chat(session, message_id, chat_id)
        assert message is not None
        return message.content


async def _while_the_photo_lands(
    chat_id: UUID, message_id: UUID, rewrite: Callable[[Any], Coroutine[Any, Any, object]]
) -> None:
    """``rewrite`` starts while the photo's write holds the reply's lock, uncommitted."""
    async with SessionLocal() as photo:
        assert await conversation_service.put_above_reply(photo, message_id, chat_id, MARKER)
        async with SessionLocal() as other:
            writing: asyncio.Task[object] = asyncio.create_task(rewrite(other))
            await asyncio.sleep(0.3)
            # It waits for the lock instead of acting on the text from before the photo.
            assert not writing.done()
            await photo.commit()
            await asyncio.wait_for(writing, 5.0)


@pytest.mark.asyncio
async def test_an_email_draft_edited_as_the_photo_lands_keeps_the_photo(
    reply: tuple[UUID, UUID, UUID],
) -> None:
    user_id, chat_id, message_id = reply
    await _set_text(message_id, chat_id, EMAIL)

    async def edit(session: Any) -> object:
        return await chats_service.update_message_email(
            session,
            redis_mock(),
            make_user(id=user_id),
            chat_id,
            message_id,
            to="b@c.com",
            subject="Bye",
            body="Shorter",
        )

    await _while_the_photo_lands(chat_id, message_id, edit)

    text = await _text(message_id, chat_id)
    assert text.startswith(MARKER)
    assert "Subject: Bye" in text and "Shorter" in text and "Hello" not in text


@pytest.mark.asyncio
async def test_a_card_saved_as_the_photo_lands_keeps_the_photo(
    reply: tuple[UUID, UUID, UUID],
) -> None:
    _user_id, chat_id, message_id = reply
    await _set_text(message_id, chat_id, CARD)

    async def save(session: Any) -> object:
        return await conversation_service.edit_recent_reply(
            session,
            chat_id,
            containing="```reminder_card",
            edit=lambda text: text.replace("Call mom", "Call mom (saved)"),
        )

    await _while_the_photo_lands(chat_id, message_id, save)

    text = await _text(message_id, chat_id)
    assert text.startswith(MARKER)
    assert "Call mom (saved)" in text

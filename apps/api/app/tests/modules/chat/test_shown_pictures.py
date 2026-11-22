"""A picture the app showed reads, as history, as what it was (owner's chat, 2026-11-22).

Read back as a bare ``[Image: /attachments/…]`` line, a painted picture told the reply's
model nothing: asked "What image is that?" it answered "I can't see any image… I've been
sending stray image markers". The turn's read could not tell a picture had been shown at
all. Each such line is now said in words, with the prompt it was drawn from or the photo
searched for.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core import readings
from app.modules.attachments.markers import image_marker
from app.modules.chat import shown_pictures
from app.modules.chat.prompt_window import PromptWindow, history_messages
from app.modules.chat.shown_pictures import ShownPicture
from app.modules.chat.tool_loop.selection import spent_tools
from app.modules.chat.turn_decision import earlier_turns

PAINTED, FOUND, ABOVE = uuid4(), uuid4(), uuid4()
LABELS = {
    PAINTED: ShownPicture("generated", "a cat wearing a hat"),
    FOUND: ShownPicture("search", "Eiffel Tower"),
    ABOVE: ShownPicture("search", "Recall AI assistant"),
}


def _row(role: str, content: str, model: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=role, content=content, model=model)


CHAT = [
    _row("user", "draw me a cat wearing a hat"),
    _row("assistant", image_marker(PAINTED), "image-gen-model"),
    _row("user", "show me the Eiffel Tower"),
    _row("assistant", image_marker(FOUND), "image-search-model"),
    _row("user", "What is ur name"),
    _row("assistant", f"{image_marker(ABOVE)}\n\nI'm Recall, your assistant.", "free-chat"),
]


def test_each_picture_is_said_with_what_it_showed() -> None:
    said = [shown_pictures.as_text(r.content, model=r.model, pictures=LABELS) for r in CHAT[1::2]]
    assert said == [
        '(Shown here: a picture the app generated for the user from the prompt "a cat wearing'
        ' a hat".)',
        '(Shown here: a photo the app found for the user of "Eiffel Tower".)',
        '(Shown here: a photo the app found for the user of "Recall AI assistant".)\n\n'
        "I'm Recall, your assistant.",
    ]


def test_a_picture_with_no_label_is_said_by_its_reply_s_model() -> None:
    said = [shown_pictures.as_text(r.content, model=r.model, pictures={}) for r in CHAT[1::2]]
    assert said[0] == "(Shown here: a picture the app generated for the user.)"
    assert said[1] == "(Shown here: a photo the app found for the user.)"
    assert said[2].startswith("(Shown here: a picture.)")
    assert "[Image:" not in "".join(said)


def test_text_without_a_picture_is_kept_as_it_is() -> None:
    text = "A plain reply. [Image: not a marker]"
    assert shown_pictures.as_text(text, model="free-chat", pictures=LABELS) == text


def test_the_reply_s_prompt_reads_each_picture_in_words() -> None:
    window = PromptWindow(recent=list(CHAT), gap=[], exchange=list(CHAT), pictures=LABELS)
    messages = history_messages(window, math_followup=False)
    replies = [m["content"] for m in messages if m["role"] == "assistant"]
    assert "a cat wearing a hat" in replies[0] and "[Image:" not in replies[0]
    assert '"Eiffel Tower"' in replies[1]
    # The user's own rows are kept: their photos load for the model as they did.
    assert [m["content"] for m in messages if m["role"] == "user"] == [
        r.content for r in CHAT if r.role == "user"
    ]


def test_the_turn_s_read_sees_the_picture_too() -> None:
    quoted = earlier_turns(CHAT[:2], LABELS)
    assert quoted[-1] == (
        "assistant",
        '(Shown here: a picture the app generated for the user from the prompt "a cat '
        'wearing a hat".)',
    )


def test_only_the_assistant_s_pictures_are_read() -> None:
    upload = uuid4()
    rows = [_row("user", image_marker(upload)), *CHAT[:2]]
    assert shown_pictures.picture_ids(rows) == [PAINTED]


@pytest.mark.asyncio
async def test_the_labels_are_read_once_a_turn_and_never_fail_it() -> None:
    readings.begin_turn()
    attachment = SimpleNamespace(id=PAINTED, source="generated", original_filename="a cat")
    get = AsyncMock(return_value=[attachment])
    with (
        patch("app.core.db.SessionLocal", _Session),
        patch("app.modules.attachments.service.get_by_ids", get),
    ):
        task = shown_pictures.start_labels(uuid4(), CHAT[:2])
        assert task is not None
        assert await shown_pictures.labels_for_turn() == {
            PAINTED: ShownPicture("generated", "a cat")
        }
    get.assert_awaited_once()
    assert get.await_args is not None and get.await_args.args[1] == [PAINTED]
    # No picture in the chat: nothing is read.
    assert shown_pictures.start_labels(uuid4(), [_row("user", "hi")]) is None


@pytest.mark.asyncio
async def test_a_failed_label_read_leaves_the_lines_said_by_their_model() -> None:
    readings.begin_turn()
    with patch("app.modules.attachments.service.get_by_ids", AsyncMock(side_effect=OSError)):
        with patch("app.core.db.SessionLocal", _Session):
            task = shown_pictures.start_labels(uuid4(), CHAT[:2])
    assert await shown_pictures.settled_labels(task) == {}


class _Session:
    async def __aenter__(self) -> Any:
        return object()

    async def __aexit__(self, *_args: object) -> None:
        return None


def test_a_picture_the_read_turned_down_is_no_tool_either() -> None:
    assert "generate_image" in spent_tools(
        solve_timed_out=False, photo_missed=False, picture_declined=True
    )
    assert "generate_image" not in spent_tools(solve_timed_out=False, photo_missed=False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "picture, paints",
    [("image", True), ("none", False), ("photo", False), (None, False)],
)
async def test_a_picture_beside_the_reply_is_painted_only_when_the_read_asks(
    picture: str | None, paints: bool
) -> None:
    """ "Draw a cat wearing a hat and also explain what a black hole is": the words find the
    picture part, the read decides it."""
    from app.modules.chat.drawn_picture import read_paints_none
    from app.tests.modules.chat.chat_test_support import picture_read

    read: asyncio.Future[Any] | None = picture_read(picture) if picture is not None else None
    assert await read_paints_none(read, None) is not paints

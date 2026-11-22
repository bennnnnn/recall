"""Only the turn's read paints a picture or looks a photo up (owner's chat, 2026-11-22).

After the app showed one picture, "No you displayed an image", "You keep generating an
image", "What?🤔 did i ask about an image?" and "Man this is so bad" were each answered by
another painting, decided by word rules before any model read them. The words now only find
what a message could ask of images; the read says whether it asks for a picture
(``drawn_picture.read_asks``), and a read with no answer paints nothing.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.attachments.markers import image_marker
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_intercepts import intercept_new_turn, intercept_regenerate
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import RegenerateBackup
from app.tests.fakes import make_user
from app.tests.modules.chat.chat_test_support import offline_deps, picture_read, turn_deps

pytestmark = pytest.mark.asyncio

_PICTURE = uuid4()
# A chat whose last reply is a picture the app painted.
AFTER_PICTURE = [
    SimpleNamespace(id=uuid4(), role="user", content="draw me a cat wearing a hat", model=None),
    SimpleNamespace(
        id=uuid4(), role="assistant", content=image_marker(_PICTURE), model="image-gen-model"
    ),
]
OWNER_LINES = [
    "No you displayed an image",
    "You keep generating an image",
    "What?🤔 did i ask about an image?",
    "Man this is so bad",
    "why are you doing this",
    "What image is that?",
]


def _kwargs(mock: AsyncMock) -> dict[str, Any]:
    assert mock.await_args is not None
    return dict(mock.await_args.kwargs)


def _saved(model: str) -> AsyncMock:
    reply = MagicMock()
    reply.id, reply.content, reply.model = uuid4(), image_marker(uuid4()), model
    return AsyncMock(return_value=(MagicMock(), reply))


async def _turn(
    content: str,
    read: asyncio.Future[TurnDecision | None] | None,
    *,
    recent: list[Any] | None = None,
) -> tuple[bool, AsyncMock, AsyncMock, set[str]]:
    paint, search = _saved("image-gen-model"), _saved("image-search-model")
    deps = turn_deps(
        image_generation={"generate_for_chat": paint},
        image_search={"search_and_attach_for_chat": search},
        plan={"can_use": MagicMock(return_value=True)},
    )
    misses: set[str] = set()
    rows = list(recent or [])
    handled = await intercept_new_turn(
        deps,
        Settings(image_search_enabled=True, image_generation_enabled=True),
        user=make_user(plan="pro"),
        chat_id=uuid4(),
        content=content,
        outcome=TurnOutcome(),
        recent_messages=rows,
        prior_count=len(rows),
        misses=misses,
        read=read,
    )
    return handled, paint, search, misses


@pytest.mark.parametrize("content", OWNER_LINES)
@pytest.mark.parametrize("picture", ["none", "diagram", None])
async def test_the_owner_s_lines_after_a_picture_paint_nothing(
    content: str, picture: str | None
) -> None:
    read = picture_read(picture) if picture is not None else None
    handled, paint, _search, misses = await _turn(content, read, recent=AFTER_PICTURE)
    assert handled is False
    paint.assert_not_awaited()
    # The reply's tool loop is offered no picture on words the read turned down.
    assert "image" in misses


async def test_a_change_to_the_last_picture_paints_it_again_when_the_read_asks() -> None:
    handled, paint, _search, _misses = await _turn(
        "make it blue", picture_read("image"), recent=AFTER_PICTURE
    )
    assert handled is True
    kwargs = _kwargs(paint)
    assert kwargs["prompt"] == "cat wearing a hat, blue"
    assert kwargs["reference_attachment_ids"] == [_PICTURE]


@pytest.mark.parametrize(
    "content, prompt",
    [
        ("draw me a cat wearing a hat", "cat wearing a hat"),
        ("sketch a cozy cabin in the snow", "sketch a cozy cabin in the snow"),
        ("show me a dragon breathing fire", "dragon breathing fire"),
    ],
)
async def test_a_picture_is_painted_only_when_the_read_asks_for_one(
    content: str, prompt: str
) -> None:
    for read in (None, picture_read("none"), picture_read("diagram", "maths")):
        handled, paint, search, misses = await _turn(content, read)
        assert handled is False
        paint.assert_not_awaited()
        search.assert_not_awaited()
        assert {"image", "photo"} <= misses
    handled, paint, search, _misses = await _turn(content, picture_read("image"))
    assert handled is True
    assert _kwargs(paint)["prompt"] == prompt
    search.assert_not_awaited()


@pytest.mark.parametrize(
    "content, query",
    [
        ("show me a photo of the Eiffel Tower", "Eiffel Tower"),
        ("what does a capybara look like", "capybara"),
        ("show me a picture of Albert Einstein", "Albert Einstein"),
    ],
)
async def test_a_photo_is_looked_up_only_when_the_read_asks_for_one(
    content: str, query: str
) -> None:
    for read in (None, picture_read("none"), picture_read("graph", "physics")):
        handled, paint, search, _misses = await _turn(content, read)
        assert handled is False
        search.assert_not_awaited()
        paint.assert_not_awaited()
    handled, paint, search, _misses = await _turn(content, picture_read("photo"))
    assert handled is True
    assert _kwargs(search)["query"] == query
    paint.assert_not_awaited()


async def test_a_plain_message_never_waits_for_the_read() -> None:
    """No word could ask for a picture: the read still out is not waited for."""
    never: asyncio.Future[TurnDecision | None] = asyncio.get_running_loop().create_future()
    handled, paint, search, misses = await asyncio.wait_for(
        _turn("what is the capital of France?", never), timeout=1
    )
    assert handled is False and not misses
    paint.assert_not_awaited()
    search.assert_not_awaited()


async def test_a_read_still_out_paints_nothing() -> None:
    """A read that has not answered by its own budget is no answer."""
    never: asyncio.Future[TurnDecision | None] = asyncio.get_running_loop().create_future()
    settings = Settings(live_read_timeout_seconds=0.05)
    paint = _saved("image-gen-model")
    deps = turn_deps(
        image_generation={"generate_for_chat": paint},
        plan={"can_use": MagicMock(return_value=True)},
    )
    handled = await asyncio.wait_for(
        intercept_new_turn(
            deps,
            settings,
            user=make_user(plan="pro"),
            chat_id=uuid4(),
            content="draw me a cat",
            outcome=TurnOutcome(),
            recent_messages=[],
            prior_count=0,
            read=never,
        ),
        timeout=2,
    )
    assert handled is False
    paint.assert_not_awaited()


@pytest.mark.parametrize("picture, painted", [("none", False), ("image", True), (None, False)])
async def test_regenerating_a_picture_asks_the_read_too(picture: str | None, painted: bool) -> None:
    """A picture painted by mistake for "Man this is so bad" is answered in words when
    regenerated; a real request paints again."""
    paint = _saved("image-gen-model")
    deps = offline_deps(
        image_generation={"generate_for_chat": paint, "image_reference_ids": lambda _c: []},
        plan={"can_use": MagicMock(return_value=True)},
        messages={"get_by_id": AsyncMock(return_value=None)},
    )
    handled = await intercept_regenerate(
        deps,
        Settings(),
        user=make_user(plan="pro"),
        chat_id=uuid4(),
        content="Man this is so bad",
        backup=RegenerateBackup(content="[Image]", model="image-gen-model", message_id=uuid4()),
        outcome=TurnOutcome(),
        read=picture_read(picture) if picture is not None else None,
        recent_messages=list(AFTER_PICTURE),
    )
    assert handled is painted
    assert paint.await_count == int(painted)

"""A maths figure is the app's drawing, never a painted picture or a photo of one.

"Draw a regular pentagon with sides of 3 cm" and "Draw a cube." read as picture requests to
the image words, and "Show x ≥ 4 on a number line" as a photo to look up. The turn's read
says what the message asks to see: a maths diagram or graph is drawn by the app from the
question's values (``chat.figure_turn``), so neither intercept takes it. Since 2026-11-22
the read is the only thing that paints or looks a photo up at all (``drawn_picture``).
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_intercepts import intercept_new_turn
from app.modules.chat.turn_outcome import TurnOutcome
from app.tests.fakes import make_user
from app.tests.modules.chat.chat_test_support import picture_read, turn_deps


def _saved(model: str) -> AsyncMock:
    asst = MagicMock()
    asst.id, asst.content, asst.model = uuid4(), "[Image: /attachments/x/file]", model
    return AsyncMock(return_value=(MagicMock(), asst))


def _user() -> Any:
    return make_user(plan="pro")


async def _intercepts(
    content: str, read: asyncio.Future[TurnDecision | None] | None
) -> tuple[bool, AsyncMock, AsyncMock]:
    paint, search = _saved("image-gen-model"), _saved("image-search-model")
    deps = turn_deps(
        plan={"can_use": MagicMock(return_value=True)},
        image_generation={"generate_for_chat": paint},
        image_search={"search_and_attach_for_chat": search},
    )
    handled = await intercept_new_turn(
        deps,
        Settings(image_search_enabled=True),
        user=_user(),
        chat_id=uuid4(),
        content=content,
        outcome=TurnOutcome(),
        recent_messages=[],
        prior_count=0,
        read=read,
    )
    return handled, paint, search


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    ["Draw a regular pentagon with sides of 3 cm.", "Draw a cube.", "Draw a hexagon"],
)
async def test_a_maths_figure_is_not_painted(content: str) -> None:
    for read in (None, picture_read("diagram", "maths")):
        handled, paint, _search = await _intercepts(content, read)
        assert handled is False
        paint.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("subject", ["everyday", "maths"])
async def test_a_painting_the_read_calls_one_is_still_painted(subject: str) -> None:
    handled, paint, _search = await _intercepts("Draw a cube.", picture_read("image", subject))
    assert handled is True
    paint.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_number_line_is_not_a_photo() -> None:
    content = "Show x ≥ 4 on a number line."
    for read in (None, picture_read("graph", "maths")):
        handled, _paint, search = await _intercepts(content, read)
        assert handled is False
        search.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content, subject, picture, photo",
    [
        # Grade 8 round, t10: after a car's acceleration, stock photos of "this motion".
        ("show me an animation of this motion", "physics", "diagram", False),
        ("show me the forces on the block", "physics", "diagram", False),
        ("show me a photo of a real hydraulic press", "physics", "photo", True),
        ("show me an ear", "everyday", "photo", True),
        ("what does a koala look like", "everyday", "photo", True),
        ("what does a koala look like", "everyday", "none", False),
    ],
)
async def test_a_photo_is_the_read_s_never_the_words(
    content: str, subject: str, picture: str, photo: bool
) -> None:
    handled, _paint, search = await _intercepts(content, picture_read(picture, subject))
    assert handled is photo
    assert search.await_count == int(photo)

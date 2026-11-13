"""A maths figure is the app's drawing, never a painted picture or a photo of one.

"Draw a regular pentagon with sides of 3 cm" and "Draw a cube." read as picture requests to
the image words, and "Show x ≥ 4 on a number line" as a photo to look up. The turn's read
says what the message asks to see: a maths diagram or graph is drawn by the app from the
question's values (``chat.figure_turn``), so neither intercept takes it.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_intercepts import try_image_gen_for_turn, try_image_lookup_for_turn
from app.modules.chat.turn_outcome import TurnOutcome
from app.tests.fakes import make_user
from app.tests.modules.chat.chat_test_support import turn_deps


def _read(subject: str, picture: str) -> asyncio.Task[TurnDecision | None]:
    # Read as the model's JSON is: the schema checks the two names.
    decision = TurnDecision.model_validate(
        {"live": False, "think": False, "subject": subject, "picture": picture}
    )

    async def answer() -> TurnDecision | None:
        return decision

    return asyncio.ensure_future(answer())


def _found() -> AsyncMock:
    asst = MagicMock()
    asst.id, asst.content, asst.model = (
        uuid4(),
        "[Image: /attachments/x/file]",
        "image-search-model",
    )
    return AsyncMock(return_value=(MagicMock(), asst))


def _user() -> Any:
    return make_user(plan="pro")


async def _paints(content: str, read: asyncio.Task[TurnDecision | None] | None) -> bool:
    generate = AsyncMock(side_effect=RuntimeError("stop before painting"))
    deps = turn_deps(
        plan={"can_use": MagicMock(return_value=True)},
        image_generation={"generate_for_chat": generate},
        messages={"list_recent": AsyncMock(return_value=[])},
    )
    try:
        await try_image_gen_for_turn(
            deps,
            Settings(),
            user=_user(),
            chat_id=uuid4(),
            content=content,
            outcome=None,
            create_user_message=True,
            skip_revision_lookup=True,
            read=read,
        )
    except RuntimeError:
        return True
    return False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    ["Draw a regular pentagon with sides of 3 cm.", "Draw a cube.", "Draw a hexagon"],
)
async def test_a_maths_figure_is_not_painted(content: str) -> None:
    assert await _paints(content, None)  # the image words alone would paint it
    assert not await _paints(content, _read("maths", "diagram"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "subject, picture",
    [("everyday", "image"), ("maths", "image"), ("everyday", "diagram")],
)
async def test_a_painting_the_read_calls_one_is_still_painted(subject: str, picture: str) -> None:
    assert await _paints("Draw a cube.", _read(subject, picture))


async def _looks_up(content: str, read: asyncio.Task[TurnDecision | None] | None) -> bool:
    search = _found()
    deps = turn_deps(image_search={"search_and_attach_for_chat": search})
    misses: set[str] = set()
    handled = await try_image_lookup_for_turn(
        deps,
        Settings(image_search_enabled=True),
        user=_user(),
        chat_id=uuid4(),
        content=content,
        outcome=TurnOutcome(),
        create_user_message=True,
        recent_messages=[],
        misses=misses,
        read=read,
    )
    return handled


@pytest.mark.asyncio
async def test_a_number_line_is_not_a_photo() -> None:
    content = "Show x ≥ 4 on a number line."
    assert await _looks_up(content, None)
    assert not await _looks_up(content, _read("maths", "graph"))


@pytest.mark.asyncio
async def test_a_photo_with_no_maths_in_its_query_never_waits_for_the_read() -> None:
    async def never() -> TurnDecision | None:
        await asyncio.sleep(30)
        return None

    read = asyncio.ensure_future(never())
    try:
        assert await asyncio.wait_for(_looks_up("show me an ear", read), timeout=2)
    finally:
        read.cancel()

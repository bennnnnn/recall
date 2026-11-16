"""A picture the app draws itself gets no photo and no painting (live, 2026-11-15).

"A 12 V battery is connected to a 4 Ω and a 2 Ω resistor in series. Find the current and
draw the circuit" put a painted circuit above the server's schematic; "How far does it
travel before landing? Show the path." looked a photo up for the path. The read and the
subject's solve decide, never the words.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.modules.chat.drawn_picture import (
    app_draws_the_picture,
    asks_for_a_drawing,
    solve_draws_a_picture,
)
from app.modules.chat.finalize_parts import attach_reply_picture
from app.modules.chat.finalize_passes import FinalizeState
from app.modules.chat.finalize_text import attach_answer_photo
from app.modules.chat.prompt_constants.multi_part import (
    PROBLEM_PICTURE_NOTE,
    multi_part_contract,
)
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_intercepts import start_reply_picture
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.modules.chat.turn_prep.intents import plan_turn
from app.modules.images.answer_photo import AnswerPhoto
from app.modules.images.reply_picture import ReplyPicture
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.services.picture_copy import PICTURE_PLACEMENT_RULE

CIRCUIT = (
    "A 12 V battery is connected to a 4 Ω and a 2 Ω resistor in series. "
    "Find the current and draw the circuit."
)
PATH = (
    "A ball is thrown at 20 m/s at 30° above the horizontal. How far does it travel "
    "before landing? Show the path."
)


def _read(subject: str, picture: str) -> TurnDecision:
    """A read as the model writes it: the validators take its two answers."""
    return TurnDecision.model_validate(
        {"live": False, "think": False, "subject": subject, "picture": picture}
    )


def _done(decision: TurnDecision | None) -> asyncio.Future[TurnDecision | None]:
    future: asyncio.Future[TurnDecision | None] = asyncio.get_event_loop().create_future()
    future.set_result(decision)
    return future


def _solved(message: str) -> Any:
    """The verified block the turn solves: its problem part, as ``augment`` solves it."""
    (part,) = plan_turn(message).of_kind("solve")
    intent = extract_physics_intent(part.text)
    assert intent is not None
    block = build_verified_physics_block(intent, Settings(math_tools_enabled=True))
    assert block is not None
    return block


@pytest.mark.parametrize(
    ("subject", "picture", "drawn"),
    [
        ("physics", "diagram", True),
        ("maths", "graph", True),
        ("maths", "diagram", True),
        ("chemistry", "molecule", True),
        # A photo or a painting is not the app's drawing, nor is an everyday picture.
        ("physics", "photo", False),
        ("everyday", "photo", False),
        ("everyday", "image", False),
        ("everyday", "diagram", False),
        ("physics", "none", False),
    ],
)
def test_the_read_says_which_pictures_the_app_draws(
    subject: str, picture: str, drawn: bool
) -> None:
    assert asks_for_a_drawing(_read(subject, picture)) is drawn


def test_no_read_is_no_drawing() -> None:
    assert asks_for_a_drawing(None) is False


def test_a_solve_that_draws_its_scene_draws_the_picture() -> None:
    assert solve_draws_a_picture(_solved(CIRCUIT))
    assert solve_draws_a_picture(_solved(PATH))
    assert not solve_draws_a_picture(None)


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
        should_cancel=None,
    )


async def _painted() -> UUID:
    return uuid4()


@pytest.mark.asyncio
async def test_a_solved_circuit_gets_no_painting_above_it() -> None:
    """The read gave no answer in time: the solve's own schematic still stands alone."""
    task = asyncio.ensure_future(_painted())
    state = _state(
        "**Answer**\n\n2 A",
        reply_picture=ReplyPicture("the circuit", task=task),
        verified_subject=_solved(CIRCUIT),
    )
    assert app_draws_the_picture(state.ctx)
    assert await attach_reply_picture(state) == "**Answer**\n\n2 A"
    assert state.ctx.answer_photo_ids == []


@pytest.mark.asyncio
async def test_a_read_that_calls_it_a_diagram_paints_nothing() -> None:
    task = asyncio.ensure_future(_painted())
    state = _state(
        "The current is 2 A.",
        reply_picture=ReplyPicture("the circuit", task=task),
        live_read=_done(_read("physics", "diagram")),
    )
    assert await attach_reply_picture(state) == "The current is 2 A."


@pytest.mark.asyncio
async def test_an_everyday_picture_is_still_painted_above_the_answer() -> None:
    picture_id = uuid4()

    async def drawn() -> UUID:
        return picture_id

    state = _state(
        "A black hole is a region where gravity...",
        reply_picture=ReplyPicture("cat wearing a hat", task=asyncio.ensure_future(drawn())),
        live_read=_done(_read("everyday", "image")),
    )
    text = await attach_reply_picture(state)
    assert text.startswith(f"[Image: /attachments/{picture_id}/file]")


@pytest.mark.asyncio
async def test_a_solved_path_gets_no_photo_and_its_fence_goes() -> None:
    photo = AnswerPhoto(Settings(), MagicMock())
    with patch("app.modules.images.search.photos_for_answer", AsyncMock(return_value=[uuid4()])):
        state = _state(
            "```photo\nprojectile arc\n```\n\n**Answer**\n\n35.3 m",
            answer_photo=photo,
            verified_subject=_solved(PATH),
        )
        text = await attach_answer_photo(state)
    assert "```photo" not in text
    assert "[Image:" not in text
    assert state.ctx.answer_photo_ids == []


@pytest.mark.asyncio
async def test_a_physics_diagram_is_never_painted_when_the_read_says_so() -> None:
    painted = AsyncMock(return_value=uuid4())
    deps = MagicMock()
    deps.plan.can_use = MagicMock(return_value=True)
    with patch("app.modules.images.reply_picture.draw_unlinked", painted):
        picture = start_reply_picture(
            deps,
            Settings(),
            user=User(id=uuid4(), plan="pro", locale="en"),
            chat_id=uuid4(),
            content=CIRCUIT,
            read=asyncio.ensure_future(asyncio.sleep(0, result=_read("physics", "diagram"))),
        )
        assert picture is not None
        assert await picture.attach("The current is 2 A.") == ("The current is 2 A.", [])
    painted.assert_not_awaited()


@pytest.mark.parametrize("message", [CIRCUIT, PATH])
def test_a_problems_picture_is_the_solves_and_never_placed(message: str) -> None:
    """The contract asks for no photo fence and names no place for the picture."""
    plan = plan_turn(message)
    assert plan.multi
    contract = multi_part_contract(plan, [[] for _ in plan.parts])
    assert PROBLEM_PICTURE_NOTE in contract
    assert "```photo" not in contract
    assert "above your reply" not in contract
    assert PICTURE_PLACEMENT_RULE in contract


def test_an_everyday_picture_part_keeps_its_painting_note() -> None:
    plan = plan_turn("draw a cat wearing a hat and also explain what a black hole is")
    contract = multi_part_contract(plan, [[] for _ in plan.parts])
    assert "a picture to draw" in contract
    assert PROBLEM_PICTURE_NOTE not in contract
    assert PICTURE_PLACEMENT_RULE in contract


@pytest.mark.parametrize(
    ("read", "noted"),
    [(_read("physics", "diagram"), True), (_read("physics", "none"), False), (None, False)],
)
def test_a_solves_picture_the_message_asks_for_gets_no_words(
    read: TurnDecision | None, noted: bool
) -> None:
    """ "Draw the ray diagram" got a section saying the picture was "drawn in the app above
    this answer", under the diagram drawn below it (live, 2026-11-15)."""
    from app.modules.chat.decided_turn import _leave_the_picture
    from app.services.picture_copy import DRAWN_PICTURE_NOTE

    state = _state("x", verified_subject=_solved(CIRCUIT))
    _leave_the_picture(state.ctx, read)
    assert any(m["content"] == DRAWN_PICTURE_NOTE for m in state.ctx.prompt_messages) is noted

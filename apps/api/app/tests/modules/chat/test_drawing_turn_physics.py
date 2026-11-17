"""A physics reply describes its field picture; physics checks it and draws it.

The owner's GCSE set (2026-11-16): "Draw the pattern of the electric field around a) a
positive charge b) a negative charge" came back as ASCII art in code blocks. On a physics
message the read says asks to see a diagram that no solve drew, the reply gets physics'
contract, its ```draw blocks are traced into field lines under it, and its own sketch goes.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.modules.chat import drawing_turn
from app.modules.chat.drawing_turn import ask_for_a_drawing, attach_drawing
from app.modules.math.drawing.contract import DRAW_CONTRACT
from app.modules.physics.field_lines.contract import FIELD_DRAW_CONTRACT
from app.services.md_fence_scan import iter_closed_fences
from app.services.solving import VerifiedPhysicsBlock
from app.tests.modules.chat.test_drawing_turn import _ctx, _deadline, _decision, _settings, _state

_FIELD = (
    "Draw the pattern of the electric field around: a) a positive charge b) a negative "
    "charge. Explain what the arrows mean."
)


def _block(description: dict[str, Any]) -> str:
    return f"```draw\n{json.dumps(description)}\n```"


async def test_a_physics_diagram_gets_physics_contract() -> None:
    ctx = _ctx(_FIELD)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    assert ctx.drawing is not None and ctx.drawing.subject == "physics"
    assert ctx.prompt_messages[-2]["content"] == FIELD_DRAW_CONTRACT
    assert not any(m["content"] == DRAW_CONTRACT for m in ctx.prompt_messages)


def _verified(question: str) -> VerifiedPhysicsBlock:
    from app.core.config import Settings
    from app.modules.physics import build_verified_physics_block, extract_physics_intent

    intent = extract_physics_intent(question)
    assert intent is not None
    block = build_verified_physics_block(intent, Settings(math_tools_enabled=True))
    assert block is not None
    return block


async def test_a_physics_solve_that_drew_the_picture_asks_for_no_description(
    thread_sympy_executor: None,
) -> None:
    """A circuit, rays or a scene the solve drew: no description is asked for."""
    verified = _verified(
        "Two point charges of 3.0 nC and 2.0 nC are 5.0 m apart. Find the force between them."
    )
    ctx = _ctx(_FIELD, verified_subject=verified)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    assert ctx.drawing is None


async def test_a_physics_solve_that_drew_nothing_still_gets_the_contract(
    thread_sympy_executor: None,
) -> None:
    """ "Calculate the field strength ... and draw its lines": the solve verifies the number
    and draws no picture, so the reply describes the field (PR #2482 review)."""
    line = (
        "Calculate the electric field strength 0.20 m from a point charge of 8.0 pC and "
        "draw its field lines."
    )
    ctx = _ctx(line, verified_subject=_verified(line))
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    assert ctx.drawing is not None and ctx.drawing.subject == "physics"


async def test_descriptions_are_traced_under_the_reply_and_the_sketch_goes(
    thread_sympy_executor: None,
) -> None:
    ctx = _ctx(_FIELD)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    reply = (
        "**Around a positive charge** the lines point outward.\n\n"
        "```\n   \\  |  /\n  -- (+) --\n   /  |  \\\n```\n\n"
        "**Around a negative charge** they point inward.\n\n"
        f"{_block({'kind': 'field', 'part': 'a', 'charges': [{'sign': '+'}]})}\n\n"
        f"{_block({'kind': 'field', 'part': 'b', 'charges': [{'sign': '-'}]})}\n"
    )
    text = await attach_drawing(_state(ctx, reply))
    bodies = [body for _start, _end, body in iter_closed_fences(text, "simulation")]
    assert len(bodies) == 2
    parts = [json.loads(body)["field"]["part"] for body in bodies]
    assert parts == ["a", "b"]
    assert "```draw" not in text and "(+)" not in text
    assert "point outward" in text and "point inward" in text


async def test_a_description_that_does_not_check_leaves_the_reply_as_written(
    thread_sympy_executor: None,
) -> None:
    ctx = _ctx(_FIELD)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    reply = "Lines point outward.\n\n" + _block(
        {"kind": "field", "charges": [{"sign": "+", "at": [1, 2]}]}
    )
    text = await attach_drawing(_state(ctx, reply))
    assert text == "Lines point outward."


@pytest.mark.parametrize("picture", ["none", "photo", "image"])
async def test_a_physics_message_asking_for_no_diagram_gets_no_contract(picture: str) -> None:
    ctx = _ctx(_FIELD)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture=picture), _deadline()
    )
    assert ctx.drawing is None


async def test_physics_turned_off_asks_for_no_description() -> None:
    ctx = _ctx(_FIELD)
    settings = _settings(physics_enabled=False)
    await ask_for_a_drawing(
        ctx, settings, _decision(subject="physics", picture="diagram"), _deadline()
    )
    assert ctx.drawing is None
    assert not any(m["content"] == FIELD_DRAW_CONTRACT for m in ctx.prompt_messages)


async def test_a_flowchart_the_user_asked_for_stays_beside_the_picture(
    thread_sympy_executor: None,
) -> None:
    line = f"{_FIELD} Also make a flowchart of how to draw field lines."
    ctx = _ctx(line)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    flowchart = "```mermaid\ngraph TD\nA[Start on +] --> B[End on -]\n```"
    reply = (
        f"Lines point outward.\n\n{flowchart}\n\n"
        f"{_block({'kind': 'field', 'part': 'a', 'charges': [{'sign': '+'}]})}\n"
    )
    text = await attach_drawing(_state(ctx, reply))
    assert flowchart in text and "```simulation" in text


@pytest.mark.parametrize(("subject", "contract"), [("physics", True), (None, False)])
async def test_a_physics_message_asking_in_words_gets_the_contract_when_the_read_is_late(
    monkeypatch: pytest.MonkeyPatch, subject: str | None, contract: bool
) -> None:
    """The read had not answered by the reply's call: a message the physics reader reads
    that asks to see something gets physics' contract, as a maths one gets maths' (PR
    #2482 review); a message no subject reads gets none."""
    monkeypatch.setattr(drawing_turn, "_words_subject", lambda _ctx: subject)
    ctx = _ctx(_FIELD)
    await ask_for_a_drawing(ctx, _settings(), None, _deadline())
    assert (ctx.drawing is not None) == contract
    if contract:
        assert ctx.drawing is not None and ctx.drawing.asked == "words"
        assert ctx.prompt_messages[-2]["content"] == FIELD_DRAW_CONTRACT


async def test_a_physics_instant_reply_gives_way_to_field_lines_its_solve_did_not_draw() -> None:
    """ "Calculate the electric field 0.20 m from a point charge of 8.0 pC and draw its
    field lines": the solve's instant reply carried the field strength alone, and no lines
    could be described (Gemini, PR #2482). The read asking for a physics picture the solve
    did not draw lets the model write around the same card."""
    import asyncio

    from app.modules.chat import drawing_turn
    from app.services.solving import VerifiedPhysicsBlock

    line = (
        "Calculate the electric field 0.20 m from a point charge of 8.0 pC and draw its "
        "field lines."
    )
    read: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    read.set_result(_decision(subject="physics", picture="diagram"))
    ctx = _ctx(
        line,
        instant_reply="E = 1.8 N/C",
        verified_subject=VerifiedPhysicsBlock(text="E = 1.8 N/C"),
        live_read=read,
    )
    await drawing_turn.write_for_a_picture(ctx, _settings())
    assert ctx.instant_reply is None
    # A read that asks to see nothing keeps the card.
    keeps: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    keeps.set_result(_decision(subject="physics", picture="none"))
    card = _ctx(
        line,
        instant_reply="E = 1.8 N/C",
        verified_subject=VerifiedPhysicsBlock(text="E = 1.8 N/C"),
        live_read=keeps,
    )
    await drawing_turn.write_for_a_picture(card, _settings())
    assert card.instant_reply == "E = 1.8 N/C"


@pytest.mark.parametrize(
    ("line", "subject", "verified"),
    [
        ("No need to sketch it, just find the roots of x^2 - 5x + 6 = 0.", "maths", "math"),
        (
            "Find the field 0.20 m from an 8.0 pC charge; don't draw the field lines.",
            "physics",
            "physics",
        ),
    ],
)
async def test_a_message_that_asks_to_see_nothing_keeps_its_card_and_gets_no_contract(
    line: str, subject: str, verified: str
) -> None:
    """A read that says the message asks to see nothing ("no need to sketch it", "don't draw
    the field lines") keeps the instant card and asks for no description: every picture
    path goes through the read's one asks check (Gemini, PR #2482)."""
    import asyncio

    from app.modules.chat import drawing_turn
    from app.services.solving import VerifiedMathBlock, VerifiedPhysicsBlock

    block = (
        VerifiedMathBlock(text="x = 2, 3")
        if verified == "math"
        else VerifiedPhysicsBlock(text="E = 1.8 N/C")
    )
    read: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
    read.set_result(_decision(subject=subject, picture="none"))
    ctx = _ctx(line, instant_reply="card", verified_subject=block, live_read=read)
    await drawing_turn.write_for_a_picture(ctx, _settings())
    assert ctx.instant_reply == "card"
    asked = _ctx(line)
    await ask_for_a_drawing(
        asked, _settings(), _decision(subject=subject, picture="none"), _deadline()
    )
    assert asked.drawing is None

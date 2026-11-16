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


async def test_a_physics_solve_draws_its_own_picture() -> None:
    """A circuit, rays or a scene the solve drew: no description is asked for."""
    verified = VerifiedPhysicsBlock(text="", subject="physics")
    ctx = _ctx(_FIELD, verified_subject=verified)
    await ask_for_a_drawing(
        ctx, _settings(), _decision(subject="physics", picture="diagram"), _deadline()
    )
    assert ctx.drawing is None


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

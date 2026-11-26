"""A picture drawn in characters comes off a physics reply at finalize, asked of every
subject's fence (``finalize_subjects.strip_text_plots``): a solve's turn, a turn the read
calls physics, and never one the user asked to draw in characters or another subject's."""

from __future__ import annotations

import pytest

from app.core.readings import begin_turn, keep_for_turn
from app.modules.chat.finalize_subjects import strip_text_plots
from app.services.solving import VerifiedPhysicsBlock
from app.tests.modules.chat.test_figure_turn import _ctx, _read, _state

_PIPE = (
    "Laminar flow moves in smooth layers.\n\n"
    "```text\n"
    "|------------------- Pipe Wall -------------------|\n"
    "|  ~~~~  ~~~~  ~~~~  ~~~~  ~~~~  ~~~~  ~~~~      |\n"
    "|  ~~~~  ~~~~  ~~~~  ~~~~  ~~~~  ~~~~  ~~~~      |\n"
    "|  Velocity profile: Parabolic (fastest in center)|\n"
    "```\n"
)
_WORDS = "Laminar flow moves in smooth layers.\n"
_LINE = "What is laminar flow in a pipe?"


async def test_a_solved_physics_turn_loses_its_sketch() -> None:
    ctx = _ctx(_LINE, verified_subject=VerifiedPhysicsBlock(text="v = 2 m/s"))
    assert strip_text_plots(_state(ctx, _PIPE)) == _WORDS


async def test_a_turn_the_read_calls_physics_loses_its_sketch() -> None:
    """A phase diagram the subject readers read as no subject's: the turn's read says it."""
    begin_turn()
    read = _read(subject="physics", picture="diagram")
    keep_for_turn("live_read", read)
    assert strip_text_plots(_state(_ctx(_LINE, live_read=read), _PIPE)) == _WORDS


@pytest.mark.parametrize(
    ("line", "subject"),
    [
        ("Show laminar flow in a pipe as ASCII art.", "physics"),
        ("What is laminar flow in a pipe?", "everyday"),
    ],
    ids=["asked-for-in-characters", "no-physics"],
)
async def test_a_sketch_asked_for_or_off_physics_stays(line: str, subject: str) -> None:
    begin_turn()
    read = _read(subject=subject, picture="diagram")
    keep_for_turn("live_read", read)
    verified = VerifiedPhysicsBlock(text="") if subject == "physics" else None
    ctx = _ctx(line, live_read=read, verified_subject=verified)
    assert strip_text_plots(_state(ctx, _PIPE)) == _PIPE

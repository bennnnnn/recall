"""A verified result that answers part of a question never stands for the whole of it.

Live (2026-11-04): "I kick a ball at 20 m/s at 30 degrees, how far does it land and
what's the max height" was answered with the height, then "Want me to work out the
horizontal range too?"; "… Where is the image and how big is it" with the image distance
alone. The block says it is partial, the model is told to answer every other ask under
its own Answer heading, and the server's card is never landed as the whole answer.
Both live questions are now answered whole by the chain (``test_physics_catalog_reach``),
so the partial cases here ask something no law answers beside the number.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.config import Settings
from app.modules.physics.fence import validate_physics_fences
from app.modules.physics.parts import asks_count
from app.modules.physics.prompt import build_physics_augmentation, solve_physics_request
from app.modules.physics.reply_policy import PHYSICS_PARTIAL_POLICY
from app.services.answer_fence import VERIFIED_ANSWER_MARKER

_SETTINGS = Settings(math_tools_enabled=True)
_KICK = "A ball is kicked at 20 m/s at 30 degrees. How far does it land and why does air resistance matter?"
_LENS = (
    "An object is 30 cm from a convex lens with focal length 10 cm. "
    "Where is the image and how big is it"
)


def test_a_place_asked_counts_as_an_ask() -> None:
    assert asks_count(_LENS) == 2
    assert (
        asks_count(
            "An object is 30 cm from a convex lens of focal length 10 cm. Where is the image?"
        )
        == 1
    )


def test_a_result_for_one_of_two_asks_is_partial() -> None:
    outcome, block = solve_physics_request(_KICK, _SETTINGS, None)
    assert outcome == "verified" and block is not None
    assert block.partial


@pytest.mark.parametrize(
    "question",
    [
        "A ball is kicked at 20 m/s at 30 degrees. Find the range and the max height.",
        "Whats the current through a 12 ohm resistor on a 9V battery",
        "An object is 30 cm from a convex lens with focal length 10 cm. Where is the image?",
        _LENS,
    ],
)
def test_a_result_that_answers_every_ask_is_whole(question: str) -> None:
    _, block = solve_physics_request(question, _SETTINGS, None)
    assert block is not None and not block.partial


async def test_the_model_is_told_to_answer_the_rest() -> None:
    prompt, block, _ = await build_physics_augmentation(_KICK, _SETTINGS)
    assert block is not None and block.partial
    assert prompt is not None and PHYSICS_PARTIAL_POLICY in prompt
    whole, _, _ = await build_physics_augmentation(
        "Whats the current through a 12 ohm resistor on a 9V battery", _SETTINGS
    )
    assert whole is not None and PHYSICS_PARTIAL_POLICY not in whole


def test_a_partial_card_never_replaces_the_replys_one_answer() -> None:
    _, block = solve_physics_request(_KICK, _SETTINGS, None)
    assert block is not None and block.partial
    reply = (
        "**Range**\n$R = 35.3\\,\\mathrm{m}$\n\n**Air resistance**\nDrag slows it, so it lands "
        "short of that.\n\n**Answer**\nThe ball lands $35.3\\,\\mathrm{m}$ away; drag makes it less."
    )
    out = validate_physics_fences(reply, verified=block, user_text=_KICK)
    assert "35.3" in out and "The verified answer is" not in out
    assert VERIFIED_ANSWER_MARKER not in out
    # The same block taken as whole lands its card, as before.
    whole = validate_physics_fences(reply, verified=replace(block, partial=False), user_text=_KICK)
    assert VERIFIED_ANSWER_MARKER in whole

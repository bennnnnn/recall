"""Prompt prep for a money turn: which part reads as money, and where its block goes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.core.config import Settings
from app.modules.chat.turn_plan import TurnPart, TurnPlan, single_plan
from app.modules.chat.turn_prep import money as money_prep
from app.modules.money.block import MONEY_HEADER

_SENTENCE = "what is my mortgage for 300k dollars house if mr rate is 1 percent"


def _request(text: str, *, image: bool = False) -> Any:
    return SimpleNamespace(content=text, has_image_attachment=image)


def _identity() -> Any:
    return SimpleNamespace(user=None, geo=SimpleNamespace(user_location=None))


async def test_a_money_message_gets_its_turn_and_block() -> None:
    turn = await money_prep.money_turn(
        _request(_SENTENCE), _identity(), Settings(), None, single_plan(_SENTENCE)
    )
    assert turn is not None and turn.request.product.key == "mortgage"
    if turn.lookup is not None:
        turn.lookup.cancel()
    prompt = [{"role": "system", "content": "S"}, {"role": "user", "content": _SENTENCE}]
    placed = money_prep.with_money_block(prompt, turn)
    assert placed[1]["role"] == "system" and placed[1]["content"].startswith(MONEY_HEADER)
    assert placed[-1]["content"] == _SENTENCE


async def test_the_money_part_of_a_multi_part_message_is_found() -> None:
    plan = TurnPlan((TurnPart("tell me a joke"), TurnPart(_SENTENCE)))
    turn = await money_prep.money_turn(
        _request(f"tell me a joke and {_SENTENCE}"), _identity(), Settings(), None, plan
    )
    assert turn is not None and turn.request.values["amount"] == 300000
    if turn.lookup is not None:
        turn.lookup.cancel()


async def test_no_money_turn_with_a_photo_or_with_money_off() -> None:
    plan = single_plan(_SENTENCE)
    assert (
        await money_prep.money_turn(
            _request(_SENTENCE, image=True), _identity(), Settings(), None, plan
        )
        is None
    )
    off = Settings(money_enabled=False)
    assert await money_prep.money_turn(_request(_SENTENCE), _identity(), off, None, plan) is None


def test_no_turn_no_block() -> None:
    prompt = [{"role": "user", "content": "hi"}]
    assert money_prep.with_money_block(prompt, None) == prompt

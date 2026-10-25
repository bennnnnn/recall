"""Prompt prep for a money turn: which part reads as money, and where its block goes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from redis.asyncio import Redis

from app.core.config import Settings
from app.modules.chat.turn_plan import TurnPart, TurnPlan, single_plan
from app.modules.chat.turn_prep import money as money_prep
from app.modules.money.block import MONEY_HEADER

_SENTENCE = "what is my mortgage for 300k dollars house if mr rate is 1 percent"


def _request(text: str, *, image: bool = False, history: tuple[str, ...] = ()) -> Any:
    rows = [
        SimpleNamespace(role=role, content=line)
        for line in history
        for role, line in (("user", line), ("assistant", "About $340 a month."))
    ]
    return SimpleNamespace(content=text, has_image_attachment=image, recent_messages=rows)


def _identity() -> Any:
    return SimpleNamespace(user=None, geo=SimpleNamespace(user_location=None))


async def test_a_money_message_gets_its_turn_and_block(fake_redis: Redis) -> None:
    turn = await money_prep.money_turn(
        _request(_SENTENCE), _identity(), Settings(), fake_redis, single_plan(_SENTENCE)
    )
    assert turn is not None and turn.request.product.key == "mortgage"
    if turn.lookup is not None:
        turn.lookup.cancel()
    prompt = [{"role": "system", "content": "S"}, {"role": "user", "content": _SENTENCE}]
    placed = money_prep.with_money_block(prompt, turn)
    assert placed[1]["role"] == "system" and placed[1]["content"].startswith(MONEY_HEADER)
    assert placed[-1]["content"] == _SENTENCE


async def test_the_money_part_of_a_multi_part_message_is_found(fake_redis: Redis) -> None:
    plan = TurnPlan((TurnPart("tell me a joke"), TurnPart(_SENTENCE)))
    turn = await money_prep.money_turn(
        _request(f"tell me a joke and {_SENTENCE}"), _identity(), Settings(), fake_redis, plan
    )
    assert turn is not None and turn.request.values["amount"] == 300000
    if turn.lookup is not None:
        turn.lookup.cancel()


async def test_no_money_turn_with_a_photo_or_with_money_off(fake_redis: Redis) -> None:
    plan = single_plan(_SENTENCE)
    assert (
        await money_prep.money_turn(
            _request(_SENTENCE, image=True), _identity(), Settings(), fake_redis, plan
        )
        is None
    )
    off = Settings(money_enabled=False)
    assert (
        await money_prep.money_turn(_request(_SENTENCE), _identity(), off, fake_redis, plan) is None
    )


def test_no_turn_no_block() -> None:
    prompt = [{"role": "user", "content": "hi"}]
    assert money_prep.with_money_block(prompt, None) == prompt


_CAR = "car loan 14000 with 3000 down at 7.16% for 5 years, what's the monthly payment"
_WHAT_IF = "hmm what if i only do 3 years instead"


async def test_a_what_if_reads_the_users_earlier_lines(fake_redis: Redis) -> None:
    """Live (2026-10-25): "what if i only do 3 years instead" got no card."""
    turn = await money_prep.money_turn(
        _request(_WHAT_IF, history=(_CAR,)),
        _identity(),
        Settings(),
        fake_redis,
        single_plan(_WHAT_IF),
    )
    assert turn is not None and turn.request.values["months"] == 36
    assert turn.request.changed == ("months",)
    if turn.lookup is not None:
        turn.lookup.cancel()


async def test_a_regenerated_what_if_skips_its_own_stored_line(fake_redis: Redis) -> None:
    """A regenerate's window ends with the line itself; it is not its own earlier request."""
    request = _request(_WHAT_IF, history=(_CAR,))
    request.recent_messages.append(SimpleNamespace(role="user", content=_WHAT_IF))
    turn = await money_prep.money_turn(
        request, _identity(), Settings(), fake_redis, single_plan(_WHAT_IF)
    )
    assert turn is not None and turn.request.values["months"] == 36
    if turn.lookup is not None:
        turn.lookup.cancel()


async def test_a_what_if_part_of_a_multi_part_message_is_found(fake_redis: Redis) -> None:
    plan = TurnPlan((TurnPart("tell me a joke"), TurnPart("what if i only do 3 years instead")))
    turn = await money_prep.money_turn(
        _request(f"tell me a joke and {_WHAT_IF}", history=(_CAR,)),
        _identity(),
        Settings(),
        fake_redis,
        plan,
    )
    assert turn is not None and turn.request.values["months"] == 36
    if turn.lookup is not None:
        turn.lookup.cancel()


async def test_a_what_if_after_the_chat_moved_on_is_no_money_turn(fake_redis: Redis) -> None:
    workout = ("give me a 4 day workout plan with 4 sets of each exercise",)
    for line, history in (
        ("what if i only do 3 sets instead", workout),
        (_WHAT_IF, (_CAR, "how do I make lasagna?")),
    ):
        turn = await money_prep.money_turn(
            _request(line, history=history), _identity(), Settings(), fake_redis, single_plan(line)
        )
        assert turn is None

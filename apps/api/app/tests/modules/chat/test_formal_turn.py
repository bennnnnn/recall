"""A physics reply's final value is held to the server's answer from the model's own setup.

Measured (docs/FORMAL_READER.md, 2026-11-16): in 36 disagreements between the server's
answer and the reply model's, the server was right every time. So a reply that states
another value gets the server's card; one that states the same value stands; one whose
value cannot be read gets the server's card under it, both shown.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.modules.chat import formal_turn
from app.modules.chat.finalize_passes import FinalizeState
from app.modules.chat.turn_decision import TurnDecision
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.modules.physics import formal_read
from app.modules.physics.formal_read import FormalAnswer
from app.services.solving import VerifiedPhysicsBlock
from app.tests.modules.chat.chat_test_support import turn_deps

_QUESTION = "A ball is kicked at 18 m/s at 35° above the ground. How far does it land?"
_RANGE = FormalAnswer(value=31.07, unit="m")


def _settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def _ctx(line: str = _QUESTION, locale: str = "en", **fields: Any) -> StreamContext:
    user = User(id=uuid4(), name="Bini", plan="pro", emoji_use="some", locale=locale)
    ctx = StreamContext(
        user_id=user.id,
        chat_id=uuid4(),
        model="smart-chat",
        prompt_messages=[{"role": "user", "content": line}],
        run_title=False,
        user_message_content=line,
        reserved_tokens=0,
        max_output_tokens=0,
        user_timezone="UTC",
        user=user,
    )
    for name, value in fields.items():
        setattr(ctx, name, value)
    return ctx


def _state(ctx: StreamContext, text: str, settings: Settings | None = None) -> FinalizeState:
    return FinalizeState(
        deps=turn_deps(),
        settings=settings or _settings(),
        ctx=ctx,
        raw=text,
        text=text,
        usage={},
        outcome=TurnOutcome(),
        was_cancelled=False,
        should_cancel=None,
    )


def _read(subject: Any = "physics") -> asyncio.Future[TurnDecision | None]:
    read: asyncio.Future[TurnDecision | None] = asyncio.get_event_loop().create_future()
    read.set_result(TurnDecision(live=False, think=False, subject=subject))
    return read


@pytest.fixture
def answer(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The server's answer, stood in for; the questions it was asked."""
    asked: list[str] = []

    async def worked(question: str, settings: Settings) -> FormalAnswer | None:
        asked.append(question)
        return _RANGE

    monkeypatch.setattr(formal_read, "formal_answer", worked)
    return asked


async def _finalized(ctx: StreamContext, reply: str, settings: Settings | None = None) -> str:
    ctx.formal = formal_turn.start_formal(settings or _settings(), ctx)
    return await formal_turn.attach_formal(_state(ctx, reply, settings))


async def test_a_reply_that_states_another_value_gets_the_server_s(answer: list[str]) -> None:
    reply = "Its time of flight is 2.1 s.\n\n**Answer**\n\nThe range is $R = 32.4\\ \\text{m}$."
    text = await _finalized(_ctx(live_read=_read()), reply)
    assert "32.4" not in text.split("**Answer**")[1]
    assert "Worked out from the values in the question: $31.07\\ \\mathrm{m}$." in text
    assert "```answer\nverified: false\n31.07\\ \\mathrm{m}\n```" in text
    assert answer == [_QUESTION]


@pytest.mark.parametrize("stated", ["$R = 31.07\\ \\text{m}$", "about 31.1 m"])
async def test_a_reply_that_states_the_server_s_value_stands(
    answer: list[str], stated: str
) -> None:
    reply = f"**Answer**\n\nThe range is {stated}."
    assert await _finalized(_ctx(live_read=_read()), reply) == reply


async def test_a_reply_whose_value_cannot_be_read_gets_both_in_its_language(
    answer: list[str],
) -> None:
    line = "Мяч ударили со скоростью 18 м/с под углом 35°. Как далеко он упадёт?"
    reply = "**Ответ**\n\nДальность полёта около 32,4 м."
    text = await _finalized(_ctx(line, locale="ru", live_read=_read()), reply)
    assert text.startswith(reply)
    assert "Рассчитано по данным задачи: $31.07\\ \\mathrm{m}$." in text
    assert text.rstrip().endswith("```answer\nverified: false\n31.07\\ \\mathrm{m}\n```")
    assert "**Answer**" not in text


async def test_a_turn_a_solver_answered_never_asks(answer: list[str]) -> None:
    verified = VerifiedPhysicsBlock(text="")
    ctx = _ctx(live_read=_read(), verified_subject=verified)
    assert formal_turn.start_formal(_settings(), ctx) is None


@pytest.mark.parametrize(
    "fields",
    [
        {"instant_reply": "It is 3 pm."},
        {"live_read": None},
    ],
    ids=["server-wrote-the-reply", "no-read"],
)
async def test_no_answer_without_a_model_reply_to_check(
    answer: list[str], fields: dict[str, Any]
) -> None:
    assert formal_turn.start_formal(_settings(), _ctx(**({"live_read": _read()} | fields))) is None


@pytest.mark.parametrize(
    "settings",
    [_settings(formal_reader_enabled=False), _settings(physics_enabled=False)],
    ids=["formal-off", "physics-off"],
)
async def test_the_switches_turn_it_off(answer: list[str], settings: Settings) -> None:
    assert formal_turn.start_formal(settings, _ctx(live_read=_read())) is None


async def test_a_turn_the_read_calls_no_physics_is_left_alone(answer: list[str]) -> None:
    reply = "**Answer**\n\n$x = 32.4$"
    assert await _finalized(_ctx(live_read=_read("maths")), reply) == reply
    assert answer == []


async def test_finalize_waits_no_longer_than_its_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    async def slow(question: str, settings: Settings) -> FormalAnswer:
        await asyncio.sleep(5)
        return _RANGE

    monkeypatch.setattr(formal_read, "formal_answer", slow)
    reply = "**Answer**\n\nThe range is $R = 32.4\\ \\text{m}$."
    ctx = _ctx(live_read=_read())
    text = await _finalized(ctx, reply, _settings(formal_wait_seconds=0.05))
    assert text == reply
    await asyncio.sleep(0)
    assert ctx.formal is not None and ctx.formal.cancelled()


@pytest.mark.parametrize(
    ("value", "unit", "shown"),
    [
        (31.07, "m", "31.07\\ \\mathrm{m}"),
        (3.4722, "m/s^2", "3.472\\ \\mathrm{m/s^{2}}"),
        (6780.0, "N", "6780\\ \\mathrm{N}"),
        (45.0, "degC", "45\\ ^\\circ\\mathrm{C}"),
        (2.998e8, "m/s", "2.998\\times 10^{8}\\ \\mathrm{m/s}"),
        (0.5, "", "0.5"),
        (12.0, "ohm", "12\\ \\Omega"),
        (12000.0, "m", "12000\\ \\mathrm{m}"),
        (50000.0, "m", "50000\\ \\mathrm{m}"),
        (12345.6, "J", "12350\\ \\mathrm{J}"),
        (9999.9, "J", "10000\\ \\mathrm{J}"),
        (0.0012346, "m", "0.001235\\ \\mathrm{m}"),
        (-4.0, "m/s^2", "-4\\ \\mathrm{m/s^{2}}"),
        (5e10, "m", "5\\times 10^{10}\\ \\mathrm{m}"),
    ],
)
def test_the_card_draws_the_value_and_its_unit(value: float, unit: str, shown: str) -> None:
    assert FormalAnswer(value=value, unit=unit).card_value == shown

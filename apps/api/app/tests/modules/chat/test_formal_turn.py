"""A physics reply's cards are held to the server's answer from the model's own setup.

Measured (docs/FORMAL_READER.md, 2026-11-16): in 36 disagreements between the server's
answer and the reply model's, the server was right every time. So a card that states
another value gets the server's; one that states the same value in any unit of its kind,
for any standard value of a constant (g as 10), stands; no card is ever added; and a
question whose values cannot all hold opens with a line saying so (G8 round, 2026-11-18).
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
from app.services.formal.answer import FormalAnswer, FormalValue, StatedConflict
from app.services.solving import VerifiedPhysicsBlock
from app.tests.modules.chat.chat_test_support import turn_deps

_QUESTION = "A ball is kicked at 18 m/s at 35° above the ground. How far does it land?"


def _value(
    value: float,
    unit: str,
    part: str = "",
    band: tuple[float, float] | None = None,
    uses: tuple[float, ...] = (),
) -> FormalValue:
    low, high = band or (value, value)
    return FormalValue(part, "x", value, unit, low, high, uses, agrees=True)


def _answer(*values: FormalValue, conflicts: tuple[StatedConflict, ...] = ()) -> FormalAnswer:
    return FormalAnswer(values=values, conflicts=conflicts)


_RANGE = _answer(_value(31.07, "m", uses=(18.0, 35.0)))


def _card(value: str) -> str:
    return f"```answer\nverified: false\n{value}\n```"


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


async def test_a_card_that_states_another_value_gets_the_server_s(answer: list[str]) -> None:
    reply = "Kicked at 18 m/s at 35°, $R = 32.4\\ \\text{m}$.\n\n**Answer**\n\n" + _card(
        "32.4\\ \\mathrm{m}"
    )
    text = await _finalized(_ctx(live_read=_read()), reply)
    after = text.split("**Answer**")[1]
    assert "32.4" not in after and after.count("```answer") == 1
    assert (
        "Worked out again from the values in the question:\n\n" + _card("31.07\\ \\mathrm{m}")
        in text
    )
    assert answer == [_QUESTION]


@pytest.mark.parametrize(
    ("server", "card"),
    [
        (_value(31.07, "m", uses=(18.0, 35.0)), "31.1\\,\\mathrm{m}"),
        (_value(0.01, "m^2", uses=(18.0,)), "100\\ \\mathrm{cm}^{2}"),
        (_value(50.0, "ohm", uses=(18.0,)), "50\\,\\mathrm{Ω}"),
        (_value(0.9, "", uses=(18.0,)), "90\\,\\%"),
        (_value(90.0, "%", uses=(18.0,)), "0.9"),
        (_value(-7500.0, "N", uses=(18.0,)), "7500\\,\\mathrm{N}"),
        (_value(2.0, "delta_degC", uses=(18.0,)), "2\\,\\mathrm{K}"),
    ],
    ids=["rounded", "another-unit", "ohms", "percent", "fraction", "size", "kelvin-change"],
)
async def test_a_card_that_states_the_server_s_value_stands(
    monkeypatch: pytest.MonkeyPatch, server: FormalValue, card: str
) -> None:
    """Card to card in any unit of the kind: 100 cm² is 0.01 m², 50 Ω a resistance, 90% the
    fraction 0.9, a braking force's size its value (the sign is the reply's convention).
    Nothing is added: 50 Ω carded twice, "Worked out from …: 50 Ω" (G8 t25, t40)."""
    _answered(monkeypatch, _answer(server))
    reply = f"With 18 m/s:\n\n**Answer**\n\n{_card(card)}\n\nA closing line."
    assert await _finalized(_ctx(live_read=_read()), reply) == reply


@pytest.mark.parametrize(
    ("server", "working", "card"),
    [
        # G8 t18: the book's g = 10 gives 250 Pa; the server's 9.81 gives 245.
        (
            _value(245.25, "Pa", band=(237.9, 252.6), uses=(1.0, 2.0, 50.0)),
            "$g = 10$, $W = 50 \\times 10 = 500$, $A = 2 \\times 1 = 2$",
            "250\\,\\mathrm{Pa}",
        ),
        # G8 t24: 2560 Pa at 32 cm is 800 kg/m³ at g = 10.
        (
            _value(815.5, "kg/m^3", band=(791.7, 840.7), uses=(32.0, 2560.0)),
            "$\\rho = \\frac{2560}{10 \\times 0.32}$, 32 cm",
            "800\\,\\mathrm{kg/m^3}",
        ),
    ],
    ids=["t18-pressure", "t24-density"],
)
async def test_a_card_that_differs_only_by_the_book_s_g_stands(
    monkeypatch: pytest.MonkeyPatch, server: FormalValue, working: str, card: str
) -> None:
    _answered(monkeypatch, _answer(server))
    reply = f"{working}\n\n**Answer**\n\n{_card(card)}"
    assert await _finalized(_ctx(live_read=_read()), reply) == reply


async def test_a_reply_read_another_way_is_not_held_to_the_server_s_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The server's value is worked from 2 V ("2 dry cells" read as 2 V); the reply never
    writes 2 and took two 1.5 V cells: a reading, not a slip, so its card stands."""
    _answered(monkeypatch, _answer(_value(4.0, "ohm", uses=(2.0, 0.5))))
    reply = "$V = 3$, $I = 0.5$, $R = 3/0.5$\n\n**Answer**\n\n" + _card("6\\,\\Omega")
    assert await _finalized(_ctx(live_read=_read()), reply) == reply


async def test_a_reply_with_no_card_gets_none_added(answer: list[str]) -> None:
    reply = "Kicked at 18 m/s at 35°, it lands about 32.4 m away."
    assert await _finalized(_ctx(live_read=_read()), reply) == reply


def _parts_reply(first: str, second: str) -> str:
    return (
        "Two resistors of 40 Ω at 120 V.\n\n**(a) Total resistance**\n\n$R = 40 + 40$\n\n"
        f"**Answer (a)**\n\n{_card(first)}\n\n---\n\n**(b) Current**\n\n$I = 120/80$\n\n"
        f"**Answer (b)**\n\n{_card(second)}\n"
    )


async def test_each_part_s_card_is_held_to_its_own_part(monkeypatch: pytest.MonkeyPatch) -> None:
    _answered(
        monkeypatch,
        _answer(_value(80.0, "ohm", "a", uses=(40.0,)), _value(1.5, "A", "b", uses=(40.0, 120.0))),
    )
    text = await _finalized(
        _ctx(live_read=_read()), _parts_reply("80\\,\\Omega", "2\\,\\mathrm{A}")
    )
    assert _card("80\\,\\Omega") in text
    assert _card("1.50\\ \\mathrm{A}") in text and "2\\,\\mathrm{A}" not in text
    assert text.count("Worked out again") == 1 and text.count("```answer") == 2


_LEVER = _answer(
    _value(2400.0, "N*m", "a", uses=(1200.0, 2.0)),
    conflicts=(
        StatedConflict(
            "a balanced lever has equal moments on each side",
            "2400\\ \\mathrm{N\\cdot m}",
            "\\neq",
            "240\\ \\mathrm{N\\cdot m}",
        ),
        StatedConflict("a machine's MA can't be more than its VR", "15", ">", "1.5"),
    ),
)


async def test_a_question_whose_values_cannot_all_hold_says_so_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live, 2026-11-18: "a lever balances 1200 N by 80 N, 2 m from the load and 3 m from
    the effort" was worked part by part and never called broken. Its cards stay: each is
    what the numbers as written give."""
    _answered(monkeypatch, _LEVER)
    reply = _parts_reply("2000\\,\\mathrm{N\\cdot m}", "240\\,\\mathrm{N\\cdot m}")
    text = await _finalized(_ctx(live_read=_read()), reply)
    assert text.startswith(
        "These values can't all be right: a balanced lever has equal moments on each side, "
        "but here $2400\\ \\mathrm{N\\cdot m} \\neq 240\\ \\mathrm{N\\cdot m}$.\n\n"
        "These values can't all be right: a machine's MA can't be more than its VR, but here "
        "$15 > 1.5$.\n\n"
    )
    assert text.endswith(reply) and "Worked out again" not in text


async def test_the_conflict_line_is_in_the_reply_s_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _answered(monkeypatch, _LEVER)
    line = "Рычаг уравновешивает груз 1200 Н силой 80 Н. Найдите моменты сил."
    text = await _finalized(_ctx(line, locale="ru", live_read=_read()), "**Ответ**")
    assert text.startswith("Эти значения не могут быть верны одновременно: ")


def _answered(monkeypatch: pytest.MonkeyPatch, answer: FormalAnswer) -> None:
    async def worked(question: str, settings: Settings) -> FormalAnswer:
        return answer

    monkeypatch.setattr(formal_read, "formal_answer", worked)


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
    reply = "18 and 35\n\n**Answer**\n\n" + _card("32.4")
    assert await _finalized(_ctx(live_read=_read("maths")), reply) == reply
    assert answer == []


async def test_finalize_waits_no_longer_than_its_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    async def slow(question: str, settings: Settings) -> FormalAnswer:
        await asyncio.sleep(5)
        return _RANGE

    monkeypatch.setattr(formal_read, "formal_answer", slow)
    reply = "18 and 35\n\n**Answer**\n\n" + _card("32.4\\ \\mathrm{m}")
    ctx = _ctx(live_read=_read())
    text = await _finalized(ctx, reply, _settings(formal_wait_seconds=0.05))
    assert text == reply
    await asyncio.sleep(0)
    assert ctx.formal is not None and ctx.formal.cancelled()


@pytest.mark.parametrize(
    ("value", "unit", "shown"),
    [
        (31.07, "m", "31.07\\ \\mathrm{m}"),
        (3.4722, "m/s^2", "3.47\\ \\mathrm{m/s^{2}}"),
        (6780.0, "N", "6780\\ \\mathrm{N}"),
        (45.0, "degC", "45\\ ^\\circ\\mathrm{C}"),
        (2.998e8, "m/s", "299800000\\ \\mathrm{m/s}"),
        (0.5, "", "0.50"),
        (12.0, "ohm", "12\\ \\Omega"),
        # A product of units is one \cdot, never a line break (review of #2465).
        (2.5, "N*m", "2.50\\ \\mathrm{N\\cdot m}"),
        (4180.0, "J/(kg*K)", "4180\\ \\mathrm{J/(kg\\cdot K)}"),
        (12000.0, "m", "12000\\ \\mathrm{m}"),
        (50000.0, "m", "50000\\ \\mathrm{m}"),
        (12345.6, "J", "12345.60\\ \\mathrm{J}"),
        (9999.9, "J", "9999.90\\ \\mathrm{J}"),
        (0.0012346, "m", "0.00123\\ \\mathrm{m}"),
        (-4.0, "m/s^2", "-4\\ \\mathrm{m/s^{2}}"),
        (5e10, "m", "5.00 \\times 10^{10}\\ \\mathrm{m}"),
        (90.0, "%", "90\\ \\%"),
    ],
)
def test_the_card_draws_the_value_and_its_unit(value: float, unit: str, shown: str) -> None:
    assert _value(value, unit).card_value == shown


async def test_a_count_named_in_words_is_compared_as_a_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live G8 t43: "4000 turns" was read as 4000 angular turns (pint), 636.6 in the
    server's pure number, and replaced by "4000"."""
    _answered(monkeypatch, _answer(_value(4000.0, "", uses=(800.0,))))
    reply = "$N_s = 800 \\times 5$\n\n**Answer**\n\n" + _card("4000\\ \\text{turns}")
    assert await _finalized(_ctx(live_read=_read()), reply) == reply


async def test_a_conflict_with_no_words_of_its_own_is_still_said(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conflict = StatedConflict("", "15", ">", "1.50", relation="MA \\le VR")
    _answered(monkeypatch, _answer(conflicts=(conflict,)))
    text = await _finalized(_ctx(live_read=_read()), "**Answer**")
    assert text.startswith(
        "These values can't all be right: $MA \\le VR$ must hold, but here $15 > 1.50$.\n\n"
    )


async def test_parts_the_reply_letters_its_own_way_are_paired_by_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live G8 t42: the reply left out the part asked in words, so its (b) was the
    setup's (c); paired by letter the resistance met the current, and no card was held.
    By kind, R = 220/0.27 = 814.8 (rounded too soon) gets the server's 806.67."""
    _answered(
        monkeypatch,
        _answer(
            _value(0.2727, "A", "b", uses=(60.0, 220.0)),
            _value(806.67, "ohm", "c", uses=(60.0, 220.0)),
        ),
    )
    reply = (
        "60 W at 220 V\n\n**(a) Current**\n\n$I = 60/220$\n\n**Answer (a)**\n\n"
        + _card("0.273\\,\\mathrm{A}")
        + "\n\n**(b) Resistance**\n\n$R = 220/0.27$\n\n**Answer (b)**\n\n"
        + _card("814.8\\,\\Omega")
    )
    text = await _finalized(_ctx(live_read=_read()), reply)
    assert _card("0.273\\,\\mathrm{A}") in text and "814.8" not in text
    assert _card("806.67\\ \\Omega") in text


async def test_a_part_no_card_letters_is_paired_by_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    """Claude on #2501: the setup's parts are (a) and (c), the reply letters (a) and (b).
    (a) pairs by letter; the setup's (c) has no card of its letter, so it pairs by kind
    with the card left, (b), and a resistance rounded too soon is held to the server's."""
    _answered(
        monkeypatch,
        _answer(
            _value(0.2727, "A", "a", uses=(60.0, 220.0)),
            _value(806.67, "ohm", "c", uses=(60.0, 220.0)),
        ),
    )
    reply = (
        "60 W at 220 V\n\n**(a) Current**\n\n$I = 60/220$\n\n**Answer (a)**\n\n"
        + _card("0.273\\,\\mathrm{A}")
        + "\n\n**(b) Resistance**\n\n$R = 220/0.27$\n\n**Answer (b)**\n\n"
        + _card("814.8\\,\\Omega")
    )
    text = await _finalized(_ctx(live_read=_read()), reply)
    assert _card("0.273\\,\\mathrm{A}") in text and "814.8" not in text
    assert _card("806.67\\ \\Omega") in text


async def test_a_card_in_powers_of_ten_is_held_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review: a card's places below 0 (1.5 x 10^6) broke the check and left every card."""
    _answered(monkeypatch, _answer(_value(1.2e6, "J", uses=(18.0,))))
    reply = "18 and 35\n\n**Answer**\n\n" + _card("E = 1.5 \\times 10^{6}\\,\\mathrm{J}")
    text = await _finalized(_ctx(live_read=_read()), reply)
    assert _card("E = 1200000\\ \\mathrm{J}") in text


async def test_two_values_of_one_kind_are_paired_by_their_own_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review: T_2 carded first was paired with the first asked, T_1, and both "corrected"."""
    _answered(
        monkeypatch,
        _answer(
            FormalValue("", "T1", 20.0, "N", 20.0, 20.0, (5.0,), True),
            FormalValue("", "T_2", 30.0, "N", 30.0, 30.0, (5.0,), True),
        ),
    )
    reply = "5 kg\n\n" + _card("T_2 = 30\\,\\mathrm{N}") + "\n\n" + _card("T_1 = 20\\,\\mathrm{N}")
    assert await _finalized(_ctx(live_read=_read()), reply) == reply


async def test_a_replaced_card_keeps_its_own_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _answered(monkeypatch, _answer(_value(806.67, "ohm", uses=(220.0,))))
    reply = "$R = 220/0.27$\n\n" + _card("R = 814.8\\,\\Omega")
    assert _card("R = 806.67\\ \\Omega") in await _finalized(_ctx(live_read=_read()), reply)


async def test_a_card_to_the_precision_asked_stands(monkeypatch: pytest.MonkeyPatch) -> None:
    _answered(monkeypatch, _answer(_value(0.2727, "A", uses=(60.0, 220.0))))
    line = "A 60 W lamp runs on 220 V. Find the current to 1 decimal place."
    reply = "$I = 60/220$\n\n" + _card("0.3\\,\\mathrm{A}")
    assert await _finalized(_ctx(line, live_read=_read()), reply) == reply


@pytest.mark.parametrize(
    ("agrees", "said"), [((True, True), True), ((True, False), False), ((), False)]
)
def test_a_broken_check_is_said_only_of_a_setup_whose_answers_agree(
    agrees: tuple[bool, ...], said: bool
) -> None:
    """Review: a misread setup (the wrong arms) would open a right reply with a false
    contradiction and keep every card from being held."""
    conflict = {"meaning": "m", "left": "1", "broken": ">", "right": "0.5", "relation": ""}
    answers = [
        {"part": "", "symbol": "x", "value": 1.0, "unit": "", "low": 1.0, "high": 1.0,
         "uses": [], "agrees": agree}
        for agree in agrees
    ]  # fmt: skip
    answer = formal_read.answer_of({"solved": True, "answers": answers, "conflicts": [conflict]})
    assert bool(answer and answer.conflicts) is said


@pytest.mark.parametrize(
    ("card", "stands"),
    [
        ("T = -10\\,^\\circ\\mathrm{C}", True),
        ("T = 263.15\\,\\mathrm{K}", True),
        ("T = 10\\,^\\circ\\mathrm{C}", False),  # 283.15 K: another temperature
    ],
)
def test_a_temperature_on_a_scale_is_held_to_its_sign(card: str, stands: bool) -> None:
    """Review: a velocity's sign is the reply's convention, a temperature's is its value."""
    from app.modules.chat.formal_cards import agrees, reply_cards

    (read,) = reply_cards(_card(card))
    assert agrees(read, _value(-10.0, "degC")) is stands


def test_a_velocity_s_sign_stays_the_reply_s_convention() -> None:
    from app.modules.chat.formal_cards import agrees, reply_cards

    (read,) = reply_cards(_card("v = 12\\,\\mathrm{m/s}"))
    assert agrees(read, _value(-12.0, "m/s")) is True

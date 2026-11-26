"""Review round 1 on #2591: each finding's case, which failed before its fix."""

from __future__ import annotations

import re

import pytest

from app.core.config import Settings
from app.modules.chat.card_lists import listed_values
from app.modules.chat.card_numbers import card_numbers
from app.modules.chat.worked_render import WorkedLayout, render_worked
from app.modules.chat.worked_solution import assemble, read_record
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.services.rounding_rule import RULE, number_latex
from app.tests.behavior.stem_sweep import _rounded_shown, same_quantity

_SETTINGS = Settings(math_tools_enabled=True)


def _answer(question: str) -> str | None:
    intent = extract_physics_intent(question)
    block = None if intent is None else build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


# --- 4703431673: a mass read in pounds is never taken for kilograms -----------------------


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        # 1.3e25 lb is 5.9e24 kg: g = G M / r² is 9.61 m/s², never 21.18 (M taken for kg).
        ("Find the surface gravity of a planet with mass 1.3e25 lb and radius 6.4e6 m.", "9.61"),
        ("Find the surface gravity of a planet with mass 5.8967e24 kg and radius 6.4e6 m.", "9.61"),
    ],
)
def test_a_planets_mass_is_read_in_its_own_unit(question: str, answer: str) -> None:
    shown = _answer(question)
    assert shown is not None and shown.startswith(answer), shown


def test_a_gravitational_potential_keeps_its_mass_unit() -> None:
    kilograms = _answer("Find the gravitational potential at 7e6 m from a body of mass 6e24 kg.")
    pounds = _answer(
        "Find the gravitational potential at 7e6 m from a body of mass 1.322774e25 lb."
    )
    assert kilograms is not None and pounds is not None
    assert float(pounds.split()[0]) == pytest.approx(float(kilograms.split()[0]), rel=1e-4)


# --- 4703432163: a ton is a short ton or a tonne: no reader takes one ---------------------


def test_a_ton_is_declined_and_a_tonne_is_read() -> None:
    assert _answer(
        "A crane lifts a 2 ton load at constant speed. Find the tension in the cable."
    ) is (None)
    assert _answer(
        "A crane lifts a 2 tonne load at constant speed. Find the tension in the cable."
    ) == ("19620 N")


# --- 4703431904: a card and a given keep their digits; only working's are shortened --------

_WORKED = (
    "given: x | 12345.67 | m | the distance\n"
    "required: y | the result\n"
    "formula: Sum | y = x + 7048.897\n"
    "substitution: y = 12345.67 + 7048.897\n"
    "substitution: y = 19394.567\n"
    "substitution: z = 0.357142857142857\n"
    "answer: y | 19394.567 | m\n"
)


def test_a_card_and_a_given_keep_their_digits() -> None:
    records = [read_record(line) for line in _WORKED.split("\n")]
    shown = render_worked(assemble([r for r in records if r is not None]), WorkedLayout())
    assert "12345.67" in shown  # the given, as the user wrote it
    assert "0.357143" in shown and "0.357142857142857" not in shown  # a calculator's digits
    # The answer the card is made from: by the rule, never cut to six figures (19394.6).
    assert shown.rstrip().endswith("$y = 19394.57\\,\\mathrm{m}$")
    assert re.search(r"19394\.6(?!\d)", shown) is None


# --- 4703433180: a float under a tie is the tie in every branch ----------------------------


@pytest.mark.parametrize(
    ("value", "shown"), [(0.1 * 0.1235, "0.0124"), (0.0001 * 50**2 / 2, "0.13")]
)
def test_a_float_under_a_tie_rounds_as_the_tie(value: float, shown: str) -> None:
    assert number_latex(value) == shown


# --- 4703432690: a unit's power in a list; money in a list stays to the cent ---------------


def test_an_acceleration_vector_card_is_rounded_and_money_is_not() -> None:
    vector = "(-9.043478 î + 8.695652 ĵ) m/s²"
    assert listed_values(vector)
    reply = f"**Answer**\n\n```answer\nverified: false\n{vector}\n```"
    assert "(-9.04 î + 8.70 ĵ) m/s²" in card_numbers(reply, RULE)
    money = "12.345 USD, 4.5678 USD"
    assert not listed_values(money)
    reply = f"**Answer**\n\n```answer\nverified: false\n{money}\n```"
    assert card_numbers(reply, RULE) == reply


# --- 4703433653: a whole physics card has no rounding allowance ---------------------------


@pytest.mark.parametrize(
    ("card", "worked", "right"),
    [("10", 14.0, False), ("2", 2.4, False), ("4700", 4650.0, False), ("0.31", 0.3142, True)],
)
def test_the_stem_judge_allows_only_a_decimal_physics_cards_rounding(
    card: str, worked: float, right: bool
) -> None:
    ok, _detail = same_quantity(
        (float(card), "m/s"), (worked, "m/s"), shown=_rounded_shown("physics", card)
    )
    assert ok is right

"""Every card's number by the one rule, whoever wrote it (``chat.card_numbers``)."""

from __future__ import annotations

import pytest

from app.modules.chat.card_numbers import card_numbers
from app.services.answer_number import Precision


def _card(value: str, verified: str = "false") -> str:
    return f"```answer\nverified: {verified}\n{value}\n```"


def test_a_card_shows_the_working_s_value_rounded_once() -> None:
    """The owner's chat, 2026-11-18: the working reached 109324.04 Pa and the card said
    1.09 x 10^5, as the prompt's "3 significant figures" had the model write it."""
    reply = "$P = 820 \\times 133.322$\n$P = 109324.04\\,\\mathrm{Pa}$\n\n**Answer**\n\n" + _card(
        "1.09 \\times 10^{5}\\,\\mathrm{Pa}"
    )
    assert _card("109324.04\\,\\mathrm{Pa}") in card_numbers(reply, Precision())


def test_a_card_in_another_unit_than_its_working_keeps_its_own_value() -> None:
    reply = "$P = 109324.04\\,\\mathrm{Pa}$\n\n" + _card("1.0932404\\,\\mathrm{bar}")
    assert _card("1.09\\,\\mathrm{bar}") in card_numbers(reply, Precision())


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        ("x = 2 \\text{ or } x = -3.5", "x = 2 \\text{ or } x = -3.50"),
        ("20\\,\\mathrm{m/s}", "20\\,\\mathrm{m/s}"),
        ("6.022 \\times 10^{23}", "6.02 \\times 10^{23}"),
        ("0.2727\\,\\mathrm{A}", "0.27\\,\\mathrm{A}"),
        ("2400\\,\\mathrm{m^{2}}", "2400\\,\\mathrm{m^{2}}"),  # a unit's power is no number
    ],
)
def test_each_number_on_a_card_follows_the_rule(value: str, shown: str) -> None:
    assert card_numbers(_card(value, "true"), Precision()) == _card(shown, "true")


@pytest.mark.parametrize(
    "value",
    [
        "\\mathrm{pH} = 2.874",  # a pH's decimals are its concentration's figures
        "\\$1,234.567",  # money, to the cent as written
        "x = \\frac{1}{3}",  # exact
        "3/4",
        "x^2 + 2.5x",  # an expression
    ],
)
def test_what_is_no_plain_value_is_left_as_written(value: str) -> None:
    assert card_numbers(_card(value), Precision()) == _card(value)


def test_the_precision_asked_is_the_card_s() -> None:
    assert card_numbers(_card("18.5185\\,\\mathrm{m/s}"), Precision(places=1)) == _card(
        "18.5\\,\\mathrm{m/s}"
    )

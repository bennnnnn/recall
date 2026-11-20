"""Every card's number by the one rule, whoever wrote it (``chat.card_numbers``)."""

from __future__ import annotations

import pytest

from app.modules.chat.card_numbers import card_numbers
from app.services.rounding_rule import Precision


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
        ("0.2727\\,\\mathrm{A}", "0.273\\,\\mathrm{A}"),  # never more than 0.5% off
        ("K_{p} = 1.2 \\times 10^{-4}", "K_{p} = 1.2 \\times 10^{-4}"),  # no figure added
        ("2400\\,\\mathrm{m^{2}}", "2400\\,\\mathrm{m^{2}}"),  # a unit's power is no number
        # A negative power in a unit is no number either (review).
        ("a = 9.8123\\,\\mathrm{m\\,s^{-2}}", "a = 9.81\\,\\mathrm{m\\,s^{-2}}"),
        ("c = 0.12345\\,\\mathrm{mol\\,L^-1}", "c = 0.123\\,\\mathrm{mol\\,L^-1}"),
        # An exact whole number stays whole at any size (review): 2^40, 20!.
        ("x = 1099511627776", "x = 1099511627776"),
        ("2432902008176640000", "2432902008176640000"),
        ("E = 6000000000\\,\\mathrm{J}", "E = 6.00 \\times 10^{9}\\,\\mathrm{J}"),
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


def test_a_whole_card_is_never_taken_back_to_its_working_s_decimals() -> None:
    """Review: 120 / 45 = 2.67 buses, carded 3, came back as 2.67."""
    reply = "$n = 120 \\div 45 = 2.67$, so round up.\n\n" + _card("n = 3")
    assert card_numbers(reply, Precision()) == reply


def test_a_whole_card_in_a_unit_of_measure_shows_its_working_s_value() -> None:
    """The owner's chat (2026-11-20): the tension at the bottom carded 104 N, three figures,
    beside the top's 45.57 N; its working reached 104.43 N."""
    reply = "$T = 104.43\\,\\mathrm{N}$\n\n" + _card("104\\,\\mathrm{N}")
    assert card_numbers(reply, Precision()).endswith(_card("104.43\\,\\mathrm{N}"))
    # A count stays the whole number the question needs.
    counted = "$n = 2.67$\n\n" + _card("n = 3 buses")
    assert card_numbers(counted, Precision()) == counted


def test_a_greek_name_is_read_and_its_number_follows_the_rule() -> None:
    assert card_numbers(
        _card("\\lambda = 5.876 \\times 10^{-7}\\,\\mathrm{m}"), Precision()
    ) == _card("\\lambda = 5.88 \\times 10^{-7}\\,\\mathrm{m}")


def test_a_card_the_model_left_open_follows_the_rule_once_closed() -> None:
    """Review: an open card shipped "13.333333 m/s" where a closed one was 13.33. The pass
    runs after ``close_fences`` (the pass order test), so the closed card is the one read."""
    from app.services.md_fence_scan import close_unclosed_fences

    reply = "$v = 160 / 12$\n\n```answer\nv = 13.333333\\,\\mathrm{m/s}"
    shown = card_numbers(close_unclosed_fences(reply), Precision())
    assert "v = 13.33\\,\\mathrm{m/s}" in shown and "13.333333" not in shown

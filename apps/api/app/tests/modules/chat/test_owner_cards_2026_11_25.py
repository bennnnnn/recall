"""Three physics answers the owner asked on the dev account (2026-11-25): "it supposed to be
just 2!". The cards showed 0.577, 0.357142857… and a vector of sixteen-digit components, and
the working the same digits. Each reply below is the one saved then, before finalize's card
pass ran on it again.
"""

from __future__ import annotations

import re

import pytest

from app.modules.chat.card_lists import listed_values
from app.modules.chat.card_numbers import card_numbers
from app.modules.chat.worked_render import _line
from app.services.answer_check import read_verified_value
from app.services.rounding_rule import RULE, number_latex, working_figures

_FRICTION_RAMP = (
    "**Substitution**  \n$\\mu = \\frac{60\\sin 30^\\circ}{60\\cos 30^\\circ}$  \n"
    "$\\mu = \\frac{30}{30\\sqrt{3}}$  \n$\\mu = \\frac{1}{\\sqrt{3}}$  \n$\\mu \\approx 0.577$\n\n"
    "**Answer**\n\n```answer\nverified: false\n0.577\n```"
)
_FRICTION_TABLE = (
    "**Substitution**  \n$N = 2 \\times 9.8$  \n$N = 19.6\\,\\mathrm{N}$  \n"
    "Solve for $\\mu_k$  \n$\\mu_k = \\frac{F_k}{N}$  \n$\\mu_k = \\frac{7}{19.6}$  \n"
    "$\\mu_k = 0.357142857\\ldots$  \n$0.357142857\\ldots \\times 19.6 = 7\\,\\mathrm{N}$\n\n"
    "**Answer**\n\n```answer\nverified: false\n0.357142857\\ldots\n```"
)
_COLLISION = (
    "**Substitution**  \n$v_{fx} = \\frac{-(1300)(16)}{1000 + 1300}$  \n"
    "$v_{fx} = -9.043478260869565\\,\\mathrm{m/s}$  \n"
    "$v_{fy} = 8.695652173913043\\,\\mathrm{m/s}$  \n"
    "$\\theta = \\tan^{-1}\\!\\left(\\frac{8.695652173913043}{9.043478260869565}\\right)$  \n"
    "$\\theta = 43.9^\\circ$\n\n"
    "**Answer (b)**\n\n```answer\nverified: false\n"
    "$(-9.043478260869565\\hat{i} + 8.695652173913043\\hat{j})\\,\\mathrm{m/s}$, "
    "$12.546951\\ldots\\,\\mathrm{m/s}$, 43.9° north of west\n```"
)


def _card(reply: str) -> str:
    return re.findall(r"```answer\nverified: false\n(.*?)\n```", card_numbers(reply, RULE))[0]


@pytest.mark.parametrize(
    ("reply", "card"),
    [
        (_FRICTION_RAMP, "0.58"),
        (_FRICTION_TABLE, "0.36"),
        (
            _COLLISION,
            "$(-9.04\\hat{i} + 8.70\\hat{j})\\,\\mathrm{m/s}$, $12.55\\,\\mathrm{m/s}$, "
            # tan⁻¹(8.695652 / 9.043478) is 43.877°: worked out from the working, never the
            # model's 43.9° padded to 43.90.
            "43.88° north of west",
        ),
    ],
    ids=["ramp", "table", "collision"],
)
def test_the_owners_cards_show_two_places(reply: str, card: str) -> None:
    assert _card(reply) == card


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (0.5773502692, "0.58"),
        (0.357142857, "0.36"),
        (0.4551, "0.46"),
        (0.0649, "0.0649"),
        (0.0456, "0.0456"),
        (0.00123, "0.00123"),
        (0.05, "0.05"),
        (0.000456, r"4.56 \times 10^{-4}"),
        (2.453, "2.45"),
        (-9.043478260869565, "-9.04"),
    ],
)
def test_two_places_below_one_and_three_figures_below_a_tenth(value: float, shown: str) -> None:
    assert number_latex(value) == shown


@pytest.mark.parametrize("value", ["0.357142857\\ldots", "0.357142857…", "0.357142857\\dots"])
def test_a_value_whose_digits_go_on_is_read(value: str) -> None:
    read = read_verified_value(value)
    assert read is not None and float(read.numbers[0].value) == pytest.approx(0.357142857)


@pytest.mark.parametrize(
    ("value", "listed"),
    [
        ("$(-9.04\\hat{i} + 8.7\\hat{j})\\,\\mathrm{m/s}$", True),
        ("12.5 m/s, 43.9° north of west", True),
        ("2x + 3.5", False),
        ("x^2 + 0.25", False),
        ("x = 0.5, y = 0.25", False),
        ("12.5 m/s", False),
    ],
)
def test_a_list_of_values_is_told_from_maths(value: str, listed: bool) -> None:
    assert listed_values(value) is listed


def test_an_expression_card_is_left_as_written() -> None:
    reply = "**Answer**\n\n```answer\nverified: false\ny = 0.333x + 2.5\n```"
    assert card_numbers(reply, RULE) == reply


@pytest.mark.parametrize(
    ("tex", "shown"),
    [
        ("v_{fx} = -9.043478260869565\\,\\mathrm{m/s}", "v_{fx} = -9.04348\\,\\mathrm{m/s}"),
        ("\\mu_k = 0.357142857\\ldots", "\\mu_k = 0.357143"),
        ("t = 4.82488\\,\\mathrm{s}", "t = 4.82488\\,\\mathrm{s}"),
        ("m^{2.5}", "m^{2.5}"),
        ("123456789", "123456789"),
    ],
)
def test_working_keeps_six_figures_never_a_calculators_sixteen(tex: str, shown: str) -> None:
    assert working_figures(tex) == shown
    # A line of working the layout writes (``worked_render._line``), not a card or a given.
    assert "9.043478260869565" not in _line(
        "v_f = \\sqrt{(-9.043478260869565)^2 + (8.695652173913043)^2}"
    )


@pytest.mark.parametrize(
    ("above", "card", "shown"),
    [
        # Nothing works it out: the figures written, never a padded zero.
        ("", "2.4\\,\\mathrm{m}", "2.4\\,\\mathrm{m}"),
        ("$\\theta = 43.9^\\circ$", "43.9^\\circ", "43.9^\\circ"),
        # The working holds it exactly (12 / 5) or unrounded (tan⁻¹): the rule's places.
        (
            "$x = \\frac{12}{5}$  \n$x = 2.4\\,\\mathrm{m}$",
            "x = 2.4\\,\\mathrm{m}",
            "x = 2.40\\,\\mathrm{m}",
        ),
        (
            "$\\theta = \\tan^{-1}(8.695652 / 9.043478)$  \n$\\theta = 43.9^\\circ$",
            "\\theta = 43.9^\\circ",
            "\\theta = 43.88^\\circ",
        ),
        # Worked from a rounded 0.9615, tan⁻¹ lies anywhere in 43.86° to 43.89°: as written.
        (
            "$\\theta = \\tan^{-1}(0.9615)$  \n$\\theta = 43.9^\\circ$",
            "\\theta = 43.9^\\circ",
            "\\theta = 43.9^\\circ",
        ),
        # 1/0.008333 is 120.0048, but 0.008333 may be 1/120: 120.0 is no 120.00 (review, #2591).
        (
            "$k = \\frac{1}{0.008333}$  \n$k = 120.0\\,\\mathrm{N/m}$",
            "k = 120.0\\,\\mathrm{N/m}",
            "k = 120\\,\\mathrm{N/m}",
        ),
    ],
)
def test_a_card_is_padded_only_when_its_precision_is_known(
    above: str, card: str, shown: str
) -> None:
    reply = f"{above}\n\n**Answer**\n\n```answer\nverified: false\n{card}\n```"
    assert _card(reply) == shown

"""The working's last line ends on the card's rounding: ``t = 4.82488 s ≈ 4.82 s``."""

from __future__ import annotations

import pytest

from app.modules.chat.card_numbers import card_numbers, cards_again, line_value
from app.modules.chat.rounded_end import rounded_ends
from app.services.rounding_rule import RULE, Precision


def _card(value: str, verified: str = "true") -> str:
    return f"```answer\nverified: {verified}\n{value}\n```"


@pytest.mark.parametrize(
    ("line", "card", "ended"),
    [
        # The owner's phone, 2026-11-23: the working's 4.82488 s beside a card of 4.82 s.
        (
            r"$t = \frac{20}{4.145} = 4.82488\ \text{s}$",
            r"t = 4.82\ \text{s}",
            r"$t = \frac{20}{4.145} = 4.82488\ \text{s} \approx 4.82\ \text{s}$",
        ),
        (
            r"$h = 98.8078\,\mathrm{m}$",
            r"h = 98.81\,\mathrm{m}",
            r"$h = 98.8078\,\mathrm{m} \approx 98.81\,\mathrm{m}$",
        ),
        # A chemistry card in its data's significant figures.
        (
            r"$c = \frac{0.0500}{0.3853} = 0.12976\,\mathrm{M}$",
            r"c = 0.1298\,\mathrm{M}",
            r"$c = \frac{0.0500}{0.3853} = 0.12976\,\mathrm{M} \approx 0.1298\,\mathrm{M}$",
        ),
        # The line's own sign and unit spelling; a card with no name.
        (r"$a = -3.4667\ \text{m/s}^2$", r"-3.47\ \text{m/s}^2", None),
        # A power of ten whose mantissa the line rounds to.
        (
            r"$P = 109324.04\,\mathrm{Pa}$",
            r"P = 1.09 \times 10^{5}\,\mathrm{Pa}",
            r"$P = 109324.04\,\mathrm{Pa} \approx 1.09 \times 10^{5}\,\mathrm{Pa}$",
        ),
        (r"$x = 2.2360679$", "x = 2.24", r"$x = 2.2360679 \approx 2.24$"),
    ],
)
def test_the_last_line_ends_on_the_cards_rounding(line: str, card: str, ended: str | None) -> None:
    reply = f"**Substitution**\n\n{line}\n\n**Answer**\n\n{_card(card)}"
    expected = ended or line[:-1] + r" \approx -3.47\ \text{m/s}^2$"
    assert rounded_ends(reply) == reply.replace(line, expected)


def test_display_maths_ends_on_the_rounding_too() -> None:
    reply = f"$$\nh = 98.8078\\,\\mathrm{{m}}\n$$\n\n{_card(r'h = 98.81\,\mathrm{m}')}"
    assert r"h = 98.8078\,\mathrm{m} \approx 98.81\,\mathrm{m}" in rounded_ends(reply)
    bracketed = f"\\[t = 4.82488\\ \\text{{s}}\\]\n\n{_card(r't = 4.82\ \text{s}')}"
    assert r"\[t = 4.82488\ \text{s} \approx 4.82\ \text{s}\]" in rounded_ends(bracketed)


@pytest.mark.parametrize(
    ("line", "card"),
    [
        # Already the card's number: nothing rounds.
        (r"$t = 4.82\ \text{s}$", r"t = 4.82\ \text{s}"),
        # A disagreement is another pass's: 4.91 never rounds to 4.82.
        (r"$t = 4.91372\ \text{s}$", r"t = 4.82\ \text{s}"),
        # Already rounding, the model's own "≈".
        (r"$t = 4.82488\ \text{s} \approx 4.82\ \text{s}$", r"t = 4.82\ \text{s}"),
        (r"$t = 4.82488\,\mathrm{s} ≈ 4.82\,\mathrm{s}$", r"t = 4.82\,\mathrm{s}"),
        # Money is exact to the cent; a pH keeps its concentration's figures.
        (r"$A = \$1234.5678$", r"A = \$1234.57"),
        (r"$\mathrm{pH} = 2.30103$", r"\mathrm{pH} = 2.30"),
        # Several values, an expression.
        (r"$x = 2.2360679$", "x = 2.24 or x = -2.24"),
        (r"$x = 2.2360679$", r"x = \sqrt{5}"),
        # A power of ten whose mantissa is not the line's.
        (r"$P = 109324.04\,\mathrm{Pa}$", r"P = 1.12 \times 10^{5}\,\mathrm{Pa}"),
        # Another unit, another quantity's name.
        (r"$t = 4.82488\ \text{min}$", r"t = 4.82\ \text{s}"),
        (r"$v_y = 3.2141\ \text{m/s}$", r"v_x = 3.21\ \text{m/s}"),
        # A count rounded as the question needs: 3.75 buses is 4.
        (r"$n = 3.75$", "n = 4"),
        # Not the line's own end: a wrapper around the number.
        (r"$t = \boxed{4.82488}$", "t = 4.82"),
    ],
)
def test_the_line_is_left_alone(line: str, card: str) -> None:
    reply = f"{line}\n\n{_card(card)}"
    assert rounded_ends(reply) == reply


def test_only_headings_may_stand_between_the_line_and_the_card() -> None:
    sentence = (
        r"$t = 4.82488\ \text{s}$" + "\n\nSo the ball lands after that.\n\n" + _card("t = 4.82 s")
    )
    assert rounded_ends(sentence) == sentence
    stop = r"The time is $t = 4.82488\ \text{s}$." + "\n\n" + _card(r"t = 4.82\ \text{s}")
    assert r"4.82488\ \text{s} \approx 4.82\ \text{s}$." in rounded_ends(stop)


def test_each_part_pairs_with_its_own_line() -> None:
    reply = (
        "**(a)**\n\n"
        r"$t = 4.82488\ \text{s}$"
        "\n\n" + _card(r"t = 4.82\ \text{s}") + "\n\n**(b)**\n\n"
        r"$d = 98.8078\,\mathrm{m}$"
        "\n\n" + _card(r"d = 98.81\,\mathrm{m}") + "\n\n**(c)**\n\n"
        r"$v = 20.5\ \text{m/s}$"
        "\n\n" + _card(r"v = 20.50\ \text{m/s}")
    )
    done = rounded_ends(reply)
    assert r"4.82488\ \text{s} \approx 4.82\ \text{s}$" in done
    assert r"98.8078\,\mathrm{m} \approx 98.81\,\mathrm{m}$" in done
    # 20.5 is 20.50: the card adds a zero, it rounds nothing.
    assert r"$v = 20.5\ \text{m/s}$" in done


def test_a_picture_between_the_line_and_the_card_parts_them() -> None:
    reply = r"$t = 4.82488\ \text{s}$" + "\n\n```graph\n{}\n```\n\n" + _card("t = 4.82 s")
    assert rounded_ends(reply) == reply


def test_the_card_number_pass_still_reads_the_unrounded_value() -> None:
    """A saved reply's line ends on its rounding; the card's numbers and a follow-up's
    precision are still read from the value before it."""
    line = r"t = 4.82488\ \text{s} \approx 4.82\ \text{s}"
    reached = line_value(line)
    assert reached is not None and float(reached.value) == pytest.approx(4.82488)
    reply = f"${line}$\n\n{_card(r't = 4.82\ \text{s}', 'false')}"
    assert card_numbers(reply, RULE) == reply
    again = cards_again(reply, Precision(places=4))
    assert again is not None and "4.8249" in again[0][1]


def test_a_rounding_on_its_own_row_still_leaves_the_value_above_it() -> None:
    """The calculation layout sets a chain with no unit one state per row: "mu = 0.404026"
    then "mu \\approx 0.404". A follow-up's precision still reads 0.404026, and the pass
    leaves the rows alone."""
    reply = "$\\mu = 0.404026$  \n$\\mu \\approx 0.404$\n\n" + _card("0.404", "false")
    assert rounded_ends(reply) == reply
    again = cards_again(reply, Precision(figures=5))
    assert again is not None and "0.40403" in again[0][1]


def test_the_pass_runs_once_the_cards_numbers_are_final() -> None:
    from app.modules.chat.finalize_passes import FINALIZE_PASSES

    names = [finalize_pass.name for finalize_pass in FINALIZE_PASSES]
    assert names.index("rounded_end") == names.index("card_numbers") + 1


def test_rounding_twice_changes_nothing() -> None:
    reply = r"$t = 4.82488\ \text{s}$" + "\n\n" + _card(r"t = 4.82\ \text{s}")
    once = rounded_ends(reply)
    assert rounded_ends(once) == once != reply

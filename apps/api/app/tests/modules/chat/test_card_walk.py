"""One card walk and one number grammar for the passes over a reply's answer cards (audit,
2026-11-25): six passes each walked the fences and read numbers their own way, and the lead
and tail passes read a calculator's "1.77e-10" as 1.77 and 10."""

from __future__ import annotations

import pytest

from app.modules.chat.card_walk import answer_cards
from app.modules.chat.worked_lead import drop_guessed_lead, drop_recap_tail
from app.modules.chat.written_numbers import any_numbers


@pytest.mark.parametrize(
    "written",
    [
        "1.77e-10",
        "1.77E-10",
        r"1.77 \times 10^{-10}",
        r"1.77\cdot10^{-10}",
        "1.77 × 10^{−10}",
        # Prose spellings (review of #2592): every digit of a bare exponent, x and *, and
        # superscripts.
        "1.77 × 10^-10",
        "1.77 x 10^-10",
        "1.77*10^-10",
        "1.77 × 10⁻¹⁰",
        "1.77 x 10^-10.",
    ],
)
def test_a_number_with_its_power_of_ten_is_one_number(written: str) -> None:
    assert any_numbers(f"K = {written} M") == {"1.77e-10"}


@pytest.mark.parametrize("written", ["6.02 × 10^23", "6.02 x 10^23", "6.02 × 10²³", "6.02*10^23"])
def test_a_bare_exponent_is_every_digit_it_has(written: str) -> None:
    """10^23 is ten to the 23rd, not 10^2 and a 3."""
    assert any_numbers(f"{written} atoms") == {"6.02e23"}


@pytest.mark.parametrize("given", ["1.8 × 10⁻⁵", "1.8 x 10^-5", "1.8e-5", r"1.8 \times 10^{-5}"])
def test_a_lead_restating_a_given_stays(given: str) -> None:
    """A lead that only says the question's value again, in prose's spelling, states no
    result: it stays above the working, which writes the value in TeX (review of #2592)."""
    working = (
        "**Given**\n\n$K_a = 1.8 \\times 10^{-5}$, $c = 0.10\\ \\mathrm{M}$\n\n"
        "**Solution**\n\n$x = \\sqrt{1.8 \\times 10^{-5} \\times 0.10} = 0.00134$\n\n"
        "```answer\nverified: false\n[H^+] = 0.00134\\ \\mathrm{M}\n```\n"
    )
    reply = f"Ka = {given}, so the acid is weak.\n\n" + working
    assert drop_guessed_lead(reply) == reply


def test_every_number_is_read_whole() -> None:
    assert any_numbers(r"1,200 m^{2} and \frac{1}{2} at (2,3), 3.50 s") == {
        "1200",
        "2",
        "1",
        "3",
        "3.50",
    }


_WORKING = (
    "**Given**\n\n$m = 12\\ \\mathrm{g}$, $c = 1.77\\ \\mathrm{M}$\n\n"
    "**Solution**\n\n$K = 1.77 \\times 10^{-10}$\n\n"
    "```answer\nverified: false\nK = 1.77e-10\n```\n"
)


def test_a_lead_stating_another_power_of_ten_is_a_guess() -> None:
    """Read as 1.77 and 12, "1.77e-12" was two numbers the working holds, and the guess
    above the working stayed."""
    reply = "The constant is **1.77e-12**.\n\n" + _WORKING
    assert drop_guessed_lead(reply) == _WORKING


def test_a_closing_line_with_a_power_of_ten_the_reply_never_wrote_is_no_recap() -> None:
    """Read as 1.77 and 12, a new value after the card read as the working said again."""
    tail = "\nThe second constant is 1.77e-12 at this temperature.\n\nCheck the table for it.\n"
    reply = _WORKING + tail
    assert drop_recap_tail(reply) == reply


def test_a_card_is_closed_or_open_to_the_reply_s_end() -> None:
    """The closer closes the last fence left open, so it is a card before the closer and
    after it; an answer fence left open with another fence after it never closes."""
    open_last = "Working\n\n```answer\nx = 3\n"
    assert [card.body(open_last) for card in answer_cards(open_last)] == ["x = 3\n"]
    open_between = "```answer\nx = 3\n```graph\n{}\n```\n"
    assert list(answer_cards(open_between)) == []
    closed = "a\n```result\nx = 3\n```\nb\n```final\ny = 4\n```\n"
    cards = list(answer_cards(closed))
    assert [card.body(closed) for card in cards] == ["x = 3\n", "y = 4\n"]
    assert cards[1].since_card == cards[0].fence.end

"""An unchecked card held to the working's last line: an expression left unworked and a
card that is not its value (live, 2026-11-22: "5 + 20" carded 37, "D = 4 - 12" carded -7)."""

from __future__ import annotations

import pytest

from app.modules.chat.working_cards import held_cards


def _reply(working: str, card: str, closing: str = "") -> str:
    reply = f"{working}\n\n**Answer**\n\n```answer\nverified: false\n{card}\n```\n"
    return f"{reply}\n{closing}" if closing else reply


_PERCENT = (
    "**Given**  \n$base = 80$  \n$percent = 25\\,\\%$  \n$addend = 5$\n\n**Substitution**  \n"
    "$\\text{part} = 80 \\times 0.25$  \n$\\text{part} = 20$  \n$\\text{total} = 5 + 20$"
)
_DISCRIMINANT = "**Substitution**  \n$D = 2^2 - 4(3)(1)$  \n$D = 4 - 12$"


@pytest.mark.parametrize(
    ("working", "card", "closing", "fixed_card", "fixed_closing"),
    [
        (
            _PERCENT,
            "total = 37",
            "Add **5** to **20** for a final answer of **37**.",
            "total = 25",
            "Add **5** to **20** for a final answer of **25**.",
        ),
        (
            _DISCRIMINANT,
            "D = -7",
            "Since -7 is negative, the equation has no real roots.",
            "D = -8",
            "Since -8 is negative, the equation has no real roots.",
        ),
        # A unit on the card, not said again in the closing line's own unit.
        (
            "$a = 1200\\,\\text{m}$  \n$b = 300\\,\\text{m}$  \n$\\text{d} = 1200 + 300$",
            "d = 1,600\\,\\text{m}",
            "So they walked 1,600 m in all.",
            "d = 1,500\\,\\text{m}",
            "So they walked 1,500 m in all.",
        ),
        # A bare expression, a card with no symbol, its decimals kept.
        ("$\\text{x} = 1.5$, $\\text{y} = 2.25$\n\n$1.5 + 2.25$", "3.85", "", "3.75", ""),
    ],
)
def test_the_card_takes_the_value_its_working_makes(
    working: str, card: str, closing: str, fixed_card: str, fixed_closing: str
) -> None:
    text, note = held_cards(_reply(working, card, closing))
    assert note is None
    assert text == _reply(working, fixed_card, fixed_closing)


@pytest.mark.parametrize(
    ("working", "card"),
    [
        # The card is the expression's value, rounded once.
        ("$t = 10/3$", "t = 3.33"),
        ("$t = 10/3$", "t \\approx 3.3"),
        ("$\\text{total} = 5 + 20$", "total = 25"),
        # A count rounded up as the question needs.
        ("$\\text{buses} = 45 / 12$", "buses = 4"),
        # Another name: c^2 is worked, c is carded.
        ("$c^2 = 9 + 16$", "c = 5"),
        ("$c^2 = 9 + 16$", "5"),
        # The line reached its value; the card is another step's.
        ("$x = 3 + 4 = 7$", "x = 9"),
        # A unit the working did not use.
        ("$d = 7000 + 200\\,\\text{m}$", "d = 7.2\\,\\text{km}"),
        # A sentence that goes on to work more out (review, #2536).
        ("Divide $100$ by $2 + 3$", "share = 20"),
        # Words between the line and the card work more out.
        ("$\\text{total} = 5 + 20$, then add the 12 extra ones.", "total = 37"),
    ],
)
def test_a_card_its_working_does_not_contradict_stays(working: str, card: str) -> None:
    reply = _reply(working, card)
    assert held_cards(reply) == (reply, None)


def test_a_number_of_the_question_is_the_workings() -> None:
    """The live reply never wrote the 5 it added: the question did (2026-11-22)."""
    working = "$\\frac{25}{100} \\times 80$  \n$0.25 \\times 80 = 20$  \nbase + result\n$5 + 20$"
    reply = _reply(working, "total = 37")
    assert held_cards(reply)[1] is not None
    text, note = held_cards(reply, "what is 5 plus 25% of 80?")
    assert note is None
    assert text == _reply(working, "total = 25")


def test_a_checked_card_is_the_solvers() -> None:
    reply = "$\\text{total} = 5 + 20$\n\n```answer\nverified: true\ntotal = 37\n```\n"
    assert held_cards(reply) == (reply, None)


@pytest.mark.parametrize(
    "working",
    [
        # 20 is no value the working reached: the expression may be the slip, not the card.
        "$\\text{part} = 32$  \n$\\text{total} = 5 + 20$",
        # An earlier step slips too.
        "$\\text{part} = 80 \\times 0.25 = 21$  \n$\\text{total} = 5 + 20$",
    ],
)
def test_a_slip_whose_side_is_unknown_is_named(working: str) -> None:
    reply = _reply(working, "total = 37")
    text, note = held_cards(reply)
    assert text == reply
    assert note == "Check the answer: $5 + 20 = 25$, not $37$."


def test_only_the_last_card_is_corrected() -> None:
    """The text after an earlier card is the next part's working, not its summary."""
    first = _reply("$a = 5$  \n$b = 20$  \n$\\text{total} = 5 + 20$", "total = 37")
    reply = first + "\n**(b)**\n$y = 37 + 1$\n\n```answer\nverified: false\ny = 38\n```\n"
    assert held_cards(reply) == (reply, "Check the answer: $5 + 20 = 25$, not $37$.")


def test_a_wrong_value_the_working_also_wrote_leaves_the_closing_line() -> None:
    working = "$a = 20$  \n$b = 5$  \n$\\text{total} = a + b$  \n$\\text{total} = 20 + 5$"
    reply = _reply(working, "total = 20", "So the total is 20.\n\nHope that helps!")
    text, note = held_cards(reply)
    assert note is None
    assert "total = 25" in text
    assert "So the total is 20." not in text and "Hope that helps!" in text


def test_only_the_closing_lines_after_the_card_say_it_again() -> None:
    """A fence or a table row after the card holds its own numbers (review, #2536)."""
    working = "$a = 1$  \n$x = 1 + 1$"
    after = 'So x is 3.\n\n| step | 3 |\n|---|---|\n\n```graph\n{"x": 3}\n```\n\nStep 3 done.'
    text, note = held_cards(_reply(working, "x = 3", after))
    assert note is None
    assert "x = 2\n```" in text and "So x is 2." in text
    assert "| step | 3 |" in text and '{"x": 3}' in text and "Step 3 done." in text


@pytest.mark.parametrize(
    ("working", "card", "note"),
    [
        # A card in powers of ten, a fraction or a multiple of pi is named, never rewritten
        # from its leading digits (review, #2536).
        (
            "$a = 2$  \n$b = 3$  \n$E = 2 \\times 10^3 + 3 \\times 10^3$",
            "E = 6 \\times 10^3",
            "Check the answer: $2 \\times 10^3 + 3 \\times 10^3 = 5 \\times 10^{3}$, not "
            "$6 \\times 10^3$.",
        ),
        ("$a = 5$  \n$b = 1$  \n$x = (5 + 1)/2$", "x = 7/2", None),
    ],
)
def test_a_card_that_is_no_plain_number_is_only_named(
    working: str, card: str, note: str | None
) -> None:
    reply = _reply(working, card)
    text, said = held_cards(reply)
    assert text == reply
    if note is not None:
        assert said == note


def test_a_heading_with_maths_above_the_card_is_no_working() -> None:
    """ "**Answer for $D$**" sits between the working and the card (review, #2536)."""
    reply = (
        "$D = 2^2 - 4(3)(1)$  \n$D = 4 - 12$\n\n**Answer for $D$**\n\n"
        "```answer\nverified: false\nD = −7\n```\n\nSince −7 is negative, there are no real roots."
    )
    text, note = held_cards(reply)
    assert note is None
    assert "D = -8" in text and "Since -8 is negative" in text


def test_a_card_value_in_its_own_maths_is_read() -> None:
    """ "D = $-7$" on the card (review, #2536)."""
    reply = _reply("$D = 2^2 - 4(3)(1)$  \n$D = 4 - 12$", "D = $-7$")
    text, note = held_cards(reply)
    assert note is None and "D = $-8$" in text


def test_the_note_never_lands_inside_a_card_left_open() -> None:
    """A card cut off at the length limit has no closer: the note went inside it, and the
    closer then shut the card after the note (review of #2592)."""
    from types import SimpleNamespace
    from typing import cast

    from app.modules.chat.finalize_passes import FinalizeState
    from app.modules.chat.finalize_subjects import check_working
    from app.services.md_fence_scan import iter_fences

    working = "**Solution**\n\n$\\text{part} = 32$  \n$\\text{total} = 5 + 20$"
    reply = f"{working}\n\n**Answer**\n\n```answer\nverified: false\ntotal = 37\n"
    state = SimpleNamespace(
        text=reply,
        server_text=False,
        was_cancelled=False,
        ctx=SimpleNamespace(
            verified_subject=None, solver_unverified=True, user_message_content="", worked=None
        ),
    )
    text = check_working(cast(FinalizeState, state))
    [card] = [fence for fence in iter_fences(text) if fence.lang == "answer"]
    assert card.closed
    assert "Check the answer" not in text[card.body_start : card.body_end]
    assert text.rstrip().endswith("not $37$.")


_JUNCTION = (
    "$\\vec{v}_f = -9.0435\\hat{i} + 8.6957\\hat{j}\\,\\mathrm{m/s}$\n\n**Answer (b)**\n\n"
    "```answer\nverified: false\n$-9.04\\,\\mathrm{m/s}$, $8.70\\,\\mathrm{m/s}$, "
    "$12.30\\,\\mathrm{m/s}$ ($43.9^\\circ$ north of west)\n```\n\n"
    "They move at **12.3 m/s**."
)


def test_a_vector_s_size_is_the_size_its_components_give() -> None:
    """Textbook round, 2026-11-26: the junction's cars carded 12.30 m/s for 12.55."""
    from app.modules.chat.working_cards import held_vector_sizes

    text = held_vector_sizes(_JUNCTION)
    assert "$12.55\\,\\mathrm{m/s}$ ($43.9^\\circ$" in text
    assert text.endswith("They move at **12.55 m/s**.")


def test_a_right_vector_size_stands() -> None:
    from app.modules.chat.working_cards import held_vector_sizes

    right = _JUNCTION.replace("12.30", "12.55").replace("12.3 ", "12.55 ")
    assert held_vector_sizes(right) == right


@pytest.mark.parametrize(
    ("card", "kept"),
    [
        ("$2.05\\,\\mathrm{N·m}$ (clockwise)", "$2.05\\,\\mathrm{N·m}$"),
        ("0.36\\,\\mathrm{N\\,m} \\text{ anticlockwise}", "0.36\\,\\mathrm{N\\,m}"),
        # Not a moment: a direction it has is the card's to keep.
        ("$5\\,\\mathrm{m/s}$ (clockwise)", "$5\\,\\mathrm{m/s}$ (clockwise)"),
    ],
)
def test_an_unchecked_moment_card_claims_no_sense(card: str, kept: str) -> None:
    from app.modules.chat.working_cards import without_unbacked_senses

    text = f"**Answer**\n\n```answer\nverified: false\n{card}\n```"
    assert without_unbacked_senses(text) == f"**Answer**\n\n```answer\nverified: false\n{kept}\n```"


@pytest.mark.parametrize(
    "card",
    [
        # A unit's power is no size (review of #2604: read as 1, it became s^{-13}).
        "(-9.04\\hat{i} + 8.70\\hat{j})\\,\\mathrm{m\\,s^{-1}}",
        "(-9.04\\hat{i} + 8.70\\hat{j})\\,\\mathrm{m\\,h^{-1}}",
        # An angle, however it is written, is no size.
        "$-9.04\\,\\mathrm{m/s}$, $8.70\\,\\mathrm{m/s}$, $43.9\\,^\\circ$",
        "$-9.04\\,\\mathrm{m/s}$, $8.70\\,\\mathrm{m/s}$, $43.9\\degree$",
        # A number in no unit of the components' is no size either.
        "$-9.04\\,\\mathrm{m/s}$, $8.70\\,\\mathrm{m/s}$, $12.30\\,\\mathrm{s}$",
    ],
)
def test_a_vector_card_with_no_size_of_its_own_stands(card: str) -> None:
    from app.modules.chat.working_cards import held_vector_sizes

    text = (
        "$\\vec{v}_f = -9.0435\\hat{i} + 8.6957\\hat{j}\\,\\mathrm{m/s}$\n\n**Answer**\n\n"
        f"```answer\nverified: false\n{card}\n```\n\n1 m/s is 1."
    )
    assert held_vector_sizes(text) == text


@pytest.mark.parametrize(
    ("card", "kept"),
    [
        ("2.05\\,\\text{N·m (clockwise)}", "2.05\\,\\text{N·m}"),
        ("2.05\\,\\text{N m clockwise}", "2.05\\,\\text{N m}"),
        ("2.05\\ \\text{N·m}\\ \\text{clockwise}", "2.05\\ \\text{N·m}"),
        ("$2.05\\,\\mathrm{N·m}$ (Counter-Clockwise)", "$2.05\\,\\mathrm{N·m}$"),
    ],
)
def test_a_sense_goes_with_its_group_never_half_of_it(card: str, kept: str) -> None:
    """Review of #2604: "\\text{N·m" was left open, and a "\\" escaped the closing "$"."""
    from app.modules.chat.working_cards import without_unbacked_senses

    text = f"**Answer**\n\n```answer\nverified: false\n{card}\n```"
    assert without_unbacked_senses(text) == f"**Answer**\n\n```answer\nverified: false\n{kept}\n```"


def test_check_working_holds_a_vector_size_and_drops_an_unbacked_sense() -> None:
    """The wiring: both card checks run in the working check (review of #2604)."""
    from types import SimpleNamespace
    from typing import cast

    from app.modules.chat.finalize_passes import FinalizeState
    from app.modules.chat.finalize_subjects import check_working

    moment = "**Answer (a)**\n\n```answer\nverified: false\n$2.05\\,\\mathrm{N·m}$ (clockwise)\n```"
    reply = f"**Solution**\n\n$M = 5 \\times 0.41$\n\n{moment}\n\n" + _JUNCTION
    state = SimpleNamespace(
        text=reply,
        server_text=False,
        was_cancelled=False,
        ctx=SimpleNamespace(
            verified_subject=None, solver_unverified=True, user_message_content="", worked=None
        ),
    )
    text = check_working(cast(FinalizeState, state))
    assert "(clockwise)" not in text
    assert "12.55\\,\\mathrm{m/s}" in text


def test_a_size_half_a_percent_off_is_no_rounding() -> None:
    """u4-11 in round 2 of #2604: 12.60 m/s for components of size 12.546 stood."""
    from app.modules.chat.working_cards import held_vector_sizes

    text = _JUNCTION.replace("12.30", "12.60")
    assert "$12.55\\,\\mathrm{m/s}$" in held_vector_sizes(text)

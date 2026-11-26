"""Every card's number by the one rule, whoever wrote it, save a chemistry solver's checked card,
which keeps its data's figures (``chat.card_numbers``)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.modules.chat.card_numbers import card_numbers
from app.modules.chemistry.block import VerifiedChemistry
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
        # Nothing above works -3.5 out: its figures as written, never a padded zero.
        ("x = 2 \\text{ or } x = -3.5", "x = 2 \\text{ or } x = -3.5"),
        ("20\\,\\mathrm{m/s}", "20\\,\\mathrm{m/s}"),
        ("6.022 \\times 10^{23}", "6.02 \\times 10^{23}"),
        (
            "0.2727\\,\\mathrm{A}",
            "0.27\\,\\mathrm{A}",
        ),  # two places below 1 too (owner, 2026-11-25)
        ("K_{p} = 1.2 \\times 10^{-4}", "K_{p} = 1.2 \\times 10^{-4}"),  # no figure added
        ("2400\\,\\mathrm{m^{2}}", "2400\\,\\mathrm{m^{2}}"),  # a unit's power is no number
        # A negative power in a unit is no number either (review).
        ("a = 9.8123\\,\\mathrm{m\\,s^{-2}}", "a = 9.81\\,\\mathrm{m\\,s^{-2}}"),
        ("c = 0.12345\\,\\mathrm{mol\\,L^-1}", "c = 0.12\\,\\mathrm{mol\\,L^-1}"),
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


def _state(text: str, question: str, verified: object) -> object:
    from types import SimpleNamespace

    ctx = SimpleNamespace(
        user_message_content=question, verified_subject=verified, photo_uncertain=None
    )
    return SimpleNamespace(text=text, ctx=ctx)


def _chemistry(question: str) -> VerifiedChemistry:
    from app.modules.chemistry.block import build_verified_chemistry
    from app.modules.chemistry.extract import extract_chemistry_intent

    intent = extract_chemistry_intent(question)
    assert intent is not None
    verified = build_verified_chemistry(intent)
    assert verified is not None
    return verified


_TITRATION = (
    "25.00 mL of HCl is titrated with 0.1000 M NaOH and it takes 32.45 mL to reach the "
    "endpoint. What is the concentration of HCl?"
)


@pytest.mark.parametrize(
    ("question", "working", "card", "shown"),
    [
        # Four figures of data: the card keeps 0.1298, never the rule's 0.130.
        (
            _TITRATION,
            "$c = 0.12980\\,\\mathrm{mol/L}$",
            "c_{2} = 0.1298\\,\\mathrm{mol/L}",
            "c_{2} = 0.1298\\,\\mathrm{mol/L}",
        ),
        # Two figures of data (4 g, raised to the two-figure floor): 36 g over a working of
        # 35.74 g stays so, never the rule's 35.74.
        (
            "how much water do i get if i burn 4 g of hydrogen",
            "$m = 35.74\\,\\mathrm{g}$",
            "m = 36\\,\\mathrm{g}",
            "m = 36\\,\\mathrm{g}",
        ),
        # Three figures: a dilution to 0.0500 M keeps its zeros, never the rule's 0.05.
        (
            "25.0 mL of 0.200 M HCl is diluted to 100.0 mL. What is the new concentration?",
            "$c_{2} = 0.05\\,\\mathrm{mol/L}$",
            "c_{2} = 0.0500\\,\\mathrm{mol/L}",
            "c_{2} = 0.0500\\,\\mathrm{mol/L}",
        ),
        # A question that asks a precision still gets it, from the working's value.
        (
            "how much water do i get if i burn 4 g of hydrogen, to 2 decimal places",
            "$m = 35.74\\,\\mathrm{g}$",
            "m = 36\\,\\mathrm{g}",
            "m = 35.74\\,\\mathrm{g}",
        ),
    ],
)
def test_a_chemistry_card_keeps_its_data_s_figures(
    question: str, working: str, card: str, shown: str
) -> None:
    from app.modules.chat.card_numbers import format_card_numbers

    verified = _chemistry(question.removesuffix(", to 2 decimal places"))
    reply = f"{working}\n\n**Answer**\n\n" + _card(card, "true")
    state = _state(reply, question, verified)
    assert format_card_numbers(state) == f"{working}\n\n**Answer**\n\n" + _card(shown, "true")  # type: ignore[arg-type]


def test_a_physics_card_still_follows_the_rule() -> None:
    from app.modules.chat.card_numbers import format_card_numbers
    from app.services.solving import VerifiedPhysicsBlock

    reply = "$P = 109324.04\\,\\mathrm{Pa}$\n\n" + _card(
        "1.09 \\times 10^{5}\\,\\mathrm{Pa}", "true"
    )
    state = _state(reply, "find P", VerifiedPhysicsBlock(text=""))
    assert _card("109324.04\\,\\mathrm{Pa}", "true") in format_card_numbers(state)  # type: ignore[arg-type]
    # A chemistry turn with a physics part: every card follows the rule (review).
    mixed = replace(_chemistry(_TITRATION), question_parts=(VerifiedPhysicsBlock(text=""),))
    state = _state(reply, "find P", mixed)
    assert _card("109324.04\\,\\mathrm{Pa}", "true") in format_card_numbers(state)  # type: ignore[arg-type]


def test_the_model_s_unchecked_card_on_a_chemistry_turn_follows_the_rule() -> None:
    """Only the solver's checked card keeps its figures: a card the model wrote, left
    unchecked because the reply contradicted the solve, is shown by the rule (review)."""
    from app.modules.chat.card_numbers import format_card_numbers

    verified = _chemistry(_TITRATION)
    reply = "$m = 345.1234\\,\\mathrm{g}$\n\n" + _card("m = 345.1234\\,\\mathrm{g}")
    state = _state(reply, _TITRATION, verified)
    assert _card("m = 345.12\\,\\mathrm{g}") in format_card_numbers(state)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("question", "working", "card", "shown"),
    [
        # The working knows 2.361 to three places: the asked precision takes it.
        (
            "Clausius-Clapeyron: P1=1.0, T1=300, T2=350, dH=15000. Find P2.",
            "$P_{2} = 1.0 \\times \\exp [-(15000) / (8.3145) \\times (1/350 - 1/300)] = 2.361$",
            "P_{2} = 2.4",
            "P_{2} = 2.361",
        ),
        # A working that stops on the rounded value knows no more: the card stays (review).
        (
            "Clausius-Clapeyron: P1=1.0, T1=300, T2=350, dH=15000. Find P2.",
            "$P_{2} = 2.4$",
            "P_{2} = 2.4",
            "P_{2} = 2.4",
        ),
    ],
)
def test_an_asked_precision_takes_a_chemistry_card_only_as_far_as_the_working_knows(
    question: str, working: str, card: str, shown: str
) -> None:
    from app.modules.chat.card_numbers import format_card_numbers

    reply = f"{working}\n\n**Answer**\n\n" + _card(card, "true")
    state = _state(reply, question + " to 3 decimal places", _chemistry(question))
    assert format_card_numbers(state).endswith(_card(shown, "true"))  # type: ignore[arg-type]


def test_a_power_of_ten_card_knows_only_its_mantissa_s_figures() -> None:
    """3.4 x 10^2 g knows two figures: "to 3 significant figures" with no working that reached
    the value leaves the card as written, never 340 g (review)."""
    from app.modules.chat.card_numbers import format_card_numbers

    question = "What is the mass of 3.5 mol of H2SO4 in grams"
    reply = "$m \\approx 340\\,\\mathrm{g}$\n\n**Answer**\n\n" + _card(
        "m = 3.4 \\times 10^{2}\\,\\mathrm{g}", "true"
    )
    state = _state(reply, question + ", to 3 significant figures", _chemistry(question))
    assert format_card_numbers(state) == reply  # type: ignore[arg-type]


def test_an_uncertain_photo_s_unchecked_solver_card_keeps_its_figures() -> None:
    """A photo read uncertainly unchecks the solver's card; it keeps 0.1298, never the rule's
    0.130 (review)."""
    from app.modules.chat.card_numbers import format_card_numbers

    reply = "$c = 0.12980\\,\\mathrm{mol/L}$\n\n**Answer**\n\n" + _card(
        "c_{2} = 0.1298\\,\\mathrm{mol/L}"
    )
    state = _state(reply, _TITRATION, _chemistry(_TITRATION))
    state.ctx.photo_uncertain = True  # type: ignore[attr-defined]
    assert format_card_numbers(state) == reply  # type: ignore[arg-type]


def test_an_uncertain_photo_s_model_card_still_follows_the_rule() -> None:
    """On that photo the model's own card, a value the solver did not reach, is rounded by the
    rule (review)."""
    from app.modules.chat.card_numbers import format_card_numbers

    reply = "$c = 0.12980\\,\\mathrm{mol/L}$\n\n**Answer**\n\n" + _card(
        "c_{2} = 0.1312\\,\\mathrm{mol/L}"
    )
    state = _state(reply, _TITRATION, _chemistry(_TITRATION))
    state.ctx.photo_uncertain = True  # type: ignore[attr-defined]
    assert "0.1312" not in format_card_numbers(state)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "written",
    [
        r"3.2\times10^{-19}",
        r"3.2 \times 10^{-19}",
        # TeX's spacing around the times sign is the number's (review of #2592): the card
        # read one number and rewrote only "3.2", leaving its power, so it showed 10^-38.
        r"3.2\,\times\,10^{-19}",
        r"3.2\;\cdot\;10^{-19}",
        # Prose spellings: every one is one number, written once by the rule.
        "3.2 × 10^-19",
        "3.2 x 10^-19",
        "3.2*10^-19",
        "3.2 · 10^-19",
        "3.2 × 10⁻¹⁹",
        "3.2 × 10^−19",
        "3.2e-19",
    ],
)
def test_a_card_in_powers_of_ten_is_written_once_whatever_its_spelling(written: str) -> None:
    reply = _card(f"E = {written}\\,\\mathrm{{J}}")
    assert card_numbers(reply, Precision()) == _card("E = 3.2 \\times 10^{-19}\\,\\mathrm{J}")


def test_a_card_of_a_multi_digit_power_keeps_it_whole() -> None:
    """10^23 is ten to the 23rd: read as 10^2 and a 3, the card was two numbers."""
    reply = _card("N = 6.02 × 10^23")
    assert card_numbers(reply, Precision()) == _card("N = 6.02 \\times 10^{23}")


@pytest.mark.parametrize(
    ("working", "card", "shown"),
    [
        # A model's zero past its last figure is no figure: 20.1 under "v = 20.1 m/s".
        ("$v = 20.1\\,\\mathrm{m/s}$", "20.10\\,\\mathrm{m/s}", "20.1\\,\\mathrm{m/s}"),
        # Worked out again where the working can: I = 5/2 is 2.50 A, known to its zeros.
        ("$I = \\frac{5}{2}$", "2.50\\,\\mathrm{A}", "2.50\\,\\mathrm{A}"),
        # The working wrote it to more places: 8.6957 is 8.70, its zero known.
        (
            "$\\vec{v} = 8.6957\\hat{j}$",
            "8.70\\hat{j}\\,\\mathrm{m/s}",
            "8.70\\hat{j}\\,\\mathrm{m/s}",
        ),
    ],
    ids=["padded", "known-zeros", "worked-places"],
)
def test_a_model_s_padded_zero_is_no_figure_it_knows(working: str, card: str, shown: str) -> None:
    """Textbook round, 2026-11-26: 21.65 m/s carded 21.70, 20.106 m/s carded 20.10."""
    reply = f"{working}\n\n**Answer**\n\n{_card(card)}"
    assert card_numbers(reply, Precision()).endswith(_card(shown))


def test_a_server_card_keeps_its_zeros() -> None:
    assert card_numbers(_card("2.50\\,\\mathrm{A}", "true"), Precision()) == _card(
        "2.50\\,\\mathrm{A}", "true"
    )


@pytest.mark.parametrize(
    ("card", "shown"),
    [
        (
            "\\begin{pmatrix}7/9\\\\-23/9\\end{pmatrix}\\,\\mathrm{m/s}",
            "\\begin{pmatrix}0.78\\\\-2.56\\end{pmatrix}\\,\\mathrm{m/s}",
        ),
        ("v = \\frac{30}{7}\\,\\mathrm{m/s}", "v = 4.29\\,\\mathrm{m/s}"),
        ("x = 1/3", "x = 1/3"),  # a pure number keeps maths' exact fraction
    ],
)
def test_a_measured_card_s_fractions_are_decimals(card: str, shown: str) -> None:
    """A velocity of (7/9, -23/9) m/s is read to two places, never in ninths."""
    assert card_numbers(_card(card), Precision()) == _card(shown)


def test_a_named_vector_card_follows_the_rule() -> None:
    reply = _card("\\vec{a} = 0.298\\hat{i}\\ \\text{m/s}^2")
    assert card_numbers(reply, Precision()) == _card("\\vec{a} = 0.30\\hat{i}\\ \\text{m/s}^2")

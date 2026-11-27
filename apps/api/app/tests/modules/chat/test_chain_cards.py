# ruff: noqa: RUF002, RUF003 -- replies write × and −.
"""Each unchecked card held to the value its own working's method reaches, worked again at
full precision (textbook round 2, 2026-11-26: twelve wrong and twenty partial answers came
from the model's own working, none from a checked one)."""

from __future__ import annotations

import pytest

from app.modules.chat.chain_cards import held_to_chains


def _card(value: str) -> str:
    return f"\n\n**Answer**\n\n```answer\nverified: false\n{value}\n```"


def _card_of(text: str) -> str:
    return text.split("```answer\nverified: false\n", 1)[1].split("\n```", 1)[0]


# A power of ten lost between two forms: 2.0 / (400 × 1.0 × 10⁻⁴) is 50, not 50000 (u8-28).
_HEAT = (
    "**Substitution**  \n"
    "$H = \\frac{100 - 30}{\\frac{2.0}{400 \\times 1.0 \\times 10^{-4}} + "
    "\\frac{1.2}{50 \\times 1.0 \\times 10^{-4}}}$  \n"
    "$H = \\frac{70}{50000 + 240000}$  \n"
    "$H = 2.4138 \\times 10^{-4}\\,\\mathrm{W}$"
)
# The same slip, carried into a later part through the wrong form (u8-08).
_WIRE = (
    "$F = 4.905\\,\\mathrm{N}$  \n"
    "$e = \\frac{4.905 \\times 1.5}{(1.0 \\times 10^{11}) \\times (2.25\\pi \\times 10^{-8})}$  \n"
    "$e = \\frac{7.3575}{2250\\pi \\times 10^{-3}}$  \n"
    "$e = \\frac{3.27}{\\pi}$  \n"
    "$e \\approx 1.041\\,\\mathrm{m}$"
    + _card("1.04\\,\\mathrm{m}")
    + "\n\n**Substitution**  \n$U = \\frac{1}{2} \\times 4.905 \\times \\frac{3.27}{\\pi}$  \n"
    "$U \\approx 1.278\\,\\mathrm{J}$" + _card("1.28\\,\\mathrm{J}")
)
# A rate per minute put in for one per second (u6-01).
_FLYWHEEL = (
    "**Given**  \n$N = 250\\,\\mathrm{rev/min}$\n\n"
    "**Formula**  \n$\\omega = 2\\pi N$\n\n"
    "**Substitution**  \n$\\omega = 2\\pi \\times 250$"
)


@pytest.mark.parametrize(
    ("reply", "question", "card", "corrected"),
    [
        (_HEAT + _card("2.41 \\times 10^{-4}\\,\\mathrm{W}"), "", "0.24\\,\\mathrm{W}", "slips at"),
        # A last expression worked in the head: 171.5 / √3 is 99.02 (u7-08).
        (
            "$N_{wall} = \\frac{686}{4\\sqrt{3}}$  \n$N_{wall} = \\frac{171.5}{\\sqrt{3}}$\n\n"
            "Taking moments about the foot removes the floor's forces."
            + _card("99.04\\,\\mathrm{N}"),
            "",
            "99.02\\,\\mathrm{N}",
            "without rounding",
        ),
        # A slip in one term carried into the sum (u6-19): 30.11 on its own inputs, not 30.09.
        (
            "$r = 9.00\\,\\mathrm{cm} = 0.09\\,\\mathrm{m}$\n\n"
            "$\\omega = \\frac{4.55}{0.09}$  \n$\\omega = 50.56\\,\\mathrm{rad/s}$  \n"
            "$K_{trans} = \\frac{1}{2}(7.27)(4.55)^2$  \n$K_{trans} = 75.25\\,\\mathrm{J}$  \n"
            "$K_{rot} = \\frac{1}{2}(\\frac{2}{5})(7.27)(0.09)^2(50.56)^2$  \n"
            "$K_{rot} = 30.09\\,\\mathrm{J}$  \n$K_{total} = 75.25 + 30.09$"
            + _card("105.32\\,\\mathrm{J}"),
            "A 7.27 kg ball with radius 9.00 cm rolls at 4.55 m/s.",
            "105.36\\,\\mathrm{J}",
            "K_{rot} = 30.09",
        ),
    ],
)
def test_a_card_its_working_contradicts_takes_the_workings_value(
    reply: str, question: str, card: str, corrected: str
) -> None:
    text, notes = held_to_chains(reply, question)
    note, claim = notes.corrected, notes.claim
    assert card in _card_of(text)
    assert note is not None and corrected in note
    assert claim is None


def test_a_slip_carried_through_a_wrong_form_is_put_right_in_the_later_part() -> None:
    text, notes = held_to_chains(_WIRE, "")
    note = notes.corrected
    cards = text.split("```answer\nverified: false\n")[1:]
    assert cards[0].startswith("0.00104\\,\\mathrm{m}")
    assert cards[1].startswith("0.00255\\,\\mathrm{J}")
    assert note is not None and "2250\\pi \\times 10^{-3}" in note


@pytest.mark.parametrize(
    ("reply", "question"),
    [
        # Right: 10 × 9.81 × cos 30° is 84.957, whatever 0.8660 makes it (live, 2026-11-27).
        ("$N = 10 \\times 9.81 \\times 0.8660$" + _card("84.96\\,\\mathrm{N}"), "θ = 30°"),
        # A conversion the formula holds itself: 2πN/60 is per second already.
        (
            "$N = 250\\,\\mathrm{rev/min}$\n\n$\\omega = \\frac{2\\pi N}{60}$\n\n"
            "**Substitution**  \n$\\omega = \\frac{2\\pi \\times 250}{60}$"
            + _card("26.18\\,\\mathrm{rad/s}"),
            "",
        ),
        # A unit changed on the way: 72 km/h is 20 m/s.
        (
            "$v = 72\\,\\mathrm{km/h} = \\frac{72}{3.6} = 20\\,\\mathrm{m/s}$"
            + _card("20\\,\\mathrm{m/s}"),
            "",
        ),
        # A thousand times the chain, with no unit and no slip: a prefix the working never named.
        ("$m = 2500 \\times 0.4$" + _card("1\\,\\mathrm{kg}"), ""),
        # A count rounded as the question needs: 4 buses for 3.75.
        ("$n = \\frac{150}{40}$" + _card("4"), ""),
        # A card naming another value than the last line: never held to it.
        ("$a = 2 \\times 3.5$  \n$t = \\frac{14}{a}$" + _card("a = 7"), ""),
        # A server's checked card is the server's.
        ("$x = 2 \\times 3$\n\n```answer\nverified: true\n7\n```", ""),
    ],
)
def test_a_card_its_working_holds_stands(reply: str, question: str) -> None:
    text, notes = held_to_chains(reply, question)
    note = notes.corrected
    assert text == reply
    assert note is None


def test_a_card_holding_the_value_more_coarsely_takes_it_without_a_note() -> None:
    """56.6 for 56.58 is padded to 56.60 by the rule; the working knows 56.58 (u7-09)."""
    reply = "$N_{wall} = \\frac{98}{1.732}$  \n$N_{wall} \\approx 56.58\\,\\mathrm{N}$" + _card(
        "56.6\\,\\mathrm{N}"
    )
    text, notes = held_to_chains(reply, "The angle is 60°.")
    note = notes.corrected
    assert _card_of(text) == "56.58\\,\\mathrm{N}"
    assert note is None


def test_a_name_said_in_a_sentence_keeps_the_card_on_its_chain() -> None:
    """ "the wall's force $N_w$" between f = N_w and the card (u7-09, live 2026-11-27)."""
    reply = (
        "$N_w = \\frac{196}{2 \\sqrt{3}}$  \n$N_w \\approx 56.58\\,\\mathrm{N}$  \n$f = N_w$\n\n"
        "Friction balances the wall's force $N_w$." + _card("56.6\\,\\mathrm{N}")
    )
    text, _notes = held_to_chains(reply, "")
    assert _card_of(text) == "56.58\\,\\mathrm{N}"


def test_the_wrong_value_said_again_after_the_card_follows_it() -> None:
    reply = (
        _HEAT
        + _card("2.41 \\times 10^{-4}\\,\\mathrm{W}")
        + "\n\nSo heat flows at 2.41 \\times 10^{-4} W."
    )
    text, _notes = held_to_chains(reply, "")
    assert "2.41 \\times 10^{-4}" not in text.split("```", 2)[2]


def test_a_claim_the_workings_values_contradict_is_named() -> None:
    """½mv₅² was said to be 405.5 J, the kinematics value; with m = 10, v₅ = 5.66 it is 160.3
    (live, 2026-11-27)."""
    reply = (
        "$m = 10\\,\\mathrm{kg}$  \n$v_5 = \\sqrt{2 \\times 3.206 \\times 5}$  \n$v_5 = 5.66\\,\\mathrm{m/s}$\n\n"
        "Energy check: the kinetic energy is $490.5 - 84.96 = 405.54$ J, giving "
        "$\\tfrac{1}{2}mv_5^2 = 405.5$ J, the same as the kinematics value."
    )
    _text, notes = held_to_chains(reply, "")
    note, claim = notes.corrected, notes.claim
    assert note is None
    assert claim is not None and "160.30" in claim and "405.5" in claim


@pytest.mark.parametrize(
    "reply",
    [
        # An equation solved for its unknown is no claim (u7-06).
        "$F = 34\\,\\mathrm{N}$\n\nThen $2.8 = 1.1 - 0.05F$ gives $0.05F = -1.7$.",
        # A formula with a name of two values is no claim.
        "$v = 3\\,\\mathrm{m/s}$  \n\n$v = 5\\,\\mathrm{m/s}$\n\nso $2v = 6$.",
        # A claim that holds.
        "$m = 2\\,\\mathrm{kg}$  \n$v = 3\\,\\mathrm{m/s}$\n\nso $\\tfrac{1}{2}mv^2 = 9$ J.",
    ],
)
def test_no_claim_is_named_where_the_working_bears_it_out(reply: str) -> None:
    assert held_to_chains(reply, "")[1].claim is None


def test_a_card_under_an_equation_solved_for_one_name_is_its_solution() -> None:
    """21250 / 241.67 is 87.93, carded 87.80 (u8-28, live 2026-11-27)."""
    reply = "$20000 + 1250 = 200\\theta + 41.67\\theta$  \n$21250 = 241.67\\theta$" + _card("87.80")
    text, notes = held_to_chains(reply, "")
    assert _card_of(text) == "87.93"
    assert notes.corrected is not None


def test_a_stated_value_a_power_of_ten_off_its_own_working_stands_for_the_worked_one() -> None:
    """The givens said A = 3.142 × 10⁻⁷ m², the working made it 3.142 × 10⁻⁶ m², and the
    stress was worked on the stated one (u8-07, live 2026-11-27)."""
    reply = (
        "$A = 3.142 \\times 10^{-7}\\,\\mathrm{m^2}$\n\n**Substitution**  \n"
        "$A = \\pi \\left(\\frac{0.002}{2}\\right)^2$  \n"
        "$A = 3.142 \\times 10^{-6}\\,\\mathrm{m^2}$\n\n"
        "$\\sigma = \\frac{19.62}{3.142 \\times 10^{-7}}$  \n"
        "$\\sigma = 6.244 \\times 10^{7}\\,\\mathrm{Pa}$" + _card("62444302.99\\,\\mathrm{Pa}")
    )
    text, notes = held_to_chains(reply, "A load of 2.0 kg, a wire of diameter 2.0 mm.")
    assert _card_of(text) == "6245239.97\\,\\mathrm{Pa}"
    assert notes.corrected is not None and "slips" in notes.corrected


def test_a_name_put_in_a_power_of_ten_off_its_value_is_a_slip() -> None:
    reply = (
        "$\\sigma = 6.245 \\times 10^{6}\\,\\mathrm{Pa}$\n\n$E = \\frac{\\sigma}{\\varepsilon}$\n\n"
        "**Substitution**  \n$E = \\frac{6.245 \\times 10^7}{6.0 \\times 10^{-5}}$  \n"
        "$E = 1.041 \\times 10^{12}\\,\\mathrm{Pa}$" + _card("1.04 \\times 10^{12}\\,\\mathrm{Pa}")
    )
    text, _notes = held_to_chains(reply, "")
    assert _card_of(text).startswith("1.04 \\times 10^{11}")


def test_a_slip_no_card_carries_is_named_with_the_value_its_own_method_gives() -> None:
    """f = N_w, then f = 113.25 N (u7-09, live 2026-11-27): no single card to correct."""
    reply = (
        "$N_w = \\frac{98}{1.732}$  \n$N_w = 56.58\\,\\mathrm{N}$  \n$f = N_w$  \n"
        "$f = 113.25\\,\\mathrm{N}$" + _card("196\\,\\mathrm{N},\\quad 113.30\\,\\mathrm{N}")
    )
    _text, notes = held_to_chains(reply, "at 60° to the ground")
    assert notes.slip is not None and "56.58" in notes.slip


@pytest.mark.parametrize(
    "reply",
    [
        # One name for two events: t = 205 s, then another t.
        "$t = 205\\,\\mathrm{s}$\n\n**(b)**  \n$t = \\frac{20 - 15}{5}$" + _card("1\\,\\mathrm{s}"),
        # A stated value in another unit is no slip: 100 g is 0.1 kg.
        "$m = 100\\,\\mathrm{g}$\n\n$m = \\frac{100}{1000}$  \n$m = 0.1\\,\\mathrm{kg}$"
        + _card("0.1\\,\\mathrm{kg}"),
    ],
)
def test_a_name_used_again_is_no_slip(reply: str) -> None:
    text, notes = held_to_chains(reply, "")
    assert text == reply
    assert notes.slip is None
    assert notes.corrected is None


@pytest.mark.parametrize(
    ("reply", "question"),
    [
        # 250 rev/min is 26.18 rad/s: a turn and a radian are not read for certain.
        (_FLYWHEEL + _card("\\omega = 1570.80\\,\\mathrm{rad/s}"), ""),
        (
            "$\\omega = 250\\,\\mathrm{rev/min} = 26.18\\,\\mathrm{rad/s}$  \n"
            "$v = 26.18 \\times 0.30$" + _card("7.85\\,\\mathrm{m/s}"),
            "",
        ),
        # 632.8 nm put in as metres (review of #2612).
        (
            "$\\lambda = 632.8\\,\\mathrm{nm}$\n\n$f = \\frac{c}{\\lambda}$\n\n**Substitution**  \n"
            "$f = \\frac{3.00 \\times 10^{8}}{632.8 \\times 10^{-9}}$"
            + _card("4.74 \\times 10^{14}\\,\\mathrm{Hz}"),
            "",
        ),
        # 400 K is 126.85 °C; 0.5236 rad is 30°.
        (
            "$T_2 = \\frac{2 \\times 300}{1.5} = 400\\,\\mathrm{K} = 126.85\\,^\\circ\\mathrm{C}$"
            + _card("126.85\\,^\\circ\\mathrm{C}"),
            "",
        ),
        ("$\\theta = \\frac{\\pi}{6} = 0.5236\\,\\mathrm{rad}$" + _card("30^\\circ"), ""),
        # km h⁻¹ is one unit of two groups.
        (
            "$v = 72\\,\\mathrm{km}\\,\\mathrm{h}^{-1} = 20\\,\\mathrm{m}\\,\\mathrm{s}^{-1}$  \n"
            "$d = 20 \\times 15$" + _card("300\\,\\mathrm{m}"),
            "",
        ),
        # A given worked in its own unit: 9.00 cm squared is cm².
        (
            "$r = 9.00\\,\\mathrm{cm} = 0.09\\,\\mathrm{m}$\n\n$A = \\pi r^2$\n\n**Substitution**  \n"
            "$A = \\pi (9.00)^2$" + _card("254.47\\,\\mathrm{cm^2}"),
            "radius 9.00 cm",
        ),
        # "2.00" carried never makes the 2 of a half 1.998.
        (
            "$t = \\frac{19.6}{9.81} = 2.00\\,\\mathrm{s}$  \n$E = \\frac{1}{2}(3)(4)^2$"
            + _card("24.0\\,\\mathrm{J}"),
            "",
        ),
        # An alias keeps its source's rounding.
        (
            "$v = \\sqrt{2 \\times 9.8 \\times 1.5} = 5.4$  \n$p = 2.0 \\times 5.4 = 10.84$  \n$J = p$  \n"
            "$J = 10.84$" + _card("10.84\\,\\mathrm{N\\,s}"),
            "",
        ),
    ],
)
def test_a_reading_the_check_is_not_sure_of_changes_nothing(reply: str, question: str) -> None:
    text, notes = held_to_chains(reply, question)
    assert text == reply
    assert notes.corrected is None
    assert notes.slip is None


@pytest.mark.parametrize(
    "reply",
    [
        "$m = 500\\,\\mathrm{g}$  \n$v = 3\\,\\mathrm{m/s}$\n\nso $\\tfrac{1}{2}mv^2 = 2.25\\,\\mathrm{J}$.",
        "$m = 10\\,\\mathrm{kg}$  \n$v = 9\\,\\mathrm{m/s}$\n\nso $\\tfrac{1}{2}mv^2 = 0.405\\,\\mathrm{kJ}$.",
        "$m = 10\\,\\mathrm{kg}$  \n$v = 9\\,\\mathrm{m/s}$\n\nso $\\tfrac{1}{2}mv^2 = 0.405$ kJ.",
    ],
)
def test_a_claim_is_worked_in_its_units(reply: str) -> None:
    assert held_to_chains(reply, "")[1].claim is None


def test_a_correction_after_a_card_never_reaches_the_next_parts_working() -> None:
    reply = (
        _HEAT
        + _card("2.41 \\times 10^{-4}\\,\\mathrm{W}")
        + "\n\n**(b)**  \n$Q = 2.41 \\times 10^{-4} \\times 60 = 0.0145\\,\\mathrm{J}$"
        + _card("0.0145\\,\\mathrm{J}")
    )
    text, _notes = held_to_chains(reply, "")
    assert "$Q = 2.41 \\times 10^{-4} \\times 60" in text


def test_the_working_pass_corrects_the_card_and_names_it_over_the_steps_note() -> None:
    """The wiring: the check corrects the card, and its note stands in place of the step's."""
    from app.modules.chat.working_pass import checked_working

    reply = "**Solution**\n\n" + _HEAT + _card("2.41 \\times 10^{-4}\\,\\mathrm{W}")
    text = checked_working(reply, "", school=True, laid_out=False, decimal_comma=False)
    assert "verified: false\n0.24\\,\\mathrm{W}" in text
    assert text.count("Corrected:") == 1
    assert "Check this step" not in text


@pytest.mark.parametrize(
    "reply",
    [
        # The server's value, under the formal reader's line, is the server's.
        _HEAT + "\n\n**Answer**\n\nWorked out again from the values in the question:\n\n"
        "```answer\nverified: false\n2.41 \\times 10^{-4}\\,\\mathrm{W}\n```",
        # The largest of several values the part worked out.
        "$a_1 = \\frac{15}{20} = 0.75\\,\\mathrm{m/s^2}$  \n$a_2 = \\frac{5}{5} = 1\\,\\mathrm{m/s^2}$  \n"
        "$a_3 = \\frac{-20}{30} = -0.67\\,\\mathrm{m/s^2}$" + _card("1\\,\\mathrm{m/s^2}"),
    ],
)
def test_a_card_that_is_not_the_last_chains_own_stands(reply: str) -> None:
    text, notes = held_to_chains(reply, "")
    assert text == reply
    assert notes.corrected is None

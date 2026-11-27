"""A ```worked block's symbols as the phone draws them (Grade 11 physics round, 2026-11-26).

The model wrote a Greek letter by its name ("theta | 60", "omega_0 = \\frac{2\\pi}{T}"), a
command run into a letter ("\\DeltaP_h"), a word or an option's numeral as what is asked
("equilibrium", "iii"), the part letters as symbols ("a | graph description"), the contract's
own "what (a) finds", "vector" as a unit, and one part's working twice.
"""

from __future__ import annotations

import pytest

from app.modules.chat.prompt_constants.worked import WORKED_BLOCK_CONTRACT, WORKING_ONCE
from app.modules.chat.worked_answers import answer_lines
from app.modules.chat.worked_asks import fitted
from app.modules.chat.worked_render import WorkedLayout, render_worked
from app.modules.chat.worked_solution import Answer, Given, assemble, read_record
from app.modules.chat.worked_text import is_word_symbol, tidy_symbol, tidy_tex
from app.services.workout import SELF_CHECK_PROMPT_RULE

PHYSICS = WorkedLayout(law_heading=True)


def _laid_out(block: str) -> str:
    records = [read_record(line) for line in block.strip().split("\n")]
    return render_worked(assemble([r for r in records if r is not None]), PHYSICS)


@pytest.mark.parametrize(
    ("tex", "shown"),
    [
        ("theta = 60^\\circ", "\\theta = 60^\\circ"),
        ("omega_0 = \\frac{2\\pi}{T}", "\\omega_0 = \\frac{2\\pi}{T}"),
        ("\\cos theta", "\\cos \\theta"),
        ("2theta", "2\\theta"),
        ("\\DeltaP_h = 5", "\\Delta P_h = 5"),
        ("\\Deltat", "\\Delta t"),
        # As written: a command, a word group, a product, a longer word.
        ("\\theta + \\beta", "\\theta + \\beta"),
        ("\\text{theta wave}", "\\text{theta wave}"),
        ("p = mu", "p = mu"),
        ("\\varepsilon_0", "\\varepsilon_0"),
        ("\\phantom{x}", "\\phantom{x}"),
        ("thetas", "thetas"),
        # A unit after a number: pounds per square inch, never psi the letter (review of #2602).
        (
            "P_2 = 30 \\times \\frac{310}{290} = 32.1 psi",
            "P_2 = 30 \\times \\frac{310}{290} = 32.1 psi",
        ),
        ("p = 32.1\\,psi", "p = 32.1\\,psi"),
        # Every other name after a number is its letter: only psi is also a unit.
        ("F_d = 0.5 rho v^2 C_d A", "F_d = 0.5 \\rho v^2 C_d A"),
        ("x = 2 theta", "x = 2 \\theta"),
        ("y = 3\\,omega t", "y = 3\\,\\omega t"),
    ],
)
def test_a_greek_name_in_maths_is_its_letter(tex: str, shown: str) -> None:
    assert tidy_tex(tex) == shown


def test_a_greek_symbol_reads_as_its_letter_in_every_line() -> None:
    text = _laid_out(
        "given: theta | 60 | ° | angle\nrequired: F | force\n"
        "formula: Force | F = mg\\cos theta\nanswer: F | 3 | N"
    )
    assert "$\\theta = 60" in text and "$\\theta$ = angle" in text
    assert "theta" not in text.replace("\\theta", "")


@pytest.mark.parametrize(
    ("symbol", "word"),
    [
        ("graph", True),
        ("equilibrium", True),
        ("iii", True),
        # Also an initial velocity's symbols (review of #2602).
        ("vi", False),
        ("iv", False),
        ("ix", False),
        ("theta", False),
        ("vmax", False),
        ("v", False),
        ("F_{net}", False),
    ],
)
def test_a_word_is_no_symbol(symbol: str, word: bool) -> None:
    assert is_word_symbol(symbol) is word


def test_what_is_asked_in_words_reads_as_words() -> None:
    text = _laid_out(
        "required: equilibrium |\nrequired: graph | velocity-time graph\n"
        "formula: Net force | F_{net} = 0\nanswer: | yes | |"
    )
    assert "$equilibrium$" not in text and "$graph$" not in text
    assert "velocity-time graph" in text


def test_part_letters_given_as_symbols_are_no_symbols() -> None:
    text = _laid_out(
        "required: a | graph description\nrequired: b | time of greatest acceleration\n"
        "part: a | graph\nsay: The graph rises.\npart: b | greatest acceleration\n"
        "formula: Acceleration | a_3 = \\frac{\\Delta v}{t}\nanswer: | Between 80 s and 95 s | |"
    )
    assert "(a) graph description" in text
    assert "(b) time of greatest acceleration" in text


def test_letters_the_working_sets_are_the_unknowns() -> None:
    # "Find a and b if 2a + b = 7 and a - b = 2": a and b are the answers, never part letters
    # (review of #2602).
    text = _laid_out(
        "required: a | first number\nrequired: b | second number\n"
        "step: 3a = 9 | add the equations\nstep: a = 3 | divide by 3\n"
        "step: b = 7 - 2a = 1 | substitute\nanswer: a | 3 |\nanswer: b | 1 |"
    )
    assert "$a$ (first number)" in text and "$b$ (second number)" in text


def test_the_contracts_placeholder_is_no_title() -> None:
    text = _laid_out(
        "required: a \\times b | what (a) finds\nrequired: b \\times a | what (b) finds\n"
        "part: a | what (a) finds\nsubstitution: a \\times b = 3\nanswer: a \\times b | 3 |\n"
        "part: b | What (b) finds\nsubstitution: b \\times a = -3\nanswer: b \\times a | -3 |"
    )
    assert "finds" not in text.lower()


def test_vector_names_no_unit() -> None:
    given = read_record("given: a | 8i + j - 2k | vector |")
    assert isinstance(given, Given) and given.unit == ""


def test_a_part_worked_twice_shows_its_working_once() -> None:
    working = "formula: Conversion | h = 66 \\times c\nsubstitution: h = 167.64\\,\\mathrm{cm}"
    text = _laid_out(
        f"given: c | 2.54 | cm/in | factor\nrequired: h | height\n{working}\n"
        f"part: a | height\n{working}\nanswer: h | 167.64 | cm"
    )
    assert text.count("$h = 167.64") == 1
    assert text.count("$h = 66 \\times c$") == 1


def test_a_symbol_split_by_two_subscripts_keeps_its_word() -> None:
    assert tidy_symbol("v_A_mag") == "v_{A,mag}"


def test_a_placeholder_for_a_value_found_later_is_no_card_value() -> None:
    answers = [
        read_record("answer: N_f | 343 | N"),
        read_record("answer: f_f | ? | N | found below"),
    ]
    lines = answer_lines([a for a in answers if isinstance(a, Answer)], PHYSICS)
    assert lines == "$343\\,\\mathrm{N}$"


def test_a_sentence_written_in_a_maths_field_reads_as_one() -> None:
    text = _laid_out(
        "required: a | acceleration\nformula: Rotation | \\tau = I\\alpha\n"
        "substitution: Substitute I = \\frac{1}{2}mR^2 and \\alpha = \\frac{a}{R}:\n"
        "substitution: Area = l w\nanswer: a | 2 | m/s^2"
    )
    assert "Substitute $I = \\frac{1}{2}mR^2$ and $\\alpha = \\frac{a}{R}$:" in text
    assert "$Area = l w$" in text


def test_a_greek_unknown_owns_its_lines_in_an_unlabelled_block() -> None:
    # The ask is keyed \theta: its line "theta = …" must be keyed alike, or the block in two
    # asks came out as one part holding both answers (review of #2602).
    block = (
        "given: m | 2 | kg | mass\nrequired: F | tension\nrequired: theta | angle\n"
        "formula: Tension | F = m g\nsubstitution: F = 2 \\times 9.8\nsubstitution: F = 19.6\n"
        "substitution: theta = \\tan^{-1}(0.75)\nsubstitution: theta = 36.87\n"
        "answer: F | 19.6 | N\nanswer: theta | 36.87 | °"
    )
    records = [read_record(line) for line in block.split("\n")]
    solution = fitted([record for record in records if record is not None])
    assert [[answer.symbol for answer in part.answers] for part in solution.parts] == [
        ["F"],
        ["theta"],
    ]


def test_one_word_ask_over_two_parts_reads_its_meaning() -> None:
    # One record "speed | average speed" over two untitled parts: each row says the meaning
    # in words, never "$speed$" in maths (review of #2602).
    text = _laid_out(
        "required: speed | average speed\n"
        "part: a |\nformula: Average speed | speed = \\frac{d}{t}\n"
        "substitution: speed = \\frac{100}{2}\nanswer: speed | 50 | km/h\n"
        "part: b |\nformula: Average speed | speed = \\frac{d}{t}\n"
        "substitution: speed = \\frac{300}{5}\nanswer: speed | 60 | km/h"
    )
    assert "$speed$" not in text
    assert "(a) average speed" in text and "(b) average speed" in text


def test_an_answer_of_only_a_placeholder_leaves_no_answer_heading() -> None:
    text = _laid_out(
        "required: f | friction\nformula: Friction | f = N_w\nanswer: f | ? | N | found below"
    )
    assert "**Answer**" not in text
    assert "?" not in text


def test_the_worked_contract_keeps_the_one_line_check() -> None:
    # The unverified answer's rule asks for a one-line **Check**; the contract's silent
    # working must not forbid it (review of #2602).
    assert WORKING_ONCE in WORKED_BLOCK_CONTRACT
    assert "**Check**" in WORKING_ONCE and "**Check**" in SELF_CHECK_PROMPT_RULE


def test_lettered_asks_wait_for_the_whole_block_while_it_streams() -> None:
    # Review of #2602: whether "a" and "b" are part letters or unknowns is known only once
    # the working that sets them is in, so Required waits and no drawn line changes.
    asks = "required: a | first number\nrequired: b | second number\n"
    records = [
        record
        for record in (read_record(line) for line in f"{asks}step: 2a + b = 7".split("\n"))
        if record is not None
    ]
    streamed = render_worked(assemble(records), PHYSICS, streaming=True)
    assert "first number" not in streamed
    whole = _laid_out(
        f"{asks}step: 2a + b = 7\nstep: a = 3 | solve\nanswer: a | 3 |\nanswer: b | 1 |"
    )
    assert "$a$ (first number)" in whole


def test_a_line_said_twice_in_an_unlabelled_block_shows_once() -> None:
    # Review of #2602: the unlabelled two-ask path (``worked_asks._by_symbol``) dedupes as
    # a lettered part does.
    block = (
        "required: F | tension\nrequired: theta | angle\n"
        "formula: Tension | F = m g\nsubstitution: F = 2 \\times 9.8\nsubstitution: F = 19.6\n"
        "substitution: F = 19.6\nformula: Angle | \\tan theta = 0.75\n"
        "substitution: theta = 36.87\nanswer: F | 19.6 | N\nanswer: theta | 36.87 | °"
    )
    records = [record for record in (read_record(line) for line in block.split("\n")) if record]
    text = render_worked(fitted(records), PHYSICS)
    assert text.count("$F = 19.6") == 1

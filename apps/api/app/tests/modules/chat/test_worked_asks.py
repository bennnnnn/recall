"""A worked reply laid out as the question asks it: its own parts, maths alone in maths, one
clean value per card, and no working said again under the cards.

The replies are Qwen 3.7 Flash's, captured on the hard geometry round's questions
(2026-11-21, ``worked_fixtures/hard_geometry_2026_11_21.json``), and blocks rebuilt from the
replies the phone received in that round, whose layout showed each defect.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from app.modules.chat.finalize_passes import FinalizeState
from app.modules.chat.finalize_subjects import check_working
from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.worked_answers import WorkedLayout
from app.modules.chat.worked_lead import drop_recap_tail
from app.modules.chat.worked_render import _given_row, _line
from app.modules.chat.worked_solution import Given, Step, read_record
from app.modules.chat.worked_stream import ReplyFilter
from app.modules.chat.worked_turn import with_worked_contract, without_worked_contract
from app.services.question_parts import labelled_part_texts
from app.tests.behavior.latex_check import latex_problems

_FIXTURES = json.loads(
    (Path(__file__).parent / "worked_fixtures" / "hard_geometry_2026_11_21.json").read_text()
)


def _layout(question: str) -> WorkedLayout:
    return WorkedLayout(question_parts=labelled_part_texts(question)[1])


def _saved(question: str, reply: str) -> str:
    """``reply`` as the model wrote it, streamed through the layout and saved through the
    working check that lands its cards."""
    layout = _layout(question)
    if not reply.lstrip().startswith("```"):
        reply = f"```worked\n{reply}\n```"
    accum = StreamAccum()
    reply_filter = ReplyFilter(accum, layout)
    for start in range(0, len(reply), 5):
        accum.shown.append(reply_filter.feed(reply[start : start + 5]))
    accum.shown.append(reply_filter.flush())
    state = SimpleNamespace(
        text="".join(accum.shown),
        server_text=False,
        was_cancelled=False,
        ctx=SimpleNamespace(
            verified_subject=None,
            solver_unverified=None,
            user_message_content=question,
            worked=layout,
        ),
    )
    return check_working(cast(FinalizeState, state))


def _headings(text: str) -> list[str]:
    return re.findall(r"^\*\*\(([a-h])\) [^*]+\*\*$", text, re.M)


def _cards(text: str) -> list[str]:
    return re.findall(r"```answer\nverified: false\n(.*?)\n```", text, re.S)


def _part(text: str, letter: str) -> str:
    """Part ``letter``'s section, from its heading to the next."""
    found = re.search(rf"^\*\*\({letter}\) .*?(?=^\*\*\([a-h]\) |\Z)", text, re.M | re.S)
    assert found is not None, letter
    return found.group()


@pytest.mark.parametrize("name", sorted(_FIXTURES))
def test_no_captured_reply_shows_latex_source_or_a_field_bar(name: str) -> None:
    fixture = _FIXTURES[name]
    text = _saved(fixture["question"], fixture["reply"])
    assert latex_problems(text) == [], name
    assert not re.search(r"\$[^$\n]*\s\|\s[^$\n]*\$", text), name


@pytest.mark.parametrize(
    "name",
    [
        "q01_no_parts_formulas_first",
        "q01_parts_note",
        "q08_unlabelled_out_of_order",
        "q23_formulas_before_parts",
        "q13_two_values_one_part",
        "q16_lettered_requireds",
        "q17_frustum",
    ],
)
def test_the_layout_has_the_questions_own_parts_each_with_its_card(name: str) -> None:
    fixture = _FIXTURES[name]
    asked = labelled_part_texts(fixture["question"])[1]
    text = _saved(fixture["question"], fixture["reply"])
    letters = list("abcdefgh"[: len(asked)])
    assert _headings(text) == letters
    assert re.findall(r"\*\*Answer \(([a-h])\)\*\*", text) == letters
    assert len(_cards(text)) == len(asked)


def test_both_legs_are_one_part_with_both_values_in_one_formula() -> None:
    """Asked "a) the altitude b) both legs c) the area", the model wrote every formula, then
    every substitution, then every answer, with no part record: a leg was a part of its own
    (a) to (d), or all four values shared one card."""
    fixture = _FIXTURES["q01_no_parts_formulas_first"]
    text = _saved(fixture["question"], fixture["reply"])
    legs = _part(text, "b")
    assert "a = \\sqrt{c \\times q}" in legs and "b = \\sqrt{c \\times p}" in legs
    assert legs.count("formula**") == 2  # each leg's formula under its own heading
    assert _cards(text) == [
        r"h = 12\,\mathrm{cm}",
        r"a = 20\,\mathrm{cm},\quad b = 15\,\mathrm{cm}",
        r"A_{tri} = 150\,\mathrm{cm}^{2}",
    ]
    assert "(b) $a, b$ (lengths of both legs)" in text


def test_each_line_goes_under_the_part_that_finds_its_symbol() -> None:
    """With no part record the block came apart at each formula: the exterior angle, worked
    first, went under "(a) Number of sides" and every part's content moved up one."""
    fixture = _FIXTURES["q08_unlabelled_out_of_order"]
    text = _saved(fixture["question"], fixture["reply"])
    assert "n = \\frac{360" in _part(text, "a")
    assert "S = 12 \\times 150" in _part(text, "b")
    assert "E = 180^\\circ - 150" in _part(text, "c")
    assert _cards(text) == ["n = 12", "S = 1800^\\circ", "E = 30^\\circ"]
    assert "Sum of interior angles." not in text  # the note under the card


def test_formulas_written_before_the_parts_go_to_their_parts() -> None:
    fixture = _FIXTURES["q23_formulas_before_parts"]
    text = _saved(fixture["question"], fixture["reply"])
    assert "Angle bisector length formula" in _part(text, "b")
    assert "Heron's formula" in _part(text, "c")
    assert "Heron" not in _part(text, "a")
    assert _cards(text)[0] == r"BD = 6.50\,\mathrm{cm},\quad DC = 7.50\,\mathrm{cm}"


_SEMI_PERIMETER_FIRST = """given: a | 25 | cm | side a
given: b | 39 | cm | side b
given: c | 56 | cm | side c
required: A | area of the triangle
required: r | inradius
required: R | circumradius
formula: Semi-perimeter | s = \\frac{a + b + c}{2}
substitution: s = \\frac{25 + 39 + 56}{2}
substitution: s = 60\\,\\mathrm{cm}
formula: Heron's formula | A = \\sqrt{s(s-a)(s-b)(s-c)}
substitution: A = \\sqrt{60(60-25)(60-39)(60-56)}
substitution: A = 420\\,\\mathrm{cm^2}
answer: A | 420 | cm^2
formula: Inradius | r = \\frac{A}{s}
substitution: r = \\frac{420}{60}
substitution: r = 7\\,\\mathrm{cm}
formula: Circumradius | R = \\frac{abc}{4A}
substitution: R = \\frac{25 \\times 39 \\times 56}{4 \\times 420}
substitution: R = 32.5\\,\\mathrm{cm}
answer: r | 7 | cm
answer: R | 32.5 | cm"""


def test_a_working_step_goes_with_the_ask_it_leads_to() -> None:
    """Q27 live: "(a) Area" held only the semi-perimeter, "(b) Inradius" held Heron's area and
    its card, "(c) Circumradius" held r and R."""
    question = (
        "A triangle has side lengths 25 cm, 39 cm, and 56 cm.\n\nFind its area using Heron's "
        "formula, then calculate its inradius and circumradius."
    )
    text = _saved(question, _SEMI_PERIMETER_FIRST)
    area, inradius, circumradius = _part(text, "a"), _part(text, "b"), _part(text, "c")
    assert "Area of the triangle" in area and "s = \\frac{25" in area and "A = 420" in area
    assert "r = \\frac{420}{60}" in inradius and "R = " not in inradius
    assert "R = \\frac{25" in circumradius
    assert _cards(text) == [
        r"A = 420\,\mathrm{cm}^{2}",
        r"r = 7\,\mathrm{cm}",
        r"R = 32.50\,\mathrm{cm}",
    ]


_INVENTED_PARTS = """given: A | 84 | cm^2 | area
given: P | 56 | cm | perimeter
required: a, b, c | leg a
required: c, a, b | hypotenuse c
part: a | Leg a
formula: Area of a right triangle | A = \\frac{1}{2}ab
substitution: ab = 168
say: The two legs multiply to 168, and their sum with the hypotenuse is 56.
part: b | Hypotenuse c
substitution: (56 - c)^2 = c^2 + 336
substitution: c = 25
substitution: a + b = 31
answer: c | 25 | cm | hypotenuse
answer: a | 7 | cm | shorter leg
answer: b | 24 | cm | longer leg"""


@pytest.mark.parametrize("block", [_INVENTED_PARTS, _FIXTURES["q14_one_ask"]["reply"]])
def test_a_question_asking_one_thing_is_laid_out_whole(block: str) -> None:
    """ "Find the lengths of all three sides" asks one thing: Q14 live got "(a) Leg a" with
    no answer and "(b) Hypotenuse c" holding every value."""
    text = _saved(_FIXTURES["q14_one_ask"]["question"], block)
    assert _headings(text) == [] and "**Answer**" in text
    (card,) = _cards(text)
    assert all(value in card for value in ("= 7", "= 24", "= 25"))


@pytest.mark.parametrize(
    ("tex", "line"),
    [
        # Q29: a label before the maths.
        (
            "Group terms: (x^2 - 8x) + (y^2 + 6y) = 11",
            "$(x^2 - 8x) + (y^2 + 6y) = 11$ — group terms",
        ),
        ("Standard form: x + y - 9 = 0", "$x + y - 9 = 0$ — standard form"),
        ("Tangent slope m_t = -1/m_r = -1", "$m_t = -1/m_r = -1$ — tangent slope"),
        # Q16, Q22: a clause after it.
        ("s = \\frac{P}{n} where n=6", "$s = \\frac{P}{n}$ — where n=6"),
        ("L = 2h, where $h = \\sqrt{R^2 - x^2}$", "$L = 2h$ — where $h = \\sqrt{R^2 - x^2}$"),
        # Q18: words in brackets at its end.
        (
            "13 + c > 8 \\implies c > -5 (always true for positive length)",
            "$13 + c > 8 \\implies c > -5$ — always true for positive length",
        ),
        # Q22: maths marked inside the field is a sentence.
        (
            "From $R^2 - x^2 = r^2 - (14 - x)^2$: $225 - x^2 = 169 - (196 - 28x + x^2)$",
            "From $R^2 - x^2 = r^2 - (14 - x)^2$: $225 - x^2 = 169 - (196 - 28x + x^2)$",
        ),
        ("x^2 - 8x = 11 -> (x - 4)^2 = 36", "$x^2 - 8x = 11 \\Rightarrow (x - 4)^2 = 36$"),
        ("v = 3.33\\,\\mathrm{m/s}", "$v = 3.33\\,\\mathrm{m/s}$"),
    ],
)
def test_words_in_a_maths_field_are_said_beside_the_maths(tex: str, line: str) -> None:
    assert _line(tex) == line


@pytest.mark.parametrize(
    ("record", "tex"),
    [
        # Q24: the symbol first and the equation as the move.
        ("step: w | 80 = 2l + 2w \\implies l + w = 40", "80 = 2l + 2w \\implies l + w = 40"),
        # Q29: the symbol it finds, and the unit, as fields of their own.
        ("substitution: r | \\sqrt{36} = 6", "r = \\sqrt{36} = 6"),
        ("substitution: C | h=4, k=-3 -> (4, -3)", "h=4, k=-3 -> (4, -3)"),
        ("substitution: l = 20 | cm", "l = 20\\,\\mathrm{cm}"),
        ("substitution: |x - 3| = 5", "|x - 3| = 5"),
    ],
)
def test_a_line_written_in_fields_is_one_line_of_maths(record: str, tex: str) -> None:
    read = read_record(record)
    assert isinstance(read, Step) and read.tex == tex and not read.move


def test_a_part_label_before_a_symbol_is_no_part_of_it() -> None:
    """Q16 live: "Required (a) $a) s$ (side length)"."""
    assert read_record("required: a) s | side length") == read_record("required: s | side length")


@pytest.mark.parametrize(
    ("record", "row"),
    [
        # Q29: an equation given is its own line, never "eq = …" and "eq = 0".
        (
            "given: eq | x^2+y^2-8x+6y-11=0 | | circle equation",
            "$x^2+y^2-8x+6y-11=0$ (circle equation)",
        ),
        # Q8: "interior angle = 150°^\\circ".
        ("given: A | 150° | ° | interior angle", "$A = 150°$"),
        # Q4: "25\\,\\mathrm{(unitless)}".
        ("given: A_s | 25 | (unitless) | area part", "$A_s = 25$"),
    ],
)
def test_a_given_row_holds_its_value_and_its_unit_once(record: str, row: str) -> None:
    given = read_record(record)
    assert isinstance(given, Given) and _given_row(given) == row


def test_a_worked_out_given_is_a_line_of_the_working_and_subscripts_are_one() -> None:
    """Q17 live: Given listed "${{V_{small}}_{cone}}_{volume} = \\frac{1}{3}\\pi(4)^2(8)$"."""
    question = _FIXTURES["q17_frustum"]["question"]
    block = (
        "given: H | 24 | cm | height of the original cone\n"
        "given: V_small_cone_volume | \\frac{1}{3}\\pi(4)^2(8) | cm^3 | small cone\n"
        "required: r | radius of the smaller cone\nrequired: r_{frustum}_{top} | upper radius\n"
        "required: V | volume of the frustum\n"
        "part: a | radius of the smaller cone\nsubstitution: r = 12 \\times \\frac{8}{24}\n"
        "answer: r | 4 | cm\npart: b | upper radius\nsubstitution: r_{frustum}_{top} = 4\n"
        "answer: r_{frustum}_{top} | 4 | cm\npart: c | volume of the frustum\n"
        "substitution: V = 1152\\pi - \\frac{128}{3}\\pi\nanswer: V | \\frac{3328}{3}\\pi | cm^3"
    )
    text = _saved(question, block)
    given = text.split("**Required**")[0]
    assert "\\pi(4)^2(8)" not in given and "\\pi(4)^2(8)" in text.split("**Solution**")[1]
    assert "r_{frustum,top}" in text and "}_{" not in text


@pytest.mark.parametrize(
    ("asked", "record", "card"),
    [
        ("E | each exterior angle", "E | 30 | ° | each exterior angle", "E = 30^\\circ"),
        ("BD | length of BD", "BD | 6.5 | cm | length", "BD = 6.50\\,\\mathrm{cm}"),
        (
            "AD | length of the bisector",
            "AD | \\sqrt{146.25} | cm | exact value",
            "AD = \\sqrt{146.25}\\,\\mathrm{cm}",
        ),
        ("n | how many values c can have", "n | 15 | | possible values", "n = 15"),
        # An equation is the card whole, never under another symbol.
        ("C | the circle's equation", "C | (x-5)^2 + y^2 = 4 | | equation", "(x-5)^2 + y^2 = 4"),
        ("y | the tangent", "y | 3x + 4y = 25 | |", "3x + 4y = 25"),
        # Physics, 2026-11-21: a decimal beside an exact value is maths, a percent the value
        # again, a sum ending on it the working, and a unit's label words no unit.
        (
            "t | period",
            "t | \\frac{\\pi}{10} | s | approximately 0.314 s",
            "t = \\frac{\\pi}{10}\\,\\mathrm{s} \\approx 0.314\\,\\mathrm{s}",
        ),
        ("e | efficiency", "e | 0.40 | dimensionless | 40% efficiency", "e = 0.40"),
        ("PD | length of PD", "PD | 7 | units | 2+5 = 7", "PD = 7\\,\\mathrm{units}"),
        ("l | slant height", "l | 10 | cm slant height", "l = 10\\,\\mathrm{cm}"),
        ("C | capacitance", "C | 1.77e-10 | F", "C = 1.77 \\times 10^{-10}\\,\\mathrm{F}"),
        ("I | moment of inertia", "I | 0.18 | kg\\cdot m^2", "I = 0.18\\,\\mathrm{kg·m²}"),
        # Words that say something of the value stay: a direction, a kind, an option.
        ("d | displacement", "d | 12 | m | east", "$d = 12\\,\\mathrm{m}$ (east)"),
        (
            "F | force between them",
            "F | 3.37 | N | attractive",
            "$F = 3.37\\,\\mathrm{N}$ (attractive)",
        ),
    ],
)
def test_a_card_holds_its_value_never_a_caption(asked: str, record: str, card: str) -> None:
    text = _saved("A question.", f"required: {asked}\nanswer: {record}")
    (shown,) = _cards(text)
    assert shown == card
    assert not text.split("```")[-1].strip()  # nothing under the card


def test_a_ratio_noted_as_a_pair_stays_on_the_card() -> None:
    """Q4: "answer: S | 5/7 | | 5:7" fell above the card as a line of working."""
    fixture = _FIXTURES["q04_ratio_answer"]
    (card,) = _cards(_saved(fixture["question"], fixture["reply"]))
    assert card == r"S_{ratio} = 5/7,\quad P_l = 56\,\mathrm{cm}"


_RECAP_TAIL = "\n\n**a) Height:** $3$ cm  \n\n**b) Area:** $48$ cm²  \n\n**c) Perimeter:** $42$ cm"
_DERIVED_AGAIN = (
    "\n\nUsing the formula for the interior angle, $\\frac{(n-2) \\times 180°}{n} = 150°$:\n"
    "$180n - 360 = 150n$\n$30n = 360$\n$n = 12$\n\nThe sum is:\n$(12-2) \\times 180° = 1800°$"
)
_HEAD = (
    "**Required**  \n$n$ (number of sides)\n\n**Substitution**  \n$n = \\frac{360}{180 - 150}$  "
    "\n$S = (12 - 2) \\times 180 = 1800$  \n$h = 3$, $A = 48$, $P = 42$, $30$\n\n**Answer**\n\n"
    "```answer\nverified: false\nn = 12\n```"
)


@pytest.mark.parametrize(
    ("tail", "kept"),
    [
        (_RECAP_TAIL, ""),
        (_DERIVED_AGAIN, ""),
        # A closing one-line summary stays, and so does a picture.
        (
            _DERIVED_AGAIN + "\n\nSo the polygon is a dodecagon with 12 sides.",
            "\n\nSo the polygon is a dodecagon with 12 sides.",
        ),
        ("\n\n```geometry\n{}\n```" + _RECAP_TAIL, "\n\n```geometry\n{}\n```"),
        # A number of its own is something new.
        ("\n\nThe possible values are $6, 7, 8, \\dots, 20$.\n\nSee: $n = 15$.", None),
    ],
)
def test_the_working_said_again_after_the_cards_goes(tail: str, kept: str | None) -> None:
    text = _HEAD + tail
    question = "A regular polygon has each interior angle equal to 150°. Find n."
    assert drop_recap_tail(text, question) == (text if kept is None else _HEAD + kept)


def test_a_proof_asked_for_is_kept_after_the_cards() -> None:
    text = _HEAD + _DERIVED_AGAIN
    assert drop_recap_tail(text, "Find n. Prove that your answer is right.") == text


def test_a_question_in_lettered_parts_names_them_beside_the_contract() -> None:
    question = _FIXTURES["q01_parts_note"]["question"]
    prompt = [{"role": "user", "content": question}]
    with_note = with_worked_contract(prompt, _layout(question))
    note = with_note[-2]["content"]
    assert note.startswith("This question is in lettered parts: (a) The altitude; (b) The")
    assert "exactly 3 `part` records" in note
    assert without_worked_contract(with_note) == prompt
    assert len(with_worked_contract(prompt, WorkedLayout())) == 2


_RESULTS_FIRST = (
    "To solve for the trapezoid with parallel sides **20 cm** and **12 cm** and legs of "
    "**5 cm**:\n\na) The height is **3 cm**.\nb) The area is **48 cm²**.\n"
    "c) The perimeter is **42 cm**.\n\n"
)
_PARTS_BELOW = (
    "**Given**  \n$a = 20\\,\\mathrm{cm}$  \n$b = 12\\,\\mathrm{cm}$  \n$c = 5\\,\\mathrm{cm}$\n\n"
    "**Solution**\n\n**Answer (a)**\n\n```answer\nverified: false\nh = 3\\,\\mathrm{cm}\n```\n\n"
    "**Answer (b)**\n\n```answer\nverified: false\nA = 48\\,\\mathrm{cm}^{2}\n```\n\n"
    "**Answer (c)**\n\n```answer\nverified: false\nP = 42\\,\\mathrm{cm}\n```"
)


def test_a_worked_turn_never_opens_with_its_results() -> None:
    """Q6, the parts note's round: the parts' values listed above the block, then the block."""
    from app.modules.chat.worked_lead import drop_guessed_lead

    assert drop_guessed_lead(_RESULTS_FIRST + _PARTS_BELOW, laid_out=True) == _PARTS_BELOW
    assert drop_guessed_lead(_RESULTS_FIRST + _PARTS_BELOW) == _RESULTS_FIRST + _PARTS_BELOW


@pytest.mark.parametrize(
    ("tex", "tidy"),
    [
        ("A = pi*(6)^2", "A = \\pi (6)^2"),
        ("36*pi", "36 \\pi"),
        ("2*3", "2 \\times 3"),
        ("x^*", "x^*"),
        ("R_{cyl} = r, \\ h_{cyl} = 2r", "R_{cyl} = r, h_{cyl} = 2r"),
    ],
)
def test_maths_typed_as_text_is_written_as_maths(tex: str, tidy: str) -> None:
    from app.modules.chat.worked_text import tidy_tex

    assert tidy_tex(tex) == tidy

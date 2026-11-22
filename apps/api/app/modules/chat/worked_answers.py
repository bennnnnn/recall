"""A worked solution's answers as its cards show them, and how the layout is set.

Each answer record is one value on its card's line (``answer_lines``): rounded once
(``worked_figures.card_answer``), its unit after it, its symbol before it unless physics'
card holds the value alone, a direction kept beside it; a conclusion in words set upright,
and a sentence answer in a card of its own whose words wrap. Split from ``worked_render``,
which lays the rest of the solution out.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.chat.worked_figures import card_answer
from app.modules.chat.worked_lines import split_line
from app.modules.chat.worked_prose import prose_maths
from app.modules.chat.worked_solution import Answer
from app.modules.chat.worked_text import is_prose, names_nothing, tidy_symbol, tidy_tex
from app.modules.chat.worked_units import quantity_tex, unit_tex
from app.modules.chat.worked_values import a_sum, one_value_each, writes_its_unit
from app.modules.turn_reading.routing import is_short_reply
from app.services.answer_fence import UNCHECKED_ANSWER_MARKER
from app.services.final_value import UNIT_VECTOR
from app.services.workout import Workout, math_line, render_workout

_HARD_BREAK = "  \n"
_COMMAND = re.compile(r"\\[A-Za-z]+")
_LETTER = re.compile(r"[A-Za-z]")


@dataclass(frozen=True)
class WorkedLayout:
    """How one turn's worked block is laid out. ``law_heading``: physics' card holds the
    value alone, as its verified replies do."""

    law_heading: bool = False
    # The precision the question asks its answer to (significant figures, decimal places,
    # as ``school_rounding.asked_rounding`` reads them): the card keeps to it.
    asked: tuple[int, int] = (0, -1)
    # The question's own lettered parts, each one's words ("The altitude.", "The lengths of
    # both legs."), as ``services.question_parts`` reads them: the layout's parts are these
    # (``worked_asks``), none when the question has no labels.
    question_parts: tuple[str, ...] = ()


_UPRIGHT_GROUP = re.compile(r"\\(?:mathrm|text)\s*\{[^{}]*\}")


# A direction by its angle: "39.8° north of west".
_ANGLE = re.compile(r"\d+(?:\.\d+)?[ \t]*°")


# A power of ten in a calculator's spelling: "1.5e-3", "6.022E23".
_E_NOTATION = re.compile(r"(?<=\d)[eE](?=[-+]?\d)")


# Euler's number raised to a power: "20e^{-0.5}" is a number; the exponent's own letters
# ("e^{-t/RC}") still make a value symbolic.
_EULER = re.compile(r"(?<![A-Za-z\\])e(?=\s*\^)")


def in_symbols(tex: str) -> bool:
    """A value written in letters ("C V_0", "\\frac{1}{2}MR^2"): its units are its
    symbols', so none is written after it. A command (\\pi, \\times), a unit set upright,
    a calculator's power of ten, Euler's e or a unit vector is no symbol: "\\pi/3",
    "2400\\,\\mathrm{s}", "1.5e-3", "20e^{-0.5}" and "-16\\hat{i} + 20\\hat{j}" are numbers."""
    plain = UNIT_VECTOR.sub(" ", _UPRIGHT_GROUP.sub("", tex))
    plain = _E_NOTATION.sub(" ", _COMMAND.sub("", plain))
    plain = _EULER.sub(" ", plain)
    return _LETTER.search(plain) is not None


def in_words(value: str) -> bool:
    """A value written in words alone ("at rest", "mass of the rod"). One with a digit is a
    quantity, its unit written beside it ("20 km", "45 min"), and keeps its row."""
    return is_prose(value) and not any(char.isdigit() for char in value)


def concludes(answer: Answer) -> bool:
    """An answer that is a conclusion in words: several words ("all the ice melts", as
    ``names_nothing`` reads them) or a reply on its own ("yes", "no", as the turn reader
    reads one). A single run of letters is symbols ("F | mg | N", "x | ab |"), kept in
    maths (Claude and Gemini on #2489)."""
    value = answer.value.strip()
    return in_words(value) and (names_nothing(value) or is_short_reply(value))


_TEXT_SPECIALS = str.maketrans(
    {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
)


_MATH_SPAN = re.compile(r"\$([^$]+)\$")


def words_tex(words: str) -> str:
    """A conclusion in words as card maths: its words upright in ``\\text{}``, TeX's specials
    escaped ("yes & no" broke the group), and a ``$…$`` it holds drawn as maths."""
    pieces: list[str] = []
    at = 0
    for span in _MATH_SPAN.finditer(words):
        if words[at : span.start()]:
            pieces.append(rf"\text{{{words[at : span.start()].translate(_TEXT_SPECIALS)}}}")
        pieces.append(span.group(1))
        at = span.end()
    if words[at:]:
        pieces.append(rf"\text{{{words[at:].translate(_TEXT_SPECIALS)}}}")
    return "".join(pieces)


# A note giving the value as a decimal: "approximately 0.314 s", "≈ 0.314", "about 5".
_ABOUT = re.compile(
    r"(?:approx(?:imately|\.)?|about|roughly|around|≈|~|\\approx)\s*"
    r"(?P<number>-?\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-zµΩ°/^²³0-9·]*)",
    re.IGNORECASE,
)
# A relation at the top of a value, outside any group: it is an equation, not a value.
_EQUATION = re.compile(r"^[^{}]*?(?<![<>!\\])=")


def _answer_line(answer: Answer, layout: WorkedLayout) -> str:
    """The value with its unit in maths, and a note after it in brackets: a short label
    ("east") stays on the card, and a remark ("about 1.20√(gh); option A gives …") goes
    in a sentence under it (``services.remark_after_answer``), its maths drawn as maths."""
    if concludes(answer):
        # A conclusion ("yes", "all the ice melts") is words, set upright: in maths its
        # letters were italic variables, under an invented symbol (phys30, 2026-11-16).
        note = prose_maths(answer.note)
        said = math_line(words_tex(answer.value.strip()))
        return f"{said} ({note})" if note else said
    if _restates(answer.note, answer.value):
        answer = answer.model_copy(update={"note": ""})
    # "approximately 0.314 s" after an exact π/10 s: the decimal in the card's maths, "≈".
    about = _ABOUT.fullmatch(answer.note.strip())
    if about is not None:
        answer = answer.model_copy(update={"note": ""})
    label, maths, after = split_line(answer.value)
    if label and maths and not after:
        # "Equation: (x - 5)^2 + …": the label is what Required names; the card holds the value.
        answer = answer.model_copy(update={"value": maths})
    answer = card_answer(answer, layout.asked)  # rounds once, by the one rule or as asked
    tex = tidy_tex(answer.value)
    unit = "" if in_symbols(tex) or writes_its_unit(tex, answer.unit) else answer.unit
    # A vector's components share its unit: (-16\hat{i} + 20\hat{j}) m/s.
    value = quantity_tex(f"({tex})" if unit and a_sum(tex) else tex, unit)
    # A symbol that only repeats the unit ("cm | 10000 | cm") or is a word names nothing.
    named = answer.symbol and answer.symbol != answer.unit and not names_nothing(answer.symbol)
    symbol = tidy_symbol(answer.symbol) if named else ""
    # A value that is an equation ("3x + 4y = 25", "x = -4") is the card whole: "y = 3x + 4y
    # = 25" and "D = x = -4" set its symbol before another (2026-11-21).
    equation = _EQUATION.search(tex) is not None
    shown = value if layout.law_heading or not symbol or equation else f"{symbol} = {value}"
    if about is not None:
        shown = f"{shown} \\approx {about['number']}{unit_tex(about['unit'] or answer.unit)}"
    note = prose_maths(answer.note)
    if _ANGLE.match(note):
        # A direction by its angle stays on the card after a comma, as a card writes one
        # ("12.50 m/s, 39.8° north of west"): in brackets, past three words, it went
        # under the card as a sentence of its own (the owner's chat, 2026-11-20).
        return f"{math_line(shown)}, {note}"
    return f"{math_line(shown)} ({note})" if note else math_line(shown)


def answer_lines(answers: Sequence[Answer], layout: WorkedLayout) -> str:
    """The answers' lines, values on one line each and a sentence answer as its own card."""
    answers = [one for answer in answers for one in one_value_each(answer)]
    sentences = [sentence_answer(answer) for answer in answers]
    values = _HARD_BREAK.join(
        _answer_line(answer, layout)
        for answer, sentence in zip(answers, sentences, strict=True)
        if sentence is None
    )
    cards = [_sentence_card(sentence) for sentence in sentences if sentence is not None]
    return "\n\n".join(block for block in (values, *cards) if block)


def _sentence_card(sentence: str) -> str:
    """A sentence answer in its own card, words that wrap: no solver checked it."""
    answer = f"{UNCHECKED_ANSWER_MARKER}\n{sentence}"
    return render_workout(Workout(), answer, answer_heading=None, solution=False).strip()


# A number in a sentence with no maths of its own: "60 W" is "$60$ W".
_BARE_NUMBER = re.compile(r"(?<![\w.$])(\d+(?:\.\d+)?)(?![\w.$])")


_DOLLAR_SPAN = re.compile(r"\$[^$]+\$")


_PROSE_WORD = re.compile(r"[A-Za-z\u00C0-\u024F\u0400-\u04FF\u1200-\u137F]{3,}")


def sentence_answer(answer: Answer) -> str | None:
    """The answer as a sentence, its maths as maths, when it is one: two words or more
    beside a number ("The lamp uses $60$ W when it runs on $220$ V"). Its card draws it as
    words that wrap, never as one formula off the card's edge."""
    if concludes(answer):
        return None
    said = prose_maths(answer.value.strip())
    words = _PROSE_WORD.findall(_DOLLAR_SPAN.sub(" ", said))
    if len(words) < 2 or not any(char.isdigit() for char in said):
        return None
    if "$" not in said:
        said = _BARE_NUMBER.sub(r"$\1$", said)
    return said


_FRACTION = re.compile(r"\\[dt]?frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
_QUOTIENT = re.compile(r"(-?\d+(?:\.\d+)?)[:/](\d+(?:\.\d+)?)")


def _restates(note: str, value: str) -> bool:
    """A note that only writes the value again ("1.03 \\times 10^5" after 103000): the card
    says it, and the bracket fell under the card as an orphan number (G8 t28)."""
    from app.services.formal.solve import parse_number

    def number(text: str) -> float | None:
        plain = re.sub(r"\\times|\\cdot", "*", _FRACTION.sub(r"\1/\2", text))
        plain = re.sub(r"[$\s{}]|\\[,; !]", "", plain)
        # A ratio is its quotient: "5:7" says the card's 5/7 again (2026-11-21).
        quotient = _QUOTIENT.fullmatch(plain)
        if quotient is not None and float(quotient.group(2)):
            return float(quotient.group(1)) / float(quotient.group(2))
        return parse_number(plain)

    # "2+5 = 7" is a sum that ends on the value; "40%" is 0.40 in hundredths.
    note = note.rsplit("=", 1)[-1]
    percent = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%(?:\s+[A-Za-z ]+)?\s*", note)
    if percent is not None:
        note = str(float(percent.group(1)) / 100)
    said, shown = number(note), number(value)
    return said is not None and shown is not None and abs(said - shown) <= 0.01 * abs(shown)

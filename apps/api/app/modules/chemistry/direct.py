# ruff: noqa: RUF001, RUF002, RUF003 -- a solver row is read as written: ×, −.
"""Exact scan-friendly replies for complete verified chemistry calculations."""

from __future__ import annotations

import re
from collections.abc import Callable

from app.modules.chemistry.block import VerifiedChemistry
from app.modules.chemistry.extractors.atom_particles import asks_more_particles
from app.modules.chemistry.fence import assemble_chemistry_reply
from app.modules.chemistry.glossary import given_meaning
from app.modules.chemistry.notation import typeset
from app.modules.chemistry.questions import asks_more_questions
from app.modules.chemistry.solvers.types import ChemistryResult
from app.modules.chemistry.tex import chemistry_tex, law_symbols, symbol_tex
from app.services.question_parts import asks_more_parts
from app.services.student_claim import has_stated_result
from app.services.workout import (
    Workout,
    formula_heading,
    math_line,
    method_heading,
    render_workout,
    text_line,
    where_line,
)

# A value alone: "2.0 mol", "5.6 × 10^-10", "-393.5 kJ/mol" (no operation left to do).
_VALUE = re.compile(r"[-−+]?\d[\d.]*(?: × 10\^-?\d+)?(?: [^\d×/+−()^√=]+)?")


class _Rows:
    """A result's rows as maths, the way every subject's worked rows are (``tex``): a row
    that is not one formula stays text. ``symbols`` are the law's own, so ``Na`` in a bond
    order is a symbol, not sodium."""

    def __init__(self, result: ChemistryResult, show: Callable[[str], str]) -> None:
        self.result = result
        self.show = show
        self.symbols = law_symbols(result.formula)

    def tex(self, row: str) -> str | None:
        return None if self.result.verbatim else chemistry_tex(row, self.symbols)

    def line(self, row: str) -> str:
        tex = self.tex(row)
        return math_line(tex) if tex is not None else text_line(self.show(row))

    def given(self) -> tuple[str, ...]:
        """Each given on its line, then the ``where`` line naming the ones it can."""
        rows: list[str] = []
        named: list[tuple[str, str]] = []
        for item in self.result.given:
            tex = self.tex(item)
            rows.append(math_line(tex) if tex is not None else text_line(self.show(item)))
            meaning = given_meaning(item) if tex is not None else None
            symbol = symbol_tex(item.split(" = ", 1)[0], self.symbols) if meaning else None
            if meaning and symbol:
                named.append((symbol, meaning))
        naming = where_line(named)
        return (*rows, naming) if naming else tuple(rows)

    def required(self) -> str:
        """What is asked, ``$n$ (amount)`` as physics', when the solver names its symbol
        ("Amount, n") or asks for a symbol alone ("pH")."""
        find = self.result.find
        meaning, comma, symbol = find.rpartition(", ")
        tex = symbol_tex(symbol, self.symbols) if comma and not self.result.verbatim else None
        if tex is not None:
            return math_line(tex, _lower_first(meaning))
        alone = None if self.result.verbatim else symbol_tex(find, self.symbols)
        return math_line(alone) if alone is not None else text_line(self.show(find))

    def law(self) -> str:
        """A law's equation, or a procedure's rule written out; its name heads either."""
        result = self.result
        if result.method:
            return text_line(_lower_first(self.show(result.formula), upper=True))
        return self.line(result.formula)

    def substitution(self) -> tuple[str, ...]:
        """The values put in, worked to their value as physics' are: ``n = 36 g /
        18.015 g/mol`` then ``n = 1.998 mol``. Each row ends on its value unrounded
        (``_worked_rows``); the card rounds it to the data's figures (2.0 mol) and says it
        once."""
        rows = list(self.result.substitution)
        closing = _closing_row(rows, self.result.answer)
        if closing is not None and self.tex(closing) is not None:
            rows.append(closing)
        worked = _worked_rows(rows, self.result.unrounded, self.result.given)
        return tuple(self.line(row) for row in worked)


def _lower_first(text: str, *, upper: bool = False) -> str:
    """ "Amount" → "amount" (``upper``: "count each" → "Count each", a rule on its own line);
    an acronym keeps its capitals ("pH", "NMR")."""
    if len(text) > 1 and text[1].isupper():
        return text
    return (text[:1].upper() if upper else text[:1].lower()) + text[1:]


def _base(side: str) -> str:
    """A quantity's symbol without what it is of: ``n(H2O)`` → ``n``."""
    return re.sub(r"\([^()]*(?:\([^()]*\))?[^()]*\)", "", side).strip()


def _closing_row(rows: list[str], answer: str) -> str | None:
    """``n = 2.0 mol`` after ``n = 36 g / 18.015 g/mol``: the last row's symbol equal to the
    answer's value, when that row stops at an operation and the answer is that quantity's."""
    if not rows or "\n" in answer.strip() or answer.count(" = ") != 1:
        return None
    asked, value = (part.strip() for part in answer.split(" = "))
    last = rows[-1]
    if " = " not in last:
        return None
    symbol, worked = last.split(" = ", 1)
    final = worked.rsplit(" = ", 1)[-1].strip()
    if _VALUE.fullmatch(final) or _base(symbol) != _base(asked):
        return None
    return f"{symbol.strip()} = {value}"


# A number as a solver writes it: "1.0", "6.0221 × 10^23"; never a formula's subscript (the
# 2 of "H2O" is no rounded 2 g).
_NUMBER_TEXT = re.compile(r"(?<![\w.^])(?<!\^-)(?<!\^−)-?\d+(?:\.\d+)?(?: × 10\^-?\d+)?(?![\w.])")


def _worked_rows(
    rows: list[str], unrounded: tuple[tuple[str, str], ...], given: tuple[str, ...] = ()
) -> list[str]:
    """Each row ending on a value the solve rounded ends on it as worked (``m = 29.22 g``),
    the card alone rounding it: a limiting reagent's yield row sits above its excess row, and
    "4 g" of hydrogen's 35.74 g is no 4 × 10^1 g there. A row stays rounded when it works with
    a rounded value or with a difference of carried values, or a later row works with its
    own: "(1.0 mol)(6.0221 × 10^23)" ending on 6.017 × 10^23 did not add up. A number the
    question typed (``given``) is never a rounded one, though it reads alike: "2 A" beside a
    card of 2 g. A closing row (``Kp = 8 × 10^-4``) follows the row it closes."""
    typed = {number for row in given for number in _NUMBER_TEXT.findall(_typed_part(row))}
    rounded = {text for text, _ in unrounded} - typed
    ends = [_rounded_end(row, unrounded) for row in rows]
    heads = [
        _CONSTANT_ARGUMENT.sub(" ", row if end is None else row.rpartition(" = ")[0])
        for row, end in zip(rows, ends, strict=True)
    ]
    inputs = [set(_NUMBER_TEXT.findall(head)) for head in heads]
    rounded_with: list[bool] = []
    for index, row in enumerate(rows):
        closing = index > 0 and " = " in row and not _NUMBER_TEXT.search(row.split(" = ")[0])
        closing = closing and not inputs[index] - ({ends[index]} - {None})
        reached = {_last_number(earlier) for earlier in rows[:index]} - {None}
        # A row with no rounded end is read whole: "Ka = (0.007943)^2 / (0.010 − 0.007943)".
        difference = row.rpartition(" = ")[0] if ends[index] is not None else row
        own = bool(inputs[index] & rounded) or _subtracts_carried(difference, reached)
        rounded_with.append(rounded_with[index - 1] if closing and not own else own)
    shown: list[str] = []
    kept: set[str] = set()
    for index, (row, end) in enumerate(zip(rows, ends, strict=True)):
        later = end is not None and _used_later(row, end, typed, heads[index + 1 :])
        # A row restating a value an earlier row kept rounded ("where c = -0.00909 mol/L")
        # keeps it too: one value, one precision.
        restated = end is not None and end.lstrip("-−") in kept
        if end is None or later or rounded_with[index] or restated:
            shown.append(row)
            if end is not None:
                kept.add(end.lstrip("-−"))
        else:
            shown.append(_unrounded_value(row, end, unrounded))
    return shown


# A whole number a function takes is a constant, no rounded value: the 2 of "ln(2)".
_CONSTANT_ARGUMENT = re.compile(r"\b(?:ln|log(?:10)?)\s*\(\d+\)")


# A difference of two values: "(1.000 mol − 0.9921 mol)", "1/350 − 1/300", and in powers
# of ten "(9.995 × 10^-4 mol − 9.921 × 10^-4 mol)".
_OPERAND = r"\d+(?:\.\d+)?(?: × 10\^-?\d+)?"
_DIFFERENCE = re.compile(
    rf"(?P<left>{_OPERAND})\s*(?:[a-zA-Z/]+\s*)?[−-]\s*\(?(?P<right>{_OPERAND})"
)


def _subtracts_carried(text: str, reached: set[str | None]) -> bool:
    """Whether ``text`` (a row's working) takes a difference of values earlier rows reached.
    They are carried to four figures, so a difference of near ones loses what the unrounded
    result keeps:
    "(1.000 mol − 0.9921 mol) × 31.998 g/mol" makes 0.2528 g, not the 0.2560 g worked in
    full. Such a row ends on its rounded value, as the card does. A difference of typed
    values ("1/350 − 1/300") is exact and works as written."""
    return any({found["left"], found["right"]} & reached for found in _DIFFERENCE.finditer(text))


def _last_number(row: str) -> str | None:
    """The number a row ends on ("1.000" of "n = 0.5000 mol × 2 = 1.000 mol")."""
    _head, equals, value = row.rpartition(" = ")
    numbers = _NUMBER_TEXT.findall(value) if equals else []
    return numbers[0] if numbers else None


def _typed_part(given: str) -> str:
    """The part of a given row the question typed: a row that works a value out
    ("pKa1 = −log10(4.3 × 10^-7) = 6.37") reached its end, it did not type it."""
    return given.rpartition(" = ")[0] if given.count(" = ") > 1 else given


def _used_later(row: str, end: str, typed: set[str], later_heads: list[str]) -> bool:
    """Whether a later row works with this row's rounded value. With its unit, the value
    itself is matched ("4 °C" in "0 °C − 4 °C"), never a count that reads alike ("(2)" beside
    b = 2 mol/kg); a bare value is matched as a number no question typed."""
    value = row.rpartition(" = ")[2].strip()
    if " " in value:
        # As a whole value: "8 g" is not in "31.998 g/mol".
        whole = re.compile(rf"(?<![\w.]){re.escape(value)}(?![\w/·])")
        return any(whole.search(head) for head in later_heads)
    return end not in typed and any(end in _NUMBER_TEXT.findall(head) for head in later_heads)


def _rounded_end(row: str, unrounded: tuple[tuple[str, str], ...]) -> str | None:
    """The rounded number a row ends on ("2 × 10^1" of "m = … = 2 × 10^1 g"), or None."""
    _head, equals, value = row.rpartition(" = ")
    if not equals:
        return None
    value = value.strip()
    for text, _worked in sorted(unrounded, key=lambda pair: -len(pair[0])):
        if value == text or value.startswith(f"{text} "):
            return text
    return None


def _unrounded_value(row: str, end: str, unrounded: tuple[tuple[str, str], ...]) -> str:
    """``m = 29 g`` → ``m = 29.22 g``: a row ending on ``end``, a value the solve rounded,
    ends on it unrounded, as worked."""
    head, _equals, value = row.rpartition(" = ")
    return f"{head} = {dict(unrounded)[end]}{value.strip()[len(end) :]}"


def format_direct_chemistry_reply(verified: VerifiedChemistry) -> str:
    result = verified.result
    # A lookup that only draws (a named compound's structure) computes nothing: no
    # Given/Required/Substitution, one line and the drawing.
    if result.structure_smiles and not result.answer.strip():
        return assemble_chemistry_reply(f"{result.title}, from PubChem:", verified)
    # The solver text is ASCII (H2SO4, Fe2+, ->); the reader gets H₂SO₄, Fe²⁺, →, and every
    # row that is one formula as maths, laid out as physics' and maths' rows are. A result
    # that carries SMILES or atom labels is left exactly as the solver wrote it.
    show = (lambda text: text) if result.verbatim else typeset
    rows = _Rows(result, show)
    workout = Workout(
        given=rows.given(),
        find=(rows.required(),),
        formula=(rows.law(),),
        # A law's name heads its equation ("Molar mass formula"), and a procedure's name its
        # rule ("Conservation of atoms and charge"), never a bare **Formula** (2026-11-11).
        formula_heading=(
            method_heading(result.formula_name)
            if result.method
            else formula_heading(result.formula_name)
        ),
        # A procedure's rows check its rule (an atom tally, a range); they substitute nothing.
        steps=tuple(text_line(show(line)) for line in result.substitution) if result.method else (),
        substitution=() if result.method else rows.substitution(),
    )
    return assemble_chemistry_reply(render_workout(workout), verified)


def maybe_direct_chemistry_reply(
    verified: VerifiedChemistry | None,
    *,
    has_image_attachment: bool,
    user_text: str = "",
) -> str | None:
    """Use exact output for typed text, and for a photo whose reading was confirmed.

    Not when the student stated a result to check: the model answers whether it is
    right, with the verified answer beside it. Not for a question that asks more than the
    result answers either (more labelled parts, more questions): the model answers them all.
    """
    if verified is None or has_stated_result(user_text):
        return None
    answers = verified.result.answer
    if (
        asks_more_parts(user_text, answers)
        or asks_more_particles(user_text, answers)
        or asks_more_questions(user_text, answers)
    ):
        return None
    if has_image_attachment:
        from app.modules.chemistry.reading import confirmed_chemistry_reading

        if confirmed_chemistry_reading(user_text) is None:
            return None
    return format_direct_chemistry_reply(verified)

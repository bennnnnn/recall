# ruff: noqa: RUF001, RUF003 -- a solver row is read as written: ×, −.
"""Exact scan-friendly replies for complete verified chemistry calculations."""

from __future__ import annotations

import re
from collections.abc import Callable

from app.modules.chemistry.block import VerifiedChemistry
from app.modules.chemistry.extractors.atom_particles import asks_more_particles
from app.modules.chemistry.fence import assemble_chemistry_reply
from app.modules.chemistry.glossary import given_meaning
from app.modules.chemistry.notation import typeset
from app.modules.chemistry.solvers.types import ChemistryResult
from app.modules.chemistry.tex import chemistry_tex, law_symbols, symbol_tex
from app.services.question_parts import asks_more_parts
from app.services.student_claim import has_stated_result
from app.services.workout import (
    Workout,
    formula_heading,
    math_line,
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
        """A law's equation (its name heads it); a procedure's rule written out."""
        result = self.result
        if result.method:
            return text_line(f"{result.formula_name}: {self.show(result.formula)}")
        return self.line(result.formula)

    def substitution(self) -> tuple[str, ...]:
        """The values put in, worked to their value as physics' are: ``n = 36 g /
        18.015 g/mol`` then ``n = 1.998 mol``. The working's last value is unrounded; the card
        rounds it to the data's figures (2.0 mol) and says it once."""
        rows = list(self.result.substitution)
        closing = _closing_row(rows, self.result.answer)
        if closing is not None and self.tex(closing) is not None:
            rows.append(closing)
        if rows:
            rows[-1] = _unrounded_value(rows[-1], self.result.unrounded)
        return tuple(self.line(row) for row in rows)


def _lower_first(text: str) -> str:
    """ "Amount" → "amount"; an acronym keeps its capitals ("pH", "NMR")."""
    if len(text) > 1 and text[1].isupper():
        return text
    return text[:1].lower() + text[1:]


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


def _unrounded_value(row: str, unrounded: tuple[tuple[str, str], ...]) -> str:
    """``m = 29 g`` → ``m = 29.22 g``: a row ending on a value the solve rounded ends on it
    unrounded, as worked; a row whose value nothing rounded stays."""
    head, equals, value = row.rpartition(" = ")
    if not equals:
        return row
    value = value.strip()
    for text, worked in sorted(unrounded, key=lambda pair: -len(pair[0])):
        if value == text or value.startswith(f"{text} "):
            return f"{head} = {worked}{value[len(text) :]}"
    return row


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
        # A law's name heads its equation ("Molar mass formula"); a procedure's
        # rule names itself on its line, under **Formula**.
        formula_heading=formula_heading(None if result.method else result.formula_name),
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
    right, with the verified answer beside it. Not for a question in more labelled parts
    than the result answers either: the model answers them all.
    """
    if verified is None or has_stated_result(user_text):
        return None
    if asks_more_parts(user_text, verified.result.answer) or asks_more_particles(
        user_text, verified.result.answer
    ):
        return None
    if has_image_attachment:
        from app.modules.chemistry.reading import confirmed_chemistry_reading

        if confirmed_chemistry_reading(user_text) is None:
            return None
    return format_direct_chemistry_reply(verified)

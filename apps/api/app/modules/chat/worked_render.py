"""A worked solution the model wrote as parts, laid out as a verified reply is.

Every section goes through ``render_workout`` (``services/workout.py``), the renderer of
every verified maths, physics and chemistry reply: **Given** (each value on its line, then
the ``where`` line naming them), **Required**, **Solution**, the formula under the heading
the model gave it (``worked_text.formula_title``: **Conservation of energy**; none, and it
follows **Solution**), ``Solve for`` lines, **Substitution** or **Steps**, then **Answer**
with the value. A question in parts is laid out as a verified one in parts: one Given (each
value once; a part's letter only on the values of one symbol the parts give apart) and what
is asked once, then **Solution** and each part under its letter, closed by its own
**Answer (a)**, a hairline between parts.
The value under **Answer** becomes the card in finalize
(``chat.finalize_subjects.check_working``), marked ``verified: false``: no solver checked
it. The words the model wrote (a heading, a move, what a symbol is) keep their maths as
maths (``worked_prose.prose_maths``).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.chat.worked_prose import prose_maths
from app.modules.chat.worked_solution import Answer, Given, Part, Step, WorkedSolution
from app.modules.chat.worked_text import (
    formula_title,
    is_prose,
    names_nothing,
    tidy_symbol,
    tidy_tex,
)
from app.modules.chat.worked_units import quantity_tex
from app.services.worked_parts import WorkedPart, lettered_line, part_letter, render_parts
from app.services.workout import (
    ANSWER,
    Workout,
    math_line,
    render_workout,
    solve_for_line,
    text_line,
    where_line,
)

_HARD_BREAK = "  \n"
_UPRIGHT = re.compile(r"\\(?:mathrm|text)|\\[,;! ]")
_NOT_ALNUM = re.compile(r"[^A-Za-z0-9.]")
_SPACING = re.compile(r"[\s{}]")
# A letter outside a command: a value that holds one is written in symbols ("C V_0").
_COMMAND = re.compile(r"\\[A-Za-z]+")
_LETTER = re.compile(r"[A-Za-z]")


@dataclass(frozen=True)
class WorkedLayout:
    """How one turn's worked block is laid out. ``law_heading``: physics' card holds the
    value alone, as its verified replies do."""

    law_heading: bool = False


def _line(tex: str, note: str | None = None) -> str:
    """One state: maths, or the model's sentence as text; its move's maths drawn as maths."""
    move = prose_maths(note) if note else None
    return text_line(prose_maths(tex), move) if is_prose(tex) else math_line(tidy_tex(tex), move)


def _plain(tex: str) -> str:
    return _NOT_ALNUM.sub("", _UPRIGHT.sub("", tex)).lower()


_UPRIGHT_GROUP = re.compile(r"\\(?:mathrm|text)\s*\{[^{}]*\}")
# A power of ten in a calculator's spelling: "1.5e-3", "6.022E23".
_E_NOTATION = re.compile(r"(?<=\d)[eE](?=[-+]?\d)")
# Euler's number raised to a power: "20e^{-0.5}" is a number; the exponent's own letters
# ("e^{-t/RC}") still make a value symbolic.
_EULER = re.compile(r"(?<![A-Za-z\\])e(?=\s*\^)")


def in_symbols(tex: str) -> bool:
    """A value written in letters ("C V_0", "\\frac{1}{2}MR^2"): its units are its
    symbols', so none is written after it. A command (\\pi, \\times), a unit set upright,
    a calculator's power of ten or Euler's e is no symbol: "\\pi/3", "2400\\,\\mathrm{s}",
    "1.5e-3" and "20e^{-0.5}" are numbers."""
    plain = _E_NOTATION.sub(" ", _COMMAND.sub("", _UPRIGHT_GROUP.sub("", tex)))
    plain = _EULER.sub(" ", plain)
    return _LETTER.search(plain) is not None


def _in_words(value: str) -> bool:
    """A value written in words alone ("at rest", "mass of the rod"). One with a digit is a
    quantity, its unit written beside it ("20 km", "45 min"), and keeps its row."""
    return is_prose(value) and not any(char.isdigit() for char in value)


def _as_its_letter(given: Given) -> bool:
    """A given the question states as a letter, not a value ("a rod of mass M"): its value
    is its own symbol, or none, or words. It is listed by its meaning, ``$M$ (mass of the
    rod)``, never as "M = M kg" (RLC and rod questions, 2026-11-11)."""
    value = _SPACING.sub("", tidy_tex(given.value))
    own = value == _SPACING.sub("", tidy_symbol(given.symbol))
    return not value or own or _in_words(given.value)


def _meaning(given: Given) -> str:
    """What a given is, its maths as maths. A value written in words is said too:
    "v_0 | at rest | m/s | initial speed" reads "initial speed, at rest", and with no
    meaning of its own it is the meaning ("M | mass of the rod")."""
    said = given.value if _in_words(given.value) else ""
    return prose_maths(", ".join(words for words in (given.meaning, said) if words))


def _given_row(given: Given, marks: Sequence[str] = ()) -> str:
    """The given on its line, with ``marks``, its parts' letters, before it when one symbol
    has a value per part: ``(a) $d = 100\\,\\mathrm{m}$``. A given stated as its letter is
    that letter and what it is, as Required reads: ``$C$ (capacitance)``."""
    if _as_its_letter(given):
        meaning = _meaning(given)
        row = math_line(tidy_symbol(given.symbol))
        row = f"{row} ({meaning})" if meaning else row
        return lettered_line(marks, row) if marks else row
    value = tidy_tex(given.value)
    shown = quantity_tex(value, "" if in_symbols(value) else given.unit)
    # "500 g = 500 g" says nothing: a conversion to the same value is left out.
    if given.converted and _plain(given.converted) != _plain(shown):
        shown = f"{shown} = {tidy_tex(given.converted)}"
    row = math_line(f"{tidy_symbol(given.symbol)} = {shown}")
    return lettered_line(marks, row) if marks else row


def _given_rows(
    givens: Sequence[Given],
    *,
    naming: bool = True,
    letters: Sequence[Sequence[str]] | None = None,
) -> tuple[str, ...]:
    """Each given on its line (with ``letters``, each one's parts), then (with ``naming``)
    the ``where`` line naming the ones with a value (a letter is named on its own line)."""
    rows = [_given_row(given, letters[at] if letters else ()) for at, given in enumerate(givens)]
    named = where_line(
        [
            (tidy_symbol(given.symbol), _meaning(given))
            for given in givens
            if given.meaning and not _as_its_letter(given)
        ]
    )
    if rows and naming and named:
        rows.append(named)
    return tuple(rows)


def _given_section(solution: WorkedSolution, *, streaming: bool) -> tuple[str, ...]:
    # While the block streams, the line naming the givens waits until they are all in:
    # one more given would change it, and the phone has drawn what went out.
    complete = not streaming or bool(solution.required or solution.parts)
    givens = solution.given if complete else _decided(solution.given)
    return _given_rows(givens, naming=complete, letters=_record_letters(givens))


def _decided(givens: Sequence[Given]) -> Sequence[Given]:
    """The givens drawn while the block streams: those before the first one the model
    lettered, whose letter shows only if another value of its symbol comes. It and the rows
    after it wait for every given (the contract writes them first), never redrawn."""
    lettered = next((at for at, given in enumerate(givens) if given.part), len(givens))
    return givens[:lettered]


def _record_letters(givens: Sequence[Given]) -> list[tuple[str, ...]]:
    """Each given's letter as its record wrote it, kept only where its symbol has another
    value too (``_one_given``'s rule, before the parts are known)."""
    values = Counter(_symbol(given) for given in givens)
    return [(given.part,) if given.part and values[_symbol(given)] > 1 else () for given in givens]


def _started(part: Part) -> bool:
    return bool(part.formula or part.working or part.answers)


def _symbol(given: Given) -> str:
    return tidy_symbol(given.symbol)


def _part_of(letter: str, parts: Sequence[Part]) -> int | None:
    """The part a lettered given names: the part the model gave that letter, else the
    part shown under it."""
    named = next((at for at, part in enumerate(parts) if part.letter == letter), None)
    if named is not None:
        return named
    shown = next((at for at in range(len(parts)) if part_letter(at) == letter), None)
    return shown


_FUNCTION_WORDS = frozenset({"for", "of", "the", "by", "in", "on", "at", "to", "a", "an"})


def _one_meaning(givens: Sequence[Given]) -> list[Given]:
    """A symbol the parts name apart ("distance for car", "distance for train") is named
    by the words they share ("distance"): the one where-line names it once, for every
    part. Meanings that share nothing keep the first."""
    meanings: dict[str, list[str]] = {}
    for given in givens:
        if given.meaning:
            meanings.setdefault(_symbol(given), []).append(given.meaning)
    shared: dict[str, str] = {}
    for symbol, said in meanings.items():
        words = [meaning.split() for meaning in dict.fromkeys(said)]
        common: list[str] = []
        for column in zip(*words, strict=False):
            if len({word.lower() for word in column}) > 1:
                break
            common.append(column[0])
        while common and common[-1].lower() in _FUNCTION_WORDS:
            common.pop()
        shared[symbol] = " ".join(common) if common else said[0]
    return [
        given.model_copy(update={"meaning": shared[_symbol(given)]}) if given.meaning else given
        for given in givens
    ]


def _placed(shared: Sequence[Given], own: Sequence[Sequence[Given]]) -> dict[int, list[int]]:
    """Which parts an unlettered given of the whole question is, by its index. A symbol
    has one value in a part, so a given written for the whole question whose symbol a part
    gives on its own is the other parts' (``d = 100`` first, ``d = 300`` after "part: b":
    the first is part (a)'s), and a symbol given once per part, all first, is one value
    per part in order. Anything else is every part's."""
    placed: dict[int, list[int]] = {}
    for symbol in dict.fromkeys(_symbol(given) for given in shared):
        values = [at for at, given in enumerate(shared) if _symbol(given) == symbol]
        lacking = [at for at, mine in enumerate(own) if all(_symbol(g) != symbol for g in mine)]
        if len(values) == 1 and 0 < len(lacking) < len(own):
            placed[values[0]] = lacking
        elif len(values) > 1 and len(values) == len(lacking):
            placed.update((value, [at]) for value, at in zip(values, lacking, strict=True))
    return placed


def _one_given(
    solution: WorkedSolution, parts: Sequence[Part]
) -> tuple[list[Given], list[tuple[str, ...]]]:
    """Every given of the question in parts, for its one Given, each with the letters of
    the parts that use it only where its symbol has another value too: a car's $d = 100$
    and a train's $d = 300$ are told apart by them. A given is data, never a part: a pie
    chart's angles lettered by the parts that used them read as parts (2026-11-13). The
    whole question's come first, as written, so nothing drawn while the block streamed
    moves; a given written after a part's label follows. A given several parts give alike
    is one line."""
    # Parts are shown lettered in order, whatever letters the model wrote.
    letters = [part_letter(index) for index in range(len(parts))]
    of = {given.part: _part_of(given.part, parts) for given in solution.given if given.part}
    own = [
        [*part.given, *(g for g in solution.given if g.part and of[g.part] == index)]
        for index, part in enumerate(parts)
    ]
    shared = [given for given in solution.given if not given.part]
    placed = _placed(shared, own)
    rows: dict[str, tuple[Given, list[str]]] = {}

    def add(given: Given, marks: Sequence[str]) -> None:
        key = _given_row(given, ())
        kept = rows.setdefault(key, (given, []))
        kept[1].extend(mark for mark in marks if mark not in kept[1])

    unlettered = iter(range(len(shared)))
    for given in solution.given:
        if given.part:
            at_part = of[given.part]
            add(given, (given.part if at_part is None else letters[at_part],))
        else:
            at = next(unlettered)
            add(given, [letters[index] for index in placed.get(at, range(len(parts)))])
    for part, letter in zip(parts, letters, strict=True):
        for given in part.given:
            add(given, (letter,))
    kept = _one_meaning([given for given, _marks in rows.values()])

    def order(mark: str) -> int:
        return letters.index(mark) if mark in letters else len(letters)

    values = Counter(_symbol(given) for given in kept)
    return kept, [
        tuple(sorted(marks, key=order)) if values[_symbol(given)] > 1 else ()
        for given, (_given, marks) in zip(kept, rows.values(), strict=True)
    ]


def _working(part: Part) -> tuple[list[str], list[str], list[str]]:
    """The formula's rows, the substitution's and the steps', in the order written.

    A rearrangement or a move before any substitution belongs to the formula when there
    is one (``Solve for $t$`` under the law); with no formula it is a step, and so is
    every line after it. Lines after the first substitution carry it on.
    """
    formula: list[str] = []
    if part.formula is not None:
        formula.append(math_line(tidy_tex(part.formula.tex)))
    substitution: list[str] = []
    steps: list[str] = []
    for step in part.working:
        # With no formula, moves come first and the lines after them carry them on: one
        # Steps section, never a Substitution above the moves it follows.
        if step.kind == "substitution" and not (steps and part.formula is None):
            substitution.append(_line(step.tex))
            continue
        target = substitution if substitution else formula if part.formula else steps
        target.extend(_step_rows(step))
    return formula, substitution, steps


def _step_rows(step: Step) -> list[str]:
    if step.kind == "solve_for" and step.symbol:
        return [solve_for_line(tidy_symbol(step.symbol)), math_line(tidy_tex(step.tex))]
    return [_line(step.tex, step.move or None)]


def _answer_line(answer: Answer, layout: WorkedLayout) -> str:
    """The value with its unit in maths, and a note after it in brackets: a short label
    ("east") stays on the card, and a remark ("about 1.20√(gh); option A gives …") goes
    in a sentence under it (``services.remark_after_answer``), its maths drawn as maths."""
    tex = tidy_tex(answer.value)
    value = quantity_tex(tex, "" if in_symbols(tex) else answer.unit)
    # A symbol that only repeats the unit ("cm | 10000 | cm") or is a word names nothing.
    named = answer.symbol and answer.symbol != answer.unit and not names_nothing(answer.symbol)
    symbol = tidy_symbol(answer.symbol) if named else ""
    shown = value if layout.law_heading or not symbol else f"{symbol} = {value}"
    note = prose_maths(answer.note)
    return f"{math_line(shown)} ({note})" if note else math_line(shown)


def _part_body(
    part: Part,
    layout: WorkedLayout,
    opening: tuple[tuple[str, ...], tuple[str, ...]],
    answer_heading: str | None,
) -> str:
    """One part's sections; with ``answer_heading``, closed by its answer's value."""
    formula, substitution, steps = _working(part)
    given, find = opening
    body = render_workout(
        Workout(
            given=given,
            find=find,
            formula=tuple(formula),
            substitution=tuple(substitution),
            steps=tuple(steps),
            # The formula's name heads it, never a note on its line.
            formula_heading=formula_title(part.formula.name) if part.formula else None,
        ),
        answer_heading=answer_heading if part.answers else None,
    )
    if not part.answers or answer_heading is None:
        return body
    values = _HARD_BREAK.join(_answer_line(answer, layout) for answer in part.answers)
    return f"{body}\n\n{values}"


def _find_rows(solution: WorkedSolution) -> tuple[str, ...]:
    return tuple(
        text_line(prose_maths(item.symbol), prose_maths(item.meaning) or None)
        if names_nothing(item.symbol)
        else math_line(tidy_symbol(item.symbol), prose_maths(item.meaning) or None)
        for item in solution.required
    )


def _answered_symbols(part: Part) -> str:
    """The symbols the part's answers name, in order, once each (``v``, ``v, t``)."""
    named = (
        tidy_symbol(answer.symbol)
        for answer in part.answers
        if answer.symbol and answer.symbol != answer.unit and not names_nothing(answer.symbol)
    )
    return ", ".join(dict.fromkeys(named))


def _asked_by_parts(
    solution: WorkedSolution, parts: Sequence[Part], written: tuple[str, ...]
) -> tuple[str, ...]:
    """What is asked, one line per part: a question in N parts lists N lines, lettered by
    the caller as the server's own parts are. The ``required`` records are the lines as
    written when there is one per part (or the question has one part and some record).
    Otherwise (one record for every part, or none, live 2026-11-02: one ``v | average
    speed`` above a car and a train) each part's line names the symbol its answer gives,
    else the record's, and means the part's title, else what that record asks
    (``$v$ (speed of the car)``). ``written``: the records' own lines."""
    asked = solution.required
    if asked and (len(parts) < 2 or len(asked) == len(parts)):
        return written
    rows: list[str] = []
    for index, part in enumerate(parts):
        record = asked[index] if index < len(asked) else asked[0] if len(asked) == 1 else None
        # A record's "symbol" in words names every part at once, never this one.
        own = record.symbol if record and not names_nothing(record.symbol) else ""
        answered = _answered_symbols(part)
        symbol = answered or own
        # The record's meaning is its own symbol's: a part finding another ("t" under
        # "v | average speed") is named by its title or by its symbol alone.
        shared = record is not None and (not answered or tidy_symbol(answered) == tidy_symbol(own))
        meaning = prose_maths(part.title or (record.meaning if record and shared else ""))
        if symbol:
            rows.append(math_line(tidy_symbol(symbol), meaning or None))
        elif meaning:
            rows.append(text_line(meaning))
        else:
            return written  # a part that names nothing: no line can be lettered for it
    return tuple(rows)


def render_worked(
    solution: WorkedSolution, layout: WorkedLayout, *, streaming: bool = False
) -> str:
    """The solution as a worked reply. ``streaming``: the block is still being written, so
    a line that a later record could change is left out until it cannot."""
    # While the block streams, what is asked waits until the working shows whether the
    # question is in parts: in parts it is lettered, and a drawn line is never rewritten.
    settled = (
        not streaming
        or solution.labelled
        or any(part.formula or part.working or part.answers for part in solution.parts)
    )
    required = _find_rows(solution) if settled else ()
    # A question asking for several things may come apart at its next law
    # (``worked_solution.assemble``), so while it streams it is drawn in parts: a part
    # added later extends what was drawn, never moves it.
    in_parts = solution.labelled or (streaming and settled and len(solution.required) > 1)
    if not in_parts:
        part = solution.parts[0] if solution.parts else Part()
        opening = (_given_section(solution, streaming=streaming), required)
        return _part_body(part, layout, opening, ANSWER)
    return _render_in_parts(solution, layout, required, streaming=streaming)


def _render_in_parts(
    solution: WorkedSolution,
    layout: WorkedLayout,
    required: tuple[str, ...],
    *,
    streaming: bool,
) -> str:
    """The one layout every question in parts has (``services/worked_parts``), as the
    server's own parts: one Given holding every given, a value only some parts use
    lettered by them (``_one_given``), one Required naming what each part finds, then each
    part, closed by its answer, with no Given of its own. What is asked comes before the
    parts, so it is lettered by its own order: a part that streams in later never rewrites
    it. The contract asks for every given first, so the one Given streams in place; a
    given the model wrote after a part's label waits at that part while the block streams
    and moves up to the one Given once it is whole (done carries that text)."""
    shown = list(solution.parts)
    if not streaming:
        # One line per part, drawn above the parts, so only once the block is whole (done
        # carries the text): while it streams the records are shown as written.
        required = _asked_by_parts(solution, shown, required)
    complete = not streaming or bool(required or solution.parts)
    if streaming:
        # A part waits for the answer above it: one written later, with the others at the
        # end, would land above what was drawn after it.
        unanswered = next((at for at, part in enumerate(shown) if not part.answers), None)
        shown = shown if unanswered is None else shown[: unanswered + 1]
        # Each given stays where it was written: the whole question's in the one Given, one
        # written after a part's label at that part for now. A lettered one keeps its letter
        # by the whole block's rule (one symbol's values apart), so the finished block
        # draws the rows the stream drew.
        given = _given_rows(
            solution.given, naming=complete, letters=_record_letters(solution.given)
        )
        own = [list(part.given) for part in shown]
    else:
        # The whole block: every given in the one Given, none under a part.
        everything, letters = _one_given(solution, shown)
        given = _given_rows(everything, letters=letters)
        own = [[] for _part in shown]
    last = len(shown) - 1
    parts = [
        WorkedPart(
            title=prose_maths(
                part.title
                or (solution.required[index].meaning if index < len(solution.required) else "")
            ),
            working=_part_body(part, layout, ((), ()), None),
            after=_HARD_BREAK.join(_answer_line(answer, layout) for answer in part.answers),
            # The last part's where-line waits, while it streams, until its givens are in.
            given=_given_rows(own[index], naming=not streaming or index < last or _started(part)),
        )
        for index, part in enumerate(shown)
    ]
    asked = [f"({part_letter(index)}) {row}" for index, row in enumerate(required)]
    return render_parts(
        parts,
        given,
        required=asked if len(required) > 1 else required,
        hoist=not streaming,
    )

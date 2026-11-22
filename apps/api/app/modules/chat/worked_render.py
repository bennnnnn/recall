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

from app.modules.chat.worked_answers import (
    WorkedLayout,
    answer_lines,
    concludes,
    in_symbols,
    in_words,
    sentence_answer,
)
from app.modules.chat.worked_lines import marks_maths, split_line, typed_signs
from app.modules.chat.worked_prose import prose_maths
from app.modules.chat.worked_solution import Given, Part, Step, WorkedSolution
from app.modules.chat.worked_text import (
    formula_title,
    is_prose,
    names_nothing,
    tidy_symbol,
    tidy_tex,
)
from app.modules.chat.worked_units import quantity_tex
from app.modules.chat.worked_values import writes_its_unit
from app.services.worked_parts import WorkedPart, lettered_line, part_letter, render_parts
from app.services.workout import (
    ANSWER,
    Workout,
    math_line,
    note_from_label,
    render_workout,
    solve_for_line,
    text_line,
    where_line,
)

# The layout and the value reader are the answers module's; callers name them here too.
__all__ = ["WorkedLayout", "in_symbols", "render_worked"]

_UPRIGHT = re.compile(r"\\(?:mathrm|text)|\\[,;! ]")
_NOT_ALNUM = re.compile(r"[^A-Za-z0-9.]")
_SPACING = re.compile(r"[\s{}]")
# A letter outside a command: a value that holds one is written in symbols ("C V_0").
_COMMAND = re.compile(r"\\[A-Za-z]+")
_LETTER = re.compile(r"[A-Za-z]")
_RELATION = re.compile(r"(?<![<>!])=|\\(?:le|ge|lt|gt|neq)\b|[<>≤≥≠]")


def _line(tex: str, note: str | None = None) -> str:
    """One state: maths, or the model's sentence as text; its move's maths drawn as maths.
    Words the model wrote around the maths ("Simplify: …", "…, where n = 6") are its note,
    beside it (``worked_lines``); a line with ``$…$`` of its own is a sentence."""
    move = prose_maths(note) if note else None
    tex = typed_signs(tex)
    before, maths, after = split_line(tex)
    if marks_maths(maths) or is_prose(maths) or _in_sentences(maths):
        return text_line(prose_maths(tex), move)
    said = [prose_maths(words) for words in (before, after) if words]
    if said:
        move = "; ".join([note_from_label(said[0]), *said[1:], *([move] if move else [])])
    return math_line(tidy_tex(maths), move)


# A braced group or a command: words in a group are a script's or an argument's
# (v_{avg}, \frac{distance}{time}, \text{W}), never the sentence's.
_COMMAND_GROUP = re.compile(r"\{[^{}]*\}|\\[A-Za-z]+")
_SENTENCE_WORD = re.compile(r"[A-Za-z]{3,}")


def _in_sentences(tex: str) -> bool:
    """A maths field written as words around some maths ("image is as far behind the
    mirror as the object is in front: D = 2d"): three words or more outside commands. Set as
    one formula, it was an italic sentence run off the screen (G8 t42, t47, 2026-11-18)."""
    plain = tex
    for _ in range(4):  # nested groups, innermost first
        plain = _COMMAND_GROUP.sub(" ", plain)
    return len(_SENTENCE_WORD.findall(plain)) >= 3


def _plain(tex: str) -> str:
    return _NOT_ALNUM.sub("", _UPRIGHT.sub("", tex)).lower()


def _as_its_letter(given: Given) -> bool:
    """A given the question states as a letter, not a value ("a rod of mass M"): its value
    is its own symbol, or none, or words. It is listed by its meaning, ``$M$ (mass of the
    rod)``, never as "M = M kg" (RLC and rod questions, 2026-11-11)."""
    value = _SPACING.sub("", tidy_tex(given.value))
    own = value == _symbol_key(given.symbol)
    return not value or own or in_words(given.value)


def _meaning(given: Given) -> str:
    """What a given is, its maths as maths. A value written in words is said too:
    "v_0 | at rest | m/s | initial speed" reads "initial speed, at rest", and with no
    meaning of its own it is the meaning ("M | mass of the rod")."""
    said = given.value if in_words(given.value) else ""
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
    if _RELATION.search(value):
        # An equation given ("x^2 + y^2 - 8x + 6y - 11 = 0") is its own line, never "eq =" it.
        meaning = _meaning(given)
        row = math_line(value)
        row = f"{row} ({meaning})" if meaning else row
        return lettered_line(marks, row) if marks else row
    unit = "" if in_symbols(value) or writes_its_unit(value, given.unit) else given.unit
    shown = quantity_tex(value, unit)
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
            if given.meaning and not _as_its_letter(given) and not _RELATION.search(given.value)
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
        formula.append(_line(part.formula.tex))
    substitution: list[str] = []
    steps: list[str] = []
    for step in part.working:
        if step.kind == "say":
            continue  # words, said after the working (``_said``)
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
        return [solve_for_line(tidy_symbol(step.symbol)), _line(step.tex)]
    return [_line(step.tex, step.move or None)]


def _part_body(
    part: Part,
    layout: WorkedLayout,
    opening: tuple[tuple[str, ...], tuple[str, ...]],
    answer_heading: str | None,
) -> str:
    """One part's sections; with ``answer_heading``, closed by its answer's value. A part
    joined from several (``Part.then``) lays each stage out under its own formula."""
    if part.then:
        return _staged_body(part, layout, opening, answer_heading)
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
        before_answer=_said(part),
    )
    if not part.answers or answer_heading is None:
        return body
    return f"{body}\n\n{answer_lines(part.answers, layout)}"


def _staged_body(
    part: Part,
    layout: WorkedLayout,
    opening: tuple[tuple[str, ...], tuple[str, ...]],
    answer_heading: str | None,
) -> str:
    """A joined part: its first stage with the opening, each further stage's formula,
    substitution and words in turn, then its one Answer heading and every value."""
    stages = [part.model_copy(update={"then": (), "answers": ()}), *part.then]
    bodies = [
        _part_body(stage, layout, opening if index == 0 else ((), ()), None)
        for index, stage in enumerate(stages)
    ]
    body = "\n\n".join(piece for piece in bodies if piece.strip())
    if not part.answers or answer_heading is None:
        return body
    return f"{body}\n\n**{answer_heading}**\n\n{answer_lines(part.answers, layout)}"


def _said(part: Part) -> str | None:
    """What the part says in words (its ``say`` records), as one paragraph of text with
    its maths as maths: a part asked in words ("What do these numbers mean?") was set as
    one italic formula under Substitution, run off the screen (G8 t42, 2026-11-18)."""
    said = [prose_maths(step.tex) for step in part.working if step.kind == "say"]
    # Each record is a sentence of its own, ended as one: two run together read as one.
    return " ".join(_ended(words) for words in said if words) or None


def _ended(sentence: str) -> str:
    return sentence if sentence.rstrip("$)*").endswith((".", "!", "?", ":")) else f"{sentence}."


def _find_rows(solution: WorkedSolution) -> tuple[str, ...]:
    concluded = _concluded(solution)
    return tuple(
        text_line(prose_maths(item.meaning))
        if item.meaning and _symbol_key(item.symbol) in concluded
        else text_line(prose_maths(item.symbol), prose_maths(item.meaning) or None)
        if names_nothing(item.symbol)
        else math_line(tidy_symbol(item.symbol), prose_maths(item.meaning) or None)
        for item in solution.required
    )


def _symbol_key(symbol: str) -> str:
    """``symbol`` as one key however it is braced or spaced: s1, s_1 and s_{1} alike."""
    return _SPACING.sub("", tidy_symbol(symbol))


def _concluded(solution: WorkedSolution) -> set[str]:
    """The symbols whose answer is a conclusion in words ("yes, all the ice melts"): no
    quantity, so they are asked by their words alone; "$slide_{back}$ (whether it slides
    back)" set an invented symbol in maths (phys30, 2026-11-16). Compared tidied:
    s_1 in Find is s_{1} in the answer. A conclusion with no symbol of its own
    ("answer: | yes, …") concludes its own ask: its part's, when each part has one, or
    the ask no other answer names in a solution of one part (Gemini on #2489)."""
    answers = [answer for part in solution.parts for answer in part.answers]
    concluded = {
        _symbol_key(answer.symbol)
        for answer in answers
        if answer.symbol and (concludes(answer) or sentence_answer(answer) is not None)
    }
    paired = len(solution.parts) == len(solution.required)
    for at, part in enumerate(solution.parts):
        if not any(
            not answer.symbol.strip() and (concludes(answer) or sentence_answer(answer) is not None)
            for answer in part.answers
        ):
            continue
        if paired:
            concluded.add(_symbol_key(solution.required[at].symbol))
        elif len(solution.parts) == 1:
            named = {_symbol_key(answer.symbol) for answer in answers if answer.symbol.strip()}
            concluded |= {
                _symbol_key(item.symbol)
                for item in solution.required
                if _symbol_key(item.symbol) not in named
            }
    return concluded


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
            # A meaning that only writes the symbol again ("$AD$ (AD)") says nothing.
            said = meaning if _plain(meaning) != _plain(tidy_symbol(symbol)) else ""
            rows.append(math_line(tidy_symbol(symbol), said or None))
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
            after=answer_lines(part.answers, layout),
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
